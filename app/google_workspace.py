from __future__ import annotations

import asyncio
from dataclasses import dataclass

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

from app.formatters import RECEIPT_SHEET_HEADERS
from app.models import ReceiptExtraction


SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


@dataclass(slots=True)
class UploadedDriveFile:
    file_id: str
    web_view_link: str | None


class GoogleWorkspaceClient:
    def __init__(self, *, service_account_info: dict, drive_folder_id: str, spreadsheet_id: str, sheet_name: str) -> None:
        credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        self._drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self._sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self._drive_folder_id = drive_folder_id
        self._spreadsheet_id = spreadsheet_id
        self._sheet_name = sheet_name

    async def ensure_receipt_sheet(self) -> None:
        await asyncio.to_thread(self._ensure_receipt_sheet_sync)

    async def upload_receipt_image(self, *, file_name: str, mime_type: str, image_bytes: bytes) -> UploadedDriveFile:
        return await asyncio.to_thread(self._upload_receipt_image_sync, file_name, mime_type, image_bytes)

    async def append_receipt_row(self, row: list[str]) -> None:
        await asyncio.to_thread(self._append_receipt_row_sync, row)

    def _ensure_receipt_sheet_sync(self) -> None:
        spreadsheet = (
            self._sheets.spreadsheets()
            .get(spreadsheetId=self._spreadsheet_id, fields="sheets.properties.title")
            .execute()
        )

        has_sheet = any(
            sheet.get("properties", {}).get("title") == self._sheet_name for sheet in spreadsheet.get("sheets", [])
        )

        if not has_sheet:
            (
                self._sheets.spreadsheets()
                .batchUpdate(
                    spreadsheetId=self._spreadsheet_id,
                    body={"requests": [{"addSheet": {"properties": {"title": self._sheet_name}}}]},
                )
                .execute()
            )

        current_header = (
            self._sheets.spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, range=f"'{self._sheet_name}'!1:1")
            .execute()
        )
        header_values = (current_header.get("values") or [[]])[0]

        if header_values == RECEIPT_SHEET_HEADERS:
            return

        (
            self._sheets.spreadsheets()
            .values()
            .update(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{self._sheet_name}'!A1",
                valueInputOption="RAW",
                body={"values": [RECEIPT_SHEET_HEADERS]},
            )
            .execute()
        )

    def _upload_receipt_image_sync(self, file_name: str, mime_type: str, image_bytes: bytes) -> UploadedDriveFile:
        media = MediaInMemoryUpload(image_bytes, mimetype=mime_type, resumable=False)
        response = (
            self._drive.files()
            .create(
                body={"name": file_name, "parents": [self._drive_folder_id]},
                media_body=media,
                fields="id,webViewLink",
            )
            .execute()
        )

        return UploadedDriveFile(file_id=response["id"], web_view_link=response.get("webViewLink"))

    def _append_receipt_row_sync(self, row: list[str]) -> None:
        (
            self._sheets.spreadsheets()
            .values()
            .append(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{self._sheet_name}'!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            )
            .execute()
        )
