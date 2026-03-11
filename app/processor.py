from __future__ import annotations

from dataclasses import dataclass

import discord

from app.formatters import (
    ReceiptRecordContext,
    build_discord_receipt_context,
    build_drive_file_name,
    build_receipt_rows,
    format_receipt_summary,
)
from app.gemini_client import GeminiReceiptExtractor
from app.google_workspace import GoogleWorkspaceClient
from app.models import ReceiptExtraction


@dataclass(slots=True)
class ProcessedReceipt:
    extraction: ReceiptExtraction
    summary: str
    drive_file_id: str | None
    drive_file_url: str | None
    rows: list[list[str]]
    google_write_performed: bool

    @property
    def row(self) -> list[str]:
        return self.rows[0]

    def as_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "drive_file_id": self.drive_file_id,
            "drive_file_url": self.drive_file_url,
            "row_count": len(self.rows),
            "row": self.row,
            "rows": self.rows,
            "google_write_performed": self.google_write_performed,
            "extraction": self.extraction.model_dump(mode="json"),
        }


class ReceiptProcessor:
    def __init__(
        self,
        *,
        gemini: GeminiReceiptExtractor,
        google_workspace: GoogleWorkspaceClient | None = None,
    ) -> None:
        self.gemini = gemini
        self.google_workspace = google_workspace

    async def ensure_receipt_sheet(self) -> None:
        if self.google_workspace is None:
            raise RuntimeError("Google Workspace is not configured for this processor.")
        await self.google_workspace.ensure_receipt_sheet()

    async def process_attachment(
        self,
        *,
        message: discord.Message,
        attachment: discord.Attachment,
    ) -> ProcessedReceipt:
        return await self.process_receipt(
            context=build_discord_receipt_context(message, attachment),
            filename=attachment.filename,
            mime_type=attachment.content_type or "image/jpeg",
            image_bytes=await attachment.read(),
        )

    async def process_receipt(
        self,
        *,
        context: ReceiptRecordContext,
        filename: str,
        mime_type: str,
        image_bytes: bytes,
        write_to_google: bool = True,
    ) -> ProcessedReceipt:
        extraction = await self.gemini.extract(
            image_bytes=image_bytes,
            mime_type=mime_type,
            filename=filename,
        )

        drive_file_id: str | None = None
        drive_file_url: str | None = None
        if write_to_google:
            if self.google_workspace is None:
                raise RuntimeError("Google Workspace is not configured for receipt uploads.")
            drive_file = await self.google_workspace.upload_receipt_image(
                file_name=build_drive_file_name(filename, extraction),
                mime_type=mime_type,
                image_bytes=image_bytes,
            )
            drive_file_id = drive_file.file_id
            drive_file_url = drive_file.web_view_link

        rows = build_receipt_rows(
            context=context,
            extraction=extraction,
            drive_file_id=drive_file_id or "",
            drive_file_url=drive_file_url,
        )
        if write_to_google:
            await self.google_workspace.append_receipt_rows(rows)

        return ProcessedReceipt(
            extraction=extraction,
            summary=format_receipt_summary(extraction, drive_file_url),
            drive_file_id=drive_file_id,
            drive_file_url=drive_file_url,
            rows=rows,
            google_write_performed=write_to_google,
        )
