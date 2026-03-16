import asyncio

from app.drive_watcher import DriveReceiptWatcher
from app.formatters import ReceiptRecordContext
from app.google_workspace import DriveImageFile, GoogleWorkspaceClient
from app.models import ReceiptExtraction, ReceiptLineItem
from app.processor import ReceiptProcessor
from app.team_intake import DriveWatchRoute


class _Execute:
    def __init__(self, payload: dict | None = None) -> None:
        self._payload = payload or {}

    def execute(self) -> dict:
        return self._payload


class _FakeSheetsValues:
    def __init__(self, values_by_range: dict[str, list[list[str]]]) -> None:
        self.values_by_range = values_by_range

    def get(self, *, spreadsheetId: str, range: str) -> _Execute:
        del spreadsheetId
        return _Execute({"values": self.values_by_range.get(range, [])})


class _FakeSheetsService:
    def __init__(self, *, sheet_names: list[str], values_by_range: dict[str, list[list[str]]]) -> None:
        self.sheet_names = sheet_names
        self.values_service = _FakeSheetsValues(values_by_range)

    def spreadsheets(self) -> "_FakeSheetsService":
        return self

    def get(self, *, spreadsheetId: str, fields: str) -> _Execute:
        del spreadsheetId, fields
        return _Execute({"sheets": [{"properties": {"title": sheet_name}} for sheet_name in self.sheet_names]})

    def values(self) -> _FakeSheetsValues:
        return self.values_service


def _build_workspace_client(
    monkeypatch,
    *,
    sheet_names: list[str],
    values_by_range: dict[str, list[list[str]]],
) -> GoogleWorkspaceClient:
    fake_sheets = _FakeSheetsService(sheet_names=sheet_names, values_by_range=values_by_range)

    def _fake_build(service_name: str, version: str, credentials, cache_discovery: bool):
        del version, credentials, cache_discovery
        if service_name == "sheets":
            return fake_sheets
        return object()

    monkeypatch.setattr("app.google_workspace.build", _fake_build)
    return GoogleWorkspaceClient(
        credentials=object(),
        drive_folder_id="drive-folder",
        spreadsheet_id="spreadsheet-1",
        sheet_name="Receipts",
        category_sheet_name="Categories",
    )


def test_list_receipt_attachment_names_reads_every_receipt_sheet(monkeypatch) -> None:
    client = _build_workspace_client(
        monkeypatch,
        sheet_names=["Categories", "2025", "2026"],
        values_by_range={
            "'2025'!K2:K": [["alpha.jpg"], ["beta.jpg"]],
            "'2026'!K2:K": [["Gamma.JPG"], ["  beta.jpg  "]],
        },
    )

    result = asyncio.run(client.list_receipt_attachment_names())

    assert result == {"alpha.jpg", "beta.jpg", "gamma.jpg"}


def test_receipt_attachment_exists_normalizes_case_and_whitespace(monkeypatch) -> None:
    client = _build_workspace_client(
        monkeypatch,
        sheet_names=["Categories", "2026"],
        values_by_range={
            "'2026'!K2:K": [["Receipt-01.JPG"]],
        },
    )

    assert asyncio.run(client.receipt_attachment_exists(attachment_name="  receipt-01.jpg ")) is True
    assert asyncio.run(client.receipt_attachment_exists(attachment_name="receipt-02.jpg")) is False


class _FakeGemini:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        filename: str,
        category_options: list[str] | None = None,
    ) -> ReceiptExtraction:
        del category_options
        assert image_bytes == b"image-bytes"
        assert mime_type == "image/jpeg"
        self.calls.append(filename)
        return ReceiptExtraction(
            merchant_name="Cafe Harina",
            purchase_date="2026-03-16",
            currency="JPY",
            total=900,
            line_items=[ReceiptLineItem(name="Tea", category="food", quantity=1, total_price=900)],
        )


class _FakeProcessorWorkspace:
    def __init__(self, *, existing_names: set[str] | None = None) -> None:
        self.existing_names = {value.casefold() for value in (existing_names or set())}
        self.categories = ["food"]
        self.upload_calls: list[str] = []
        self.rows: list[list[str]] = []
        self.spreadsheet_url = "https://docs.google.com/spreadsheets/d/test-sheet/edit"

    async def receipt_attachment_exists(self, *, attachment_name: str) -> bool:
        return attachment_name.casefold() in self.existing_names

    async def list_receipt_categories(self) -> list[str]:
        return self.categories

    async def append_receipt_categories(self, categories: list[str], *, source: str = "gemini") -> list[str]:
        del categories, source
        return []

    async def upload_receipt_image(
        self,
        *,
        file_name: str,
        mime_type: str,
        image_bytes: bytes,
        purchase_date: str | None = None,
    ):
        del purchase_date
        del mime_type, image_bytes
        self.upload_calls.append(file_name)

        class _DriveFile:
            file_id = "drive-1"
            web_view_link = "https://drive.example/file/drive-1"

        return _DriveFile()

    async def append_receipt_rows(self, rows: list[list[str]]) -> None:
        self.rows.extend(rows)


def test_receipt_processor_skips_existing_attachment_name() -> None:
    workspace = _FakeProcessorWorkspace(existing_names={"receipt.jpg"})
    gemini = _FakeGemini()
    processor = ReceiptProcessor(gemini=gemini, google_workspace=workspace)

    result = asyncio.run(
        processor.process_receipt(
            context=ReceiptRecordContext(
                channel_name="cli",
                author_tag="tester",
                attachment_name="receipt.jpg",
                attachment_url="D:/tmp/receipt.jpg",
            ),
            filename="receipt.jpg",
            mime_type="image/jpeg",
            image_bytes=b"image-bytes",
            write_to_google=True,
        )
    )

    assert result.skipped_existing is True
    assert result.rows == []
    assert gemini.calls == []
    assert workspace.upload_calls == []


def test_receipt_processor_rescans_existing_attachment_name_when_requested() -> None:
    workspace = _FakeProcessorWorkspace(existing_names={"receipt.jpg"})
    gemini = _FakeGemini()
    processor = ReceiptProcessor(gemini=gemini, google_workspace=workspace)

    result = asyncio.run(
        processor.process_receipt(
            context=ReceiptRecordContext(
                channel_name="cli",
                author_tag="tester",
                attachment_name="receipt.jpg",
                attachment_url="D:/tmp/receipt.jpg",
            ),
            filename="receipt.jpg",
            mime_type="image/jpeg",
            image_bytes=b"image-bytes",
            write_to_google=True,
            rescan_existing=True,
        )
    )

    assert result.skipped_existing is False
    assert gemini.calls == ["receipt.jpg"]
    assert len(workspace.upload_calls) == 1
    assert len(workspace.rows) == 1


class _FakeDriveWorkspace:
    def __init__(self, *, existing_names: set[str] | None = None) -> None:
        self.existing_names = {value.casefold() for value in (existing_names or set())}
        self.categories = ["food"]
        self.rows: list[list[str]] = []
        self.moves: list[tuple[str, str]] = []
        self.storage_folder_requests: list[tuple[str, str | None]] = []

    async def ensure_receipt_sheet(self) -> None:
        return None

    async def list_receipt_attachment_names(self) -> set[str]:
        return set(self.existing_names)

    async def list_receipt_categories(self) -> list[str]:
        return self.categories

    async def append_receipt_categories(self, categories: list[str], *, source: str = "gemini") -> list[str]:
        del categories, source
        return []

    async def list_image_files(self, *, folder_id: str) -> list[DriveImageFile]:
        assert folder_id == "source-folder"
        return [
            DriveImageFile(
                file_id="drive-file-1",
                name="receipt.jpg",
                mime_type="image/jpeg",
                created_time="2026-03-16T00:00:00Z",
                parents=["source-folder"],
                web_view_link="https://drive.example/file/drive-file-1",
            )
        ]

    async def download_file(self, *, file_id: str) -> bytes:
        assert file_id == "drive-file-1"
        return b"image-bytes"

    async def append_receipt_rows(self, rows: list[list[str]]) -> None:
        self.rows.extend(rows)

    async def ensure_receipt_storage_folder(self, *, root_folder_id: str | None = None, date_hint: str | None = None) -> str:
        self.storage_folder_requests.append((root_folder_id or "", date_hint))
        return f"{root_folder_id}/2026/03"

    async def move_file(self, *, file_id: str, destination_folder_id: str) -> None:
        self.moves.append((file_id, destination_folder_id))


class _FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def send_receipt_notification(
        self,
        *,
        route: DriveWatchRoute,
        file_name: str,
        image_bytes: bytes,
        extraction: ReceiptExtraction,
        drive_file_url: str | None,
    ) -> None:
        del route, image_bytes, extraction, drive_file_url
        self.calls.append(file_name)


def _build_route() -> DriveWatchRoute:
    return DriveWatchRoute(
        key="alice",
        label="Alice",
        discord_channel_id=123,
        source_folder_id="source-folder",
        processed_folder_id="processed-folder",
    )


def test_drive_watcher_skips_existing_attachment_name_and_moves_file() -> None:
    workspace = _FakeDriveWorkspace(existing_names={"receipt.jpg"})
    notifier = _FakeNotifier()
    gemini = _FakeGemini()
    watcher = DriveReceiptWatcher(
        gemini=gemini,
        google_workspace=workspace,
        notifier=notifier,
        routes=[_build_route()],
    )

    summary = asyncio.run(watcher.scan_once())

    assert summary.scanned == 1
    assert summary.processed == 0
    assert summary.skipped == 1
    assert summary.failed == 0
    assert summary.notified == 0
    assert summary.moved == 1
    assert gemini.calls == []
    assert notifier.calls == []
    assert workspace.rows == []
    assert workspace.storage_folder_requests == [("processed-folder", "2026-03-16T00:00:00Z")]
    assert workspace.moves == [("drive-file-1", "processed-folder/2026/03")]


def test_drive_watcher_rescans_existing_attachment_name_when_requested() -> None:
    workspace = _FakeDriveWorkspace(existing_names={"receipt.jpg"})
    notifier = _FakeNotifier()
    gemini = _FakeGemini()
    watcher = DriveReceiptWatcher(
        gemini=gemini,
        google_workspace=workspace,
        notifier=notifier,
        routes=[_build_route()],
        rescan_existing=True,
    )

    summary = asyncio.run(watcher.scan_once())

    assert summary.scanned == 1
    assert summary.processed == 1
    assert summary.skipped == 0
    assert summary.failed == 0
    assert summary.notified == 1
    assert summary.moved == 1
    assert gemini.calls == ["receipt.jpg"]
    assert notifier.calls == ["receipt.jpg"]
    assert len(workspace.rows) == 1
    assert workspace.storage_folder_requests == [("processed-folder", "2026-03-16")]
    assert workspace.moves == [("drive-file-1", "processed-folder/2026/03")]
