import asyncio

from app.drive_watcher import DriveReceiptWatcher
from app.google_workspace import DriveImageFile
from app.models import ReceiptExtraction, ReceiptLineItem
from app.team_intake import DriveWatchRoute


class _FakeGemini:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        filename: str,
        category_options: list[str] | None = None,
    ) -> ReceiptExtraction:
        assert image_bytes == b"drive-image"
        assert mime_type == "image/jpeg"
        assert filename == "receipt.jpg"
        self.calls.append(list(category_options or []))
        return ReceiptExtraction(
            merchant_name="Cafe Harina",
            purchase_date="2026-03-11",
            currency="JPY",
            total=1100,
            confidence=0.97,
            line_items=[
                ReceiptLineItem(name="Cabbage", category="野菜", quantity=1, total_price=198),
                ReceiptLineItem(name="Juice", category="新カテゴリ", quantity=2, unit_price=150, total_price=300),
            ],
        )


class _FakeWorkspace:
    def __init__(self) -> None:
        self.rows: list[list[str]] = []
        self.moves: list[tuple[str, str]] = []
        self.categories = ["野菜", "飲料"]
        self.added_categories: list[tuple[list[str], str]] = []

    async def ensure_receipt_sheet(self) -> None:
        return None

    async def list_receipt_categories(self) -> list[str]:
        return self.categories

    async def append_receipt_categories(self, categories: list[str], *, source: str = "gemini") -> list[str]:
        self.added_categories.append((categories, source))
        return ["新カテゴリ"]

    async def list_image_files(self, *, folder_id: str) -> list[DriveImageFile]:
        assert folder_id == "source-folder"
        return [
            DriveImageFile(
                file_id="drive-file-123",
                name="receipt.jpg",
                mime_type="image/jpeg",
                created_time="2026-03-11T00:00:00Z",
                parents=["source-folder"],
                web_view_link="https://drive.example/file/drive-file-123",
            )
        ]

    async def download_file(self, *, file_id: str) -> bytes:
        assert file_id == "drive-file-123"
        return b"drive-image"

    async def append_receipt_rows(self, rows: list[list[str]]) -> None:
        self.rows.extend(rows)

    async def move_file(self, *, file_id: str, destination_folder_id: str) -> None:
        self.moves.append((file_id, destination_folder_id))


class _FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_receipt_notification(
        self,
        *,
        route: DriveWatchRoute,
        file_name: str,
        image_bytes: bytes,
        extraction: ReceiptExtraction,
        drive_file_url: str | None,
    ) -> None:
        self.calls.append(
            {
                "route": route,
                "file_name": file_name,
                "image_bytes": image_bytes,
                "extraction": extraction,
                "drive_file_url": drive_file_url,
            }
        )


def test_drive_watcher_processes_files_and_moves_them() -> None:
    workspace = _FakeWorkspace()
    notifier = _FakeNotifier()
    gemini = _FakeGemini()
    watcher = DriveReceiptWatcher(
        gemini=gemini,
        google_workspace=workspace,
        notifier=notifier,
        routes=[
            DriveWatchRoute(
                key="alice",
                label="Alice",
                discord_channel_id=123,
                source_folder_id="source-folder",
                processed_folder_id="processed-folder",
            )
        ],
    )

    summary = asyncio.run(watcher.scan_once())

    assert summary.scanned == 1
    assert summary.processed == 1
    assert summary.failed == 0
    assert summary.notified == 1
    assert summary.moved == 1
    assert len(workspace.rows) == 2
    assert workspace.rows[0][4] == "google-drive:alice"
    assert workspace.rows[0][9] == "drive-file-123"
    assert workspace.rows[0][12] == "drive-file-123"
    assert workspace.rows[0][31] == "Cabbage"
    assert workspace.rows[0][32] == "野菜"
    assert workspace.rows[1][31] == "Juice"
    assert workspace.rows[1][32] == "新カテゴリ"
    assert workspace.moves == [("drive-file-123", "processed-folder")]
    assert workspace.added_categories == [(["野菜", "新カテゴリ"], "gemini")]
    assert gemini.calls == [["野菜", "飲料"]]
    assert notifier.calls[0]["route"].key == "alice"
    assert notifier.calls[0]["file_name"] == "receipt.jpg"
    assert notifier.calls[0]["image_bytes"] == b"drive-image"
    assert notifier.calls[0]["extraction"].merchant_name == "Cafe Harina"


def test_drive_watcher_continues_after_file_failure() -> None:
    class _BrokenWorkspace(_FakeWorkspace):
        async def download_file(self, *, file_id: str) -> bytes:
            raise RuntimeError("download failed")

    watcher = DriveReceiptWatcher(
        gemini=_FakeGemini(),
        google_workspace=_BrokenWorkspace(),
        notifier=_FakeNotifier(),
        routes=[
            DriveWatchRoute(
                key="alice",
                label="Alice",
                discord_channel_id=123,
                source_folder_id="source-folder",
                processed_folder_id="processed-folder",
            )
        ],
    )

    summary = asyncio.run(watcher.scan_once())

    assert summary.scanned == 1
    assert summary.processed == 0
    assert summary.failed == 1
    assert summary.notified == 0
    assert summary.moved == 0


def test_drive_watcher_does_not_move_file_when_notification_fails_midway() -> None:
    class _BrokenNotifier(_FakeNotifier):
        async def send_receipt_notification(
            self,
            *,
            route: DriveWatchRoute,
            file_name: str,
            image_bytes: bytes,
            extraction: ReceiptExtraction,
            drive_file_url: str | None,
        ) -> None:
            raise RuntimeError("discord send failed")

    workspace = _FakeWorkspace()
    watcher = DriveReceiptWatcher(
        gemini=_FakeGemini(),
        google_workspace=workspace,
        notifier=_BrokenNotifier(),
        routes=[
            DriveWatchRoute(
                key="alice",
                label="Alice",
                discord_channel_id=123,
                source_folder_id="source-folder",
                processed_folder_id="processed-folder",
            )
        ],
    )

    summary = asyncio.run(watcher.scan_once())

    assert summary.scanned == 1
    assert summary.processed == 0
    assert summary.failed == 1
    assert summary.notified == 0
    assert summary.moved == 0
    assert len(workspace.rows) == 2
    assert workspace.moves == []
