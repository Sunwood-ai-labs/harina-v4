from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from dataclasses import dataclass
import re
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaInMemoryUpload

from app.category_catalog import (
    CATEGORY_SHEET_HEADERS,
    DEFAULT_CATEGORY_DESCRIPTION_MAP,
    build_default_category_rows,
    dedupe_category_names,
    normalize_category_name,
)
from app.formatters import RECEIPT_SHEET_HEADERS


RECEIPT_PROCESSED_AT_INDEX = RECEIPT_SHEET_HEADERS.index("processedAt")
RECEIPT_PURCHASE_DATE_INDEX = RECEIPT_SHEET_HEADERS.index("purchaseDate")
RECEIPT_ATTACHMENT_NAME_COLUMN = chr(ord("A") + RECEIPT_SHEET_HEADERS.index("attachmentName"))
YEAR_PATTERN = re.compile(r"(?<!\d)((?:19|20|21)\d{2})(?!\d)")


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
    def __init__(
        self,
        *,
        credentials,
        drive_folder_id: str,
        spreadsheet_id: str,
        sheet_name: str,
        category_sheet_name: str = "Categories",
    ) -> None:
        self._drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self._sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self._drive_folder_id = drive_folder_id
        self._spreadsheet_id = spreadsheet_id
        self._sheet_name = sheet_name
        self._category_sheet_name = category_sheet_name

    async def ensure_receipt_sheet(self) -> None:
        await asyncio.to_thread(self._ensure_receipt_sheet_sync)

    async def list_receipt_categories(self) -> list[str]:
        return await asyncio.to_thread(self._list_receipt_categories_sync)

    async def append_receipt_categories(self, categories: list[str], *, source: str = "gemini") -> list[str]:
        return await asyncio.to_thread(self._append_receipt_categories_sync, categories, source)

    async def upload_receipt_image(self, *, file_name: str, mime_type: str, image_bytes: bytes) -> UploadedDriveFile:
        return await asyncio.to_thread(self._upload_receipt_image_sync, file_name, mime_type, image_bytes)

    async def append_receipt_row(self, row: list[str]) -> None:
        await asyncio.to_thread(self._append_receipt_row_sync, row)

    async def append_receipt_rows(self, rows: list[list[str]]) -> None:
        await asyncio.to_thread(self._append_receipt_rows_sync, rows)

    async def list_receipt_attachment_names(self) -> set[str]:
        return await asyncio.to_thread(self._list_receipt_attachment_names_sync)

    async def receipt_attachment_exists(self, *, attachment_name: str) -> bool:
        return await asyncio.to_thread(self._receipt_attachment_exists_sync, attachment_name)

    async def list_image_files(self, *, folder_id: str) -> list[DriveImageFile]:
        return await asyncio.to_thread(self._list_image_files_sync, folder_id)

    async def download_file(self, *, file_id: str) -> bytes:
        return await asyncio.to_thread(self._download_file_sync, file_id)

    async def move_file(self, *, file_id: str, destination_folder_id: str) -> None:
        await asyncio.to_thread(self._move_file_sync, file_id, destination_folder_id)

    @property
    def spreadsheet_url(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self._spreadsheet_id}/edit"

    def _ensure_receipt_sheet_sync(self) -> None:
        self._ensure_sheet_with_header_sync(sheet_name=self._sheet_name, headers=RECEIPT_SHEET_HEADERS)
        self._ensure_category_sheet_sync()

    def _ensure_category_sheet_sync(self) -> None:
        self._ensure_sheet_with_header_sync(sheet_name=self._category_sheet_name, headers=CATEGORY_SHEET_HEADERS)

        existing_rows = (
            self._sheets.spreadsheets()
            .values()
            .get(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{self._category_sheet_name}'!A2:F",
            )
            .execute()
        ).get("values", [])
        if existing_rows:
            self._migrate_category_sheet_rows_sync(existing_rows)
            return

        seeded_rows = build_default_category_rows(timestamp=_timestamp_now())
        (
            self._sheets.spreadsheets()
            .values()
            .append(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{self._category_sheet_name}'!A2",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": seeded_rows},
            )
            .execute()
        )

    def _migrate_category_sheet_rows_sync(self, rows: list[list[str]]) -> None:
        updates: list[dict[str, object]] = []
        timestamp = _timestamp_now()

        for row_index, row in enumerate(rows, start=2):
            raw_name = row[0] if row else ""
            normalized_name = normalize_category_name(raw_name)
            if not normalized_name:
                continue

            description = DEFAULT_CATEGORY_DESCRIPTION_MAP.get(normalized_name)
            if normalized_name != raw_name:
                updates.append(
                    {
                        "range": f"'{self._category_sheet_name}'!A{row_index}:B{row_index}",
                        "values": [[normalized_name, description if description is not None else (row[1] if len(row) > 1 else "")]],
                    }
                )
                updates.append(
                    {
                        "range": f"'{self._category_sheet_name}'!E{row_index}",
                        "values": [[timestamp]],
                    }
                )

        if not updates:
            return

        (
            self._sheets.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"valueInputOption": "RAW", "data": updates},
            )
            .execute()
        )

    def _ensure_sheet_with_header_sync(self, *, sheet_name: str, headers: list[str]) -> None:
        spreadsheet = (
            self._sheets.spreadsheets()
            .get(spreadsheetId=self._spreadsheet_id, fields="sheets.properties.title")
            .execute()
        )

        has_sheet = any(sheet.get("properties", {}).get("title") == sheet_name for sheet in spreadsheet.get("sheets", []))

        if not has_sheet:
            (
                self._sheets.spreadsheets()
                .batchUpdate(
                    spreadsheetId=self._spreadsheet_id,
                    body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
                )
                .execute()
            )

        current_header = (
            self._sheets.spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, range=f"'{sheet_name}'!1:1")
            .execute()
        )
        header_values = (current_header.get("values") or [[]])[0]

        if header_values == headers:
            return

        (
            self._sheets.spreadsheets()
            .values()
            .update(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption="RAW",
                body={"values": [headers]},
            )
            .execute()
        )

    def _list_receipt_categories_sync(self) -> list[str]:
        self._ensure_category_sheet_sync()

        response = (
            self._sheets.spreadsheets()
            .values()
            .get(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{self._category_sheet_name}'!A2:C",
            )
            .execute()
        )

        categories: list[str] = []
        for row in response.get("values", []):
            category_name = normalize_category_name(row[0]) if row else ""
            if not category_name:
                continue

            is_active = row[2].strip().lower() if len(row) >= 3 and row[2] is not None else "true"
            if is_active in {"false", "0", "no", "inactive"}:
                continue
            categories.append(category_name)

        return dedupe_category_names(categories)

    def _append_receipt_categories_sync(self, categories: list[str], source: str) -> list[str]:
        candidate_categories = dedupe_category_names(categories)
        if not candidate_categories:
            return []

        existing_categories = self._list_receipt_categories_sync()
        existing_keys = {value.casefold() for value in existing_categories}
        categories_to_add = [value for value in candidate_categories if value.casefold() not in existing_keys]
        if not categories_to_add:
            return []

        timestamp = _timestamp_now()
        (
            self._sheets.spreadsheets()
            .values()
            .append(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{self._category_sheet_name}'!A2",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={
                    "values": [
                        [category_name, "", "TRUE", timestamp, timestamp, source]
                        for category_name in categories_to_add
                    ]
                },
            )
            .execute()
        )
        return categories_to_add

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
        for sheet_name, grouped_rows in self._group_receipt_rows_by_sheet_name(rows).items():
            self._ensure_sheet_with_header_sync(sheet_name=sheet_name, headers=RECEIPT_SHEET_HEADERS)
            (
                self._sheets.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self._spreadsheet_id,
                    range=f"'{sheet_name}'!A1",
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body={"values": grouped_rows},
                )
                .execute()
            )

    def _group_receipt_rows_by_sheet_name(self, rows: list[list[str]]) -> dict[str, list[list[str]]]:
        grouped_rows: dict[str, list[list[str]]] = {}
        for row in rows:
            sheet_name = self._resolve_receipt_sheet_name(row)
            grouped_rows.setdefault(sheet_name, []).append(row)
        return grouped_rows

    def _list_receipt_attachment_names_sync(self) -> set[str]:
        attachment_names: set[str] = set()
        for sheet_name in self._list_receipt_sheet_names_sync():
            response = (
                self._sheets.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self._spreadsheet_id,
                    range=f"'{sheet_name}'!{RECEIPT_ATTACHMENT_NAME_COLUMN}2:{RECEIPT_ATTACHMENT_NAME_COLUMN}",
                )
                .execute()
            )
            for row in response.get("values", []):
                normalized_attachment_name = _normalize_attachment_name(row[0] if row else "")
                if normalized_attachment_name:
                    attachment_names.add(normalized_attachment_name)
        return attachment_names

    def _receipt_attachment_exists_sync(self, attachment_name: str) -> bool:
        normalized_attachment_name = _normalize_attachment_name(attachment_name)
        if not normalized_attachment_name:
            return False
        return normalized_attachment_name in self._list_receipt_attachment_names_sync()

    def _list_receipt_sheet_names_sync(self) -> list[str]:
        spreadsheet = (
            self._sheets.spreadsheets()
            .get(spreadsheetId=self._spreadsheet_id, fields="sheets.properties.title")
            .execute()
        )
        return [
            title
            for title in (
                sheet.get("properties", {}).get("title", "")
                for sheet in spreadsheet.get("sheets", [])
            )
            if title and title != self._category_sheet_name
        ]

    def _resolve_receipt_sheet_name(self, row: list[str]) -> str:
        for column_index in (RECEIPT_PURCHASE_DATE_INDEX, RECEIPT_PROCESSED_AT_INDEX):
            year = _extract_year_from_cell(_get_row_value(row, column_index))
            if year is not None:
                return year

        configured_year = _extract_year_from_cell(self._sheet_name)
        if configured_year is not None:
            return configured_year
        return str(datetime.now(UTC).year)

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


def _timestamp_now() -> str:
    return datetime.now(UTC).isoformat()


def _get_row_value(row: list[str], index: int) -> str:
    if index >= len(row):
        return ""
    return row[index] or ""


def _extract_year_from_cell(value: str) -> str | None:
    match = YEAR_PATTERN.search(value)
    if match is None:
        return None
    return match.group(1)


def _normalize_attachment_name(value: str) -> str:
    return value.strip().casefold()
