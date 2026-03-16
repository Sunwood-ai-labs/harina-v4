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
    extraction: ReceiptExtraction | None
    summary: str
    drive_file_id: str | None
    drive_file_url: str | None
    spreadsheet_url: str | None
    rows: list[list[str]]
    google_write_performed: bool
    skipped_existing: bool = False
    skipped_attachment_name: str | None = None

    @property
    def row(self) -> list[str]:
        if not self.rows:
            raise RuntimeError("No receipt rows are available for this result.")
        return self.rows[0]

    def as_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "drive_file_id": self.drive_file_id,
            "drive_file_url": self.drive_file_url,
            "spreadsheet_url": self.spreadsheet_url,
            "row_count": len(self.rows),
            "row": self.rows[0] if self.rows else None,
            "rows": self.rows,
            "google_write_performed": self.google_write_performed,
            "skipped_existing": self.skipped_existing,
            "skipped_attachment_name": self.skipped_attachment_name,
            "extraction": self.extraction.model_dump(mode="json") if self.extraction is not None else None,
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
        rescan_existing: bool = False,
    ) -> ProcessedReceipt:
        use_google_category_catalog = self.google_workspace is not None and write_to_google
        spreadsheet_url: str | None = None
        if write_to_google:
            if self.google_workspace is None:
                raise RuntimeError("Google Workspace is not configured for receipt uploads.")
            spreadsheet_url = self.google_workspace.spreadsheet_url
            if not rescan_existing and context.attachment_name:
                if await self.google_workspace.receipt_attachment_exists(attachment_name=context.attachment_name):
                    attachment_name = context.attachment_name
                    return ProcessedReceipt(
                        extraction=None,
                        summary=f"Skipped because {attachment_name} is already recorded in Google Sheets.",
                        drive_file_id=None,
                        drive_file_url=None,
                        spreadsheet_url=spreadsheet_url,
                        rows=[],
                        google_write_performed=False,
                        skipped_existing=True,
                        skipped_attachment_name=attachment_name,
                    )

        category_options: list[str] = []
        if use_google_category_catalog:
            category_options = await self.google_workspace.list_receipt_categories()

        extraction = await self.gemini.extract(
            image_bytes=image_bytes,
            mime_type=mime_type,
            filename=filename,
            category_options=category_options,
        )

        if use_google_category_catalog:
            await self.google_workspace.append_receipt_categories(
                [
                    item.category or ""
                    for item in extraction.line_items
                ],
                source="gemini",
            )

        drive_file_id: str | None = None
        drive_file_url: str | None = None
        if write_to_google:
            drive_file = await self.google_workspace.upload_receipt_image(
                file_name=build_drive_file_name(filename, extraction),
                mime_type=mime_type,
                image_bytes=image_bytes,
            )
            drive_file_id = drive_file.file_id
            drive_file_url = drive_file.web_view_link
            spreadsheet_url = self.google_workspace.spreadsheet_url

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
            spreadsheet_url=spreadsheet_url,
            rows=rows,
            google_write_performed=write_to_google,
        )
