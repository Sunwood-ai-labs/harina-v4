from __future__ import annotations

import logging

import discord

from app.config import Settings
from app.formatters import is_image_attachment
from app.gemini_client import GeminiReceiptExtractor
from app.google_workspace import GoogleWorkspaceClient
from app.processor import ReceiptProcessor


logger = logging.getLogger(__name__)


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
        self.processor = ReceiptProcessor(
            gemini=GeminiReceiptExtractor(api_key=settings.require_gemini_api_key(), model=settings.gemini_model),
            google_workspace=GoogleWorkspaceClient(
                credentials=settings.google_credentials,
                drive_folder_id=settings.google_drive_folder_id or "",
                spreadsheet_id=settings.google_sheets_spreadsheet_id or "",
                sheet_name=settings.google_sheets_sheet_name,
            ),
        )

    async def setup_hook(self) -> None:
        await self.processor.ensure_receipt_sheet()

    async def on_ready(self) -> None:
        if self.user:
            logger.info("Receipt bot is ready as %s", self.user)

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

        try:
            await message.add_reaction("🧾")
        except discord.HTTPException:
            logger.warning("Could not add reaction to message %s", message.id)

        try:
            summaries = []
            for index, attachment in enumerate(receipt_attachments, start=1):
                summary = await self._process_attachment(message=message, attachment=attachment)
                label = f"Receipt {index}" if len(receipt_attachments) > 1 else "Receipt"
                summaries.append(f"{label}: {summary}")

            await message.reply("\n".join(summaries), mention_author=False)
        except Exception:  # noqa: BLE001
            logger.exception("Receipt processing failed for message %s", message.id)
            await message.reply(
                "レシートの処理に失敗しました。Gemini / Google Drive / Google Sheets の設定と画像形式を確認してください。",
                mention_author=False,
            )

    async def _process_attachment(self, *, message: discord.Message, attachment: discord.Attachment) -> str:
        processed = await self.processor.process_attachment(message=message, attachment=attachment)
        return processed.summary
