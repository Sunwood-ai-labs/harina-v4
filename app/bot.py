from __future__ import annotations

import logging
from dataclasses import dataclass

import discord

from app.config import Settings
from app.discord_debug import DiscordDebugSession, serialize_message
from app.formatters import build_receipt_embed, build_receipt_links_view, is_image_attachment
from app.gemini_client import GeminiReceiptExtractor
from app.google_workspace import GoogleWorkspaceClient
from app.processor import ProcessedReceipt, ReceiptProcessor


logger = logging.getLogger(__name__)

PROCESSING_REACTION = "🧾"
ERROR_EMBED_TITLE = "Receipt Processing Failed"
ERROR_MESSAGE = (
    "Receipt processing failed. Check the Gemini, Google Drive, and Google Sheets settings and image contents."
)
SKIPPED_EXISTING_EMBED_TITLE_SUFFIX = "Skipped"
THREAD_NAME_PREFIX = "receipt"
BOT_EXHAUSTED_KEYS_RETRY_DELAY_SECONDS = 60 * 60
BOT_EXHAUSTED_KEYS_RETRY_COUNT = 1


@dataclass(frozen=True)
class AttachmentProcessingOutcome:
    attachment: discord.Attachment
    embed: discord.Embed
    view: discord.ui.View | None
    ok: bool


def build_receipt_thread_name(*, message_id: int, attachment_count: int) -> str:
    suffix = "receipt" if attachment_count == 1 else f"{attachment_count}-receipts"
    return f"{THREAD_NAME_PREFIX}-{message_id}-{suffix}"


def should_process_message(
    *,
    author_is_bot: bool,
    author_id: int,
    self_user_id: int | None,
    content: str,
    channel_id: int,
    allowed_channel_ids: set[int],
    test_message_prefix: str,
) -> bool:
    if author_is_bot:
        is_self_test_message = self_user_id is not None and author_id == self_user_id and content.startswith(
            test_message_prefix
        )
        if not is_self_test_message:
            return False

    if allowed_channel_ids and channel_id not in allowed_channel_ids:
        return False

    return True


class ReceiptBot(discord.Client):
    def __init__(self, *, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True

        super().__init__(intents=intents)

        self.settings = settings
        self.settings.require_google_workspace()
        self.debug_session = DiscordDebugSession.create(
            base_dir=settings.discord_debug_log_dir_path,
            purpose="receipt-bot",
        )
        self.processor = ReceiptProcessor(
            gemini=GeminiReceiptExtractor(
                api_keys=settings.require_gemini_api_keys(),
                model=settings.gemini_model,
                exhausted_keys_retry_delay_seconds=BOT_EXHAUSTED_KEYS_RETRY_DELAY_SECONDS,
                exhausted_keys_retry_count=BOT_EXHAUSTED_KEYS_RETRY_COUNT,
            ),
            google_workspace=GoogleWorkspaceClient(
                credentials=settings.google_credentials,
                drive_folder_id=settings.google_drive_folder_id or "",
                spreadsheet_id=settings.google_sheets_spreadsheet_id or "",
                sheet_name=settings.google_sheets_sheet_name,
                category_sheet_name=settings.google_sheets_category_sheet_name,
            ),
        )

    async def setup_hook(self) -> None:
        await self.processor.ensure_receipt_sheet()

    async def on_ready(self) -> None:
        if self.user:
            logger.info("Receipt bot is ready as %s", self.user)
            self.debug_session.write_event("bot_ready", user_id=self.user.id, user_name=str(self.user))

    async def on_message(self, message: discord.Message) -> None:
        if not should_process_message(
            author_is_bot=message.author.bot,
            author_id=message.author.id,
            self_user_id=self.user.id if self.user else None,
            content=message.content or "",
            channel_id=message.channel.id,
            allowed_channel_ids=self.settings.allowed_channel_ids,
            test_message_prefix=self.settings.discord_test_message_prefix,
        ):
            return

        receipt_attachments = [attachment for attachment in message.attachments if is_image_attachment(attachment)]
        if not receipt_attachments:
            return

        logger.info(
            "Processing Discord message %s in channel %s with %s receipt attachment(s)",
            message.id,
            message.channel.id,
            len(receipt_attachments),
        )
        self.debug_session.write_event(
            "message_received",
            message=serialize_message(message),
            receipt_attachment_count=len(receipt_attachments),
        )

        try:
            await message.add_reaction(PROCESSING_REACTION)
        except discord.HTTPException:
            logger.warning("Could not add reaction to message %s", message.id)

        try:
            response_thread = await self._get_response_thread(
                message=message,
                attachment_count=len(receipt_attachments),
            )
            outcomes = []
            for index, attachment in enumerate(receipt_attachments, start=1):
                outcomes.append(
                    await self._process_attachment_outcome(
                        message=message,
                        attachment=attachment,
                        index=index,
                        total_attachments=len(receipt_attachments),
                    )
                )

            await self._reply_with_outcomes(target=response_thread, outcomes=outcomes)
            self.debug_session.write_event(
                "message_processed",
                message_id=message.id,
                target=self._describe_messageable(target=response_thread),
                attachment_count=len(receipt_attachments),
                ok_count=sum(1 for outcome in outcomes if outcome.ok),
                error_count=sum(1 for outcome in outcomes if not outcome.ok),
            )
        except Exception:  # noqa: BLE001
            logger.exception("Receipt processing failed for message %s", message.id)
            self.debug_session.write_event(
                "message_processing_failed",
                message_id=message.id,
                channel_id=message.channel.id,
            )
            error_embed = discord.Embed(
                title=ERROR_EMBED_TITLE,
                description=ERROR_MESSAGE,
                color=discord.Color.red(),
            )
            await self._send_error_embed(
                message=message,
                error_embed=error_embed,
                attachment_count=len(receipt_attachments),
            )

    async def _reply_with_outcomes(
        self,
        *,
        target: discord.abc.Messageable,
        outcomes: list[AttachmentProcessingOutcome],
    ) -> None:
        if not outcomes:
            return

        for outcome in outcomes:
            logger.info(
                "Sending receipt embed to Discord target %s",
                self._describe_messageable(target),
            )
            await target.send(embed=outcome.embed, view=outcome.view)
            self.debug_session.write_event(
                "embed_sent",
                target=self._describe_messageable(target),
                embed_title=outcome.embed.title,
                source_filename=outcome.attachment.filename,
                has_view=outcome.view is not None,
            )

    async def _send_error_embed(
        self,
        *,
        message: discord.Message,
        error_embed: discord.Embed,
        attachment_count: int,
    ) -> None:
        try:
            response_thread = await self._get_response_thread(message=message, attachment_count=attachment_count)
            logger.info(
                "Sending error embed for message %s to Discord target %s",
                message.id,
                self._describe_messageable(response_thread),
            )
            await response_thread.send(embed=error_embed)
            self.debug_session.write_event(
                "error_embed_sent",
                message_id=message.id,
                target=self._describe_messageable(response_thread),
            )
        except Exception:  # noqa: BLE001
            logger.exception("Could not send thread error response for message %s", message.id)
            logger.info("Falling back to direct reply for message %s", message.id)
            self.debug_session.write_event(
                "error_embed_send_failed",
                message_id=message.id,
                channel_id=message.channel.id,
            )
            await message.reply(embed=error_embed, mention_author=False)

    async def _get_response_thread(
        self,
        *,
        message: discord.Message,
        attachment_count: int,
    ) -> discord.Thread | discord.abc.Messageable:
        existing_thread = getattr(message, "thread", None)
        if existing_thread is not None:
            logger.info("Using existing response thread %s for message %s", existing_thread.id, message.id)
            return existing_thread

        if isinstance(message.channel, discord.Thread):
            logger.info("Message %s already arrived inside thread %s", message.id, message.channel.id)
            return message.channel

        thread_name = build_receipt_thread_name(message_id=message.id, attachment_count=attachment_count)
        try:
            logger.info("Creating response thread '%s' for message %s", thread_name, message.id)
            thread = await message.create_thread(name=thread_name)
            logger.info("Created response thread %s for message %s", thread.id, message.id)
            self.debug_session.write_event(
                "thread_created",
                message_id=message.id,
                thread_id=thread.id,
                thread_name=thread.name,
            )
            return thread
        except discord.HTTPException:
            logger.exception("Could not create response thread for message %s", message.id)
            logger.info("Falling back to parent channel %s for message %s", message.channel.id, message.id)
            self.debug_session.write_event(
                "thread_create_failed",
                message_id=message.id,
                channel_id=message.channel.id,
            )
            return message.channel

    async def _process_attachment_outcome(
        self,
        *,
        message: discord.Message,
        attachment: discord.Attachment,
        index: int,
        total_attachments: int,
    ) -> AttachmentProcessingOutcome:
        title = f"Receipt {index}" if total_attachments > 1 else "Receipt"
        try:
            logger.info(
                "Processing attachment %s/%s for message %s: %s",
                index,
                total_attachments,
                message.id,
                attachment.filename,
            )
            processed = await self._process_attachment(message=message, attachment=attachment)
        except Exception:  # noqa: BLE001
            logger.exception("Receipt processing failed for attachment %s on message %s", attachment.id, message.id)
            self.debug_session.write_event(
                "attachment_failed",
                message_id=message.id,
                attachment_id=attachment.id,
                filename=attachment.filename,
                index=index,
                total_attachments=total_attachments,
            )
            return AttachmentProcessingOutcome(
                attachment=attachment,
                embed=discord.Embed(
                    title=f"{title} Failed",
                    description=f"{ERROR_MESSAGE}\nSource: `{attachment.filename}`",
                    color=discord.Color.red(),
                ),
                view=None,
                ok=False,
            )

        logger.info(
            "Processed attachment %s/%s for message %s successfully: %s",
            index,
            total_attachments,
            message.id,
            attachment.filename,
        )
        if processed.skipped_existing:
            self.debug_session.write_event(
                "attachment_skipped_existing",
                message_id=message.id,
                attachment_id=attachment.id,
                filename=attachment.filename,
                index=index,
                total_attachments=total_attachments,
            )
            return AttachmentProcessingOutcome(
                attachment=attachment,
                embed=discord.Embed(
                    title=f"{title} {SKIPPED_EXISTING_EMBED_TITLE_SUFFIX}",
                    description=(
                        f"Skipped because `{processed.skipped_attachment_name or attachment.filename}` is already "
                        "recorded in Google Sheets."
                    ),
                    color=discord.Color.orange(),
                ),
                view=build_receipt_links_view(
                    spreadsheet_url=processed.spreadsheet_url,
                ),
                ok=True,
            )

        self.debug_session.write_event(
            "attachment_processed",
            message_id=message.id,
            attachment_id=attachment.id,
            filename=attachment.filename,
            index=index,
            total_attachments=total_attachments,
        )
        return AttachmentProcessingOutcome(
            attachment=attachment,
            embed=build_receipt_embed(
                title=title,
                extraction=processed.extraction,
                drive_file_url=processed.drive_file_url,
                spreadsheet_url=processed.spreadsheet_url,
                source_label=attachment.filename,
            ),
            view=build_receipt_links_view(
                drive_file_url=processed.drive_file_url,
                spreadsheet_url=processed.spreadsheet_url,
            ),
            ok=True,
        )

    async def _process_attachment(self, *, message: discord.Message, attachment: discord.Attachment) -> ProcessedReceipt:
        return await self.processor.process_attachment(message=message, attachment=attachment)

    @staticmethod
    def _describe_messageable(target: discord.abc.Messageable) -> str:
        target_id = getattr(target, "id", "unknown")
        target_name = getattr(target, "name", None)
        if target_name:
            return f"{target.__class__.__name__}(id={target_id}, name={target_name})"
        return f"{target.__class__.__name__}(id={target_id})"
