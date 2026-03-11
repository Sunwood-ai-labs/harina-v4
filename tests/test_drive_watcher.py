import asyncio

from app.drive_watcher import DriveReceiptWatcher
from app.google_workspace import DriveImageFile
from app.models import ReceiptExtraction


class _FakeGemini:
    async def extract(self, *, image_bytes: bytes, mime_type: str, filename: str) -> ReceiptExtraction:
        assert image_bytes == b"drive-image"
        assert mime_type == "image/jpeg"
        assert filename == "receipt.jpg"
        return ReceiptExtraction(
            merchant_name="Cafe Harina",
            purchase_date="2026-03-11",
            currency="JPY",
            total=1100,
            confidence=0.97,
        )


class _FakeWorkspace:
    def __init__(self) -> None:
        self.rows: list[list[str]] = []
        self.moves: list[tuple[str, str]] = []

    async def ensure_receipt_sheet(self) -> None:
        return None

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

    async def append_receipt_row(self, row: list[str]) -> None:
        self.rows.append(row)

    async def move_file(self, *, file_id: str, destination_folder_id: str) -> None:
        self.moves.append((file_id, destination_folder_id))


class _FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_receipt_notification(
        self,
        *,
        file_name: str,
        image_bytes: bytes,
        summary: str,
        drive_file_url: str | None,
    ) -> None:
        self.calls.append(
            {
                "file_name": file_name,
                "image_bytes": image_bytes,
                "summary": summary,
                "drive_file_url": drive_file_url,
            }
        )


def test_drive_watcher_processes_files_and_moves_them() -> None:
    workspace = _FakeWorkspace()
    notifier = _FakeNotifier()
    watcher = DriveReceiptWatcher(
        gemini=_FakeGemini(),
        google_workspace=workspace,
        notifier=notifier,
        source_folder_id="source-folder",
        processed_folder_id="processed-folder",
    )

    summary = asyncio.run(watcher.scan_once())

    assert summary.scanned == 1
    assert summary.processed == 1
    assert summary.failed == 0
    assert summary.notified == 1
    assert summary.moved == 1
    assert workspace.rows[0][4] == "google-drive-watch"
    assert workspace.rows[0][9] == "drive-file-123"
    assert workspace.rows[0][12] == "drive-file-123"
    assert workspace.moves == [("drive-file-123", "processed-folder")]
    assert notifier.calls[0]["file_name"] == "receipt.jpg"
    assert notifier.calls[0]["image_bytes"] == b"drive-image"
    assert "Cafe Harina" in str(notifier.calls[0]["summary"])


def test_drive_watcher_continues_after_file_failure() -> None:
    class _BrokenWorkspace(_FakeWorkspace):
        async def download_file(self, *, file_id: str) -> bytes:
            raise RuntimeError("download failed")

    watcher = DriveReceiptWatcher(
        gemini=_FakeGemini(),
        google_workspace=_BrokenWorkspace(),
        notifier=_FakeNotifier(),
        source_folder_id="source-folder",
        processed_folder_id="processed-folder",
    )

    summary = asyncio.run(watcher.scan_once())

    assert summary.scanned == 1
    assert summary.processed == 0
    assert summary.failed == 1
    assert summary.notified == 0
    assert summary.moved == 0
