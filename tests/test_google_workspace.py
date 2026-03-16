from app.formatters import RECEIPT_SHEET_HEADERS, ReceiptRecordContext, build_receipt_rows
from app.google_workspace import GoogleWorkspaceClient
from app.models import ReceiptExtraction, ReceiptLineItem


class _Execute:
    def __init__(self, payload: dict | None = None) -> None:
        self._payload = payload or {}

    def execute(self) -> dict:
        return self._payload


class _FakeSheetsValues:
    def __init__(self) -> None:
        self.append_calls: list[dict[str, object]] = []

    def append(
        self,
        *,
        spreadsheetId: str,
        range: str,
        valueInputOption: str,
        insertDataOption: str,
        body: dict[str, object],
    ) -> _Execute:
        self.append_calls.append(
            {
                "spreadsheetId": spreadsheetId,
                "range": range,
                "valueInputOption": valueInputOption,
                "insertDataOption": insertDataOption,
                "body": body,
            }
        )
        return _Execute()


class _FakeSheetsService:
    def __init__(self) -> None:
        self.values_service = _FakeSheetsValues()

    def spreadsheets(self) -> "_FakeSheetsService":
        return self

    def values(self) -> _FakeSheetsValues:
        return self.values_service


class _FakeDriveFiles:
    def __init__(self, *, existing_folders: dict[tuple[str, str], str] | None = None) -> None:
        self.existing_folders = dict(existing_folders or {})
        self.folder_create_calls: list[dict[str, object]] = []
        self.file_create_calls: list[dict[str, object]] = []
        self.list_calls: list[dict[str, object]] = []
        self._folder_counter = 0
        self._file_counter = 0

    def list(self, *, q: str, fields: str, pageSize: int) -> _Execute:
        self.list_calls.append({"q": q, "fields": fields, "pageSize": pageSize})
        parent_folder_id, folder_name = _parse_drive_folder_query(q)
        folder_id = self.existing_folders.get((parent_folder_id, folder_name))
        files = [{"id": folder_id, "name": folder_name}] if folder_id else []
        return _Execute({"files": files})

    def create(self, *, body: dict[str, object], fields: str, media_body=None) -> _Execute:
        del fields
        if body.get("mimeType") == "application/vnd.google-apps.folder":
            self._folder_counter += 1
            folder_id = f"folder-{self._folder_counter}"
            parent_folder_id = str(body["parents"][0])
            folder_name = str(body["name"])
            self.existing_folders[(parent_folder_id, folder_name)] = folder_id
            self.folder_create_calls.append(body)
            return _Execute({"id": folder_id})

        self._file_counter += 1
        file_id = f"file-{self._file_counter}"
        self.file_create_calls.append({"body": body, "media_body": media_body})
        return _Execute({"id": file_id, "webViewLink": f"https://drive.example/file/{file_id}"})


class _FakeDriveService:
    def __init__(self, *, existing_folders: dict[tuple[str, str], str] | None = None) -> None:
        self.files_service = _FakeDriveFiles(existing_folders=existing_folders)

    def files(self) -> _FakeDriveFiles:
        return self.files_service


def _parse_drive_folder_query(query: str) -> tuple[str, str]:
    parent_prefix = "'"
    parent_suffix = "' in parents"
    name_prefix = "name = '"
    name_suffix = "' and mimeType"
    parent_start = query.index(parent_prefix) + len(parent_prefix)
    parent_end = query.index(parent_suffix)
    name_start = query.index(name_prefix) + len(name_prefix)
    name_end = query.index(name_suffix)
    return query[parent_start:parent_end], query[name_start:name_end]


def _build_workspace_client(
    monkeypatch,
    *,
    sheet_name: str = "Receipts",
    existing_folders: dict[tuple[str, str], str] | None = None,
) -> tuple[GoogleWorkspaceClient, _FakeSheetsService, _FakeDriveService]:
    fake_sheets = _FakeSheetsService()
    fake_drive = _FakeDriveService(existing_folders=existing_folders)

    def _fake_build(service_name: str, version: str, credentials, cache_discovery: bool):
        del version, credentials, cache_discovery
        if service_name == "sheets":
            return fake_sheets
        return fake_drive

    monkeypatch.setattr("app.google_workspace.build", _fake_build)

    client = GoogleWorkspaceClient(
        credentials=object(),
        drive_folder_id="drive-folder-1",
        spreadsheet_id="spreadsheet-1",
        sheet_name=sheet_name,
    )
    return client, fake_sheets, fake_drive


def _build_rows(*, processed_at: str, purchase_date: str | None) -> list[list[str]]:
    return build_receipt_rows(
        context=ReceiptRecordContext(
            processed_at=processed_at,
            channel_name="cli",
            author_tag="tester",
            attachment_name="receipt.jpg",
            attachment_url="D:/Prj/harina-v3/tests/fixtures/receipt.jpg",
        ),
        extraction=ReceiptExtraction(
            merchant_name="Cafe Harina",
            purchase_date=purchase_date,
            line_items=[ReceiptLineItem(name="Tea", quantity=1, total_price=120)],
        ),
        drive_file_id="drive-file-1",
        drive_file_url="https://drive.example/file/drive-file-1",
    )


def test_append_receipt_rows_uses_purchase_year_sheet(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    ensured_sheets: list[tuple[str, list[str]]] = []

    def _record_header(*, sheet_name: str, headers: list[str]) -> None:
        ensured_sheets.append((sheet_name, headers))

    monkeypatch.setattr(client, "_ensure_sheet_with_header_sync", _record_header)

    rows = _build_rows(processed_at="2026-03-15T09:30:00+00:00", purchase_date="2025-12-31")
    client._append_receipt_rows_sync(rows)

    assert ensured_sheets == [("2025", RECEIPT_SHEET_HEADERS)]
    assert fake_sheets.values_service.append_calls == [
        {
            "spreadsheetId": "spreadsheet-1",
            "range": "'2025'!A1",
            "valueInputOption": "USER_ENTERED",
            "insertDataOption": "INSERT_ROWS",
            "body": {"values": rows},
        }
    ]


def test_append_receipt_rows_falls_back_to_processed_year_when_purchase_date_missing(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    ensured_sheets: list[str] = []

    def _record_header(*, sheet_name: str, headers: list[str]) -> None:
        del headers
        ensured_sheets.append(sheet_name)

    monkeypatch.setattr(client, "_ensure_sheet_with_header_sync", _record_header)

    rows = _build_rows(processed_at="2024-01-02T03:04:05+00:00", purchase_date=None)
    client._append_receipt_rows_sync(rows)

    assert ensured_sheets == ["2024"]
    assert fake_sheets.values_service.append_calls[0]["range"] == "'2024'!A1"


def test_append_receipt_rows_groups_mixed_year_batches(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    ensured_sheets: list[str] = []

    def _record_header(*, sheet_name: str, headers: list[str]) -> None:
        del headers
        ensured_sheets.append(sheet_name)

    monkeypatch.setattr(client, "_ensure_sheet_with_header_sync", _record_header)

    rows_2025 = _build_rows(processed_at="2026-03-15T09:30:00+00:00", purchase_date="2025-05-01")
    rows_2026 = _build_rows(processed_at="2026-03-15T09:30:00+00:00", purchase_date="2026-06-01")

    client._append_receipt_rows_sync(rows_2025 + rows_2026)

    assert ensured_sheets == ["2025", "2026"]
    assert [call["range"] for call in fake_sheets.values_service.append_calls] == ["'2025'!A1", "'2026'!A1"]
    assert fake_sheets.values_service.append_calls[0]["body"] == {"values": rows_2025}
    assert fake_sheets.values_service.append_calls[1]["body"] == {"values": rows_2026}


def test_resolve_receipt_sheet_name_uses_configured_year_when_row_dates_are_missing(monkeypatch) -> None:
    client, _fake_sheets, _fake_drive = _build_workspace_client(monkeypatch, sheet_name="2031")

    assert client._resolve_receipt_sheet_name([""] * len(RECEIPT_SHEET_HEADERS)) == "2031"


def test_upload_receipt_image_creates_year_and_month_folders(monkeypatch) -> None:
    client, _fake_sheets, fake_drive = _build_workspace_client(monkeypatch)

    uploaded = client._upload_receipt_image_sync(
        "receipt.jpg",
        "image/jpeg",
        b"image-bytes",
        "2026-03-11",
    )

    assert fake_drive.files_service.folder_create_calls == [
        {
            "name": "2026",
            "parents": ["drive-folder-1"],
            "mimeType": "application/vnd.google-apps.folder",
        },
        {
            "name": "03",
            "parents": ["folder-1"],
            "mimeType": "application/vnd.google-apps.folder",
        },
    ]
    assert fake_drive.files_service.file_create_calls[0]["body"] == {
        "name": "receipt.jpg",
        "parents": ["folder-2"],
    }
    assert uploaded.file_id == "file-1"
    assert uploaded.web_view_link == "https://drive.example/file/file-1"


def test_upload_receipt_image_reuses_existing_year_and_month_folders(monkeypatch) -> None:
    client, _fake_sheets, fake_drive = _build_workspace_client(
        monkeypatch,
        existing_folders={
            ("drive-folder-1", "2026"): "year-2026",
            ("year-2026", "03"): "month-03",
        },
    )

    uploaded = client._upload_receipt_image_sync(
        "receipt.jpg",
        "image/jpeg",
        b"image-bytes",
        "2026/03/11",
    )

    assert fake_drive.files_service.folder_create_calls == []
    assert fake_drive.files_service.file_create_calls[0]["body"] == {
        "name": "receipt.jpg",
        "parents": ["month-03"],
    }
    assert uploaded.file_id == "file-1"
