from __future__ import annotations

from dataclasses import dataclass

import discord

from app.formatters import build_drive_file_name, build_receipt_row, format_receipt_summary
from app.gemini_client import GeminiReceiptExtractor
from app.google_workspace import GoogleWorkspaceClient


@dataclass(slots=True)
class ProcessedReceipt:
    summary: str
    drive_file_id: str
    drive_file_url: str | None
    row: list[str]


class ReceiptProcessor:
    def __init__(self, *, gemini: GeminiReceiptExtractor, google_workspace: GoogleWorkspaceClient) -> None:
        self.gemini = gemini
        self.google_workspace = google_workspace

    async def ensure_receipt_sheet(self) -> None:
        await self.google_workspace.ensure_receipt_sheet()

    async def process_attachment(
        self,
        *,
        message: discord.Message,
        attachment: discord.Attachment,
    ) -> ProcessedReceipt:
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

        return ProcessedReceipt(
            summary=format_receipt_summary(extraction, drive_file.web_view_link),
            drive_file_id=drive_file.file_id,
            drive_file_url=drive_file.web_view_link,
            row=row,
        )
