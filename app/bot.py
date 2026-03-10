from __future__ import annotations

import logging

import discord

from app.config import Settings
from app.formatters import build_drive_file_name, build_receipt_row, format_receipt_summary, is_image_attachment
from app.gemini_client import GeminiReceiptExtractor
from app.google_workspace import GoogleWorkspaceClient


logger = logging.getLogger(__name__)


class ReceiptBot(discord.Client):
    def __init__(self, *, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True

        super().__init__(intents=intents)

        self.settings = settings
        self.gemini = GeminiReceiptExtractor(api_key=settings.gemini_api_key, model=settings.gemini_model)
        self.google_workspace = GoogleWorkspaceClient(
            service_account_info=settings.service_account_info,
            drive_folder_id=settings.google_drive_folder_id,
            spreadsheet_id=settings.google_sheets_spreadsheet_id,
            sheet_name=settings.google_sheets_sheet_name,
        )

    async def setup_hook(self) -> None:
        await self.google_workspace.ensure_receipt_sheet()

    async def on_ready(self) -> None:
        if self.user:
            logger.info("Receipt bot is ready as %s", self.user)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        if self.settings.allowed_channel_ids and message.channel.id not in self.settings.allowed_channel_ids:
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
        image_bytes = await attachment.read()
        mime_type = attachment.content_type or "image/jpeg"

        extraction = await self.gemini.extract(
            image_bytes=image_bytes,
            mime_type=mime_type,
            filename=attachment.filename,
        )

        drive_file = await self.google_workspace.upload_receipt_image(
            file_name=build_drive_file_name(attachment.filename, extraction),
            mime_type=mime_type,
            image_bytes=image_bytes,
        )

        row = build_receipt_row(
            message=message,
            attachment=attachment,
            extraction=extraction,
            drive_file_id=drive_file.file_id,
            drive_file_url=drive_file.web_view_link,
        )
        await self.google_workspace.append_receipt_row(row)

        return format_receipt_summary(extraction, drive_file.web_view_link)
