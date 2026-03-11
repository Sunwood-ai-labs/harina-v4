from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaInMemoryUpload

from app.formatters import RECEIPT_SHEET_HEADERS


@dataclass(slots=True)
class UploadedDriveFile:
    file_id: str
    web_view_link: str | None


@dataclass(slots=True)
class DriveImageFile:
    file_id: str
    name: str
    mime_type: str
    created_time: str
    parents: list[str]
    web_view_link: str | None


class GoogleWorkspaceClient:
    def __init__(self, *, credentials, drive_folder_id: str, spreadsheet_id: str, sheet_name: str) -> None:
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

    async def append_receipt_rows(self, rows: list[list[str]]) -> None:
        await asyncio.to_thread(self._append_receipt_rows_sync, rows)

    async def list_image_files(self, *, folder_id: str) -> list[DriveImageFile]:
        return await asyncio.to_thread(self._list_image_files_sync, folder_id)

    async def download_file(self, *, file_id: str) -> bytes:
        return await asyncio.to_thread(self._download_file_sync, file_id)

    async def move_file(self, *, file_id: str, destination_folder_id: str) -> None:
        await asyncio.to_thread(self._move_file_sync, file_id, destination_folder_id)

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
        try:
            response = (
                self._drive.files()
                .create(
                    body={"name": file_name, "parents": [self._drive_folder_id]},
                    media_body=media,
                    fields="id,webViewLink",
                )
                .execute()
            )
        except HttpError as exc:
            if _is_service_account_quota_error(exc):
                raise RuntimeError(
                    "Google Drive rejected the upload because service accounts do not have storage quota on personal "
                    "My Drive. Use a Google Workspace shared drive or add OAuth refresh-token support for a user-owned "
                    "Drive account."
                ) from exc
            raise

        return UploadedDriveFile(file_id=response["id"], web_view_link=response.get("webViewLink"))

    def _append_receipt_row_sync(self, row: list[str]) -> None:
        self._append_receipt_rows_sync([row])

    def _append_receipt_rows_sync(self, rows: list[list[str]]) -> None:
        if not rows:
            return
        (
            self._sheets.spreadsheets()
            .values()
            .append(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{self._sheet_name}'!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": rows},
            )
                .execute()
        )

    def _list_image_files_sync(self, folder_id: str) -> list[DriveImageFile]:
        page_token = None
        files: list[DriveImageFile] = []

        while True:
            response = (
                self._drive.files()
                .list(
                    q=(
                        f"'{folder_id}' in parents and trashed = false "
                        "and mimeType != 'application/vnd.google-apps.folder'"
                    ),
                    fields="nextPageToken,files(id,name,mimeType,createdTime,parents,webViewLink)",
                    orderBy="createdTime asc",
                    pageSize=100,
                    pageToken=page_token,
                )
                .execute()
            )

            image_items = [item for item in response.get("files", []) if str(item.get("mimeType", "")).startswith("image/")]
            files.extend(_parse_drive_image_files(image_items))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return files

    def _download_file_sync(self, file_id: str) -> bytes:
        return self._drive.files().get_media(fileId=file_id).execute()

    def _move_file_sync(self, file_id: str, destination_folder_id: str) -> None:
        response = self._drive.files().get(fileId=file_id, fields="parents").execute()
        parents = response.get("parents", [])
        remove_parents = ",".join(parent for parent in parents if parent != destination_folder_id)
        (
            self._drive.files()
            .update(
                fileId=file_id,
                addParents=destination_folder_id,
                removeParents=remove_parents or None,
                fields="id,parents",
            )
            .execute()
        )


def _is_service_account_quota_error(exc: HttpError) -> bool:
    if getattr(exc, "resp", None) is not None and getattr(exc.resp, "status", None) != 403:
        return False

    text = str(exc)
    return "storageQuotaExceeded" in text or "Service Accounts do not have storage quota" in text


def _parse_drive_image_files(items: list[dict[str, Any]]) -> list[DriveImageFile]:
    return [
        DriveImageFile(
            file_id=item["id"],
            name=item["name"],
            mime_type=item["mimeType"],
            created_time=item.get("createdTime", ""),
            parents=list(item.get("parents", [])),
            web_view_link=item.get("webViewLink"),
        )
        for item in items
    ]
