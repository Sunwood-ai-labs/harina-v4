import asyncio
from types import SimpleNamespace

from app.drive_watcher import DriveReceiptWatcher, DriveWatchCycleSummaryState, DriveWatchScanSummary, DriveWatcherClient
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
        self.storage_folder_requests: list[tuple[str, str | None]] = []

    async def ensure_receipt_sheet(self) -> None:
        return None

    async def list_receipt_categories(self) -> list[str]:
        return self.categories

    async def list_receipt_attachment_names(self) -> set[str]:
        return set()

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

    async def ensure_receipt_storage_folder(self, *, root_folder_id: str | None = None, date_hint: str | None = None) -> str:
        self.storage_folder_requests.append((root_folder_id or "", date_hint))
        return f"{root_folder_id}/2026/03"

    async def move_file(self, *, file_id: str, destination_folder_id: str) -> None:
        self.moves.append((file_id, destination_folder_id))


class _FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.progress_calls: list[dict[str, object]] = []

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

    async def send_system_progress(
        self,
        *,
        route: DriveWatchRoute,
        status: str,
        file_name: str,
        summary,
        remaining_in_route: int,
        error_message: str | None = None,
    ) -> None:
        self.progress_calls.append(
            {
                "route": route,
                "status": status,
                "file_name": file_name,
                "summary": summary.as_dict(),
                "remaining_in_route": remaining_in_route,
                "error_message": error_message,
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
    assert summary.skipped == 0
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
    assert workspace.storage_folder_requests == [("processed-folder", "2026-03-11")]
    assert workspace.moves == [("drive-file-123", "processed-folder/2026/03")]
    assert workspace.added_categories == [(["野菜", "新カテゴリ"], "gemini")]
    assert gemini.calls == [["野菜", "飲料"]]
    assert notifier.calls[0]["route"].key == "alice"
    assert notifier.calls[0]["file_name"] == "receipt.jpg"
    assert notifier.calls[0]["image_bytes"] == b"drive-image"
    assert notifier.calls[0]["extraction"].merchant_name == "Cafe Harina"
    assert notifier.progress_calls == [
        {
            "route": DriveWatchRoute(
                key="alice",
                label="Alice",
                discord_channel_id=123,
                source_folder_id="source-folder",
                processed_folder_id="processed-folder",
            ),
            "status": "processed",
            "file_name": "receipt.jpg",
            "summary": {
                "scanned": 1,
                "processed": 1,
                "skipped": 0,
                "failed": 0,
                "moved": 1,
                "notified": 1,
            },
            "remaining_in_route": 0,
            "error_message": None,
        }
    ]


def test_drive_watcher_continues_after_file_failure() -> None:
    class _BrokenWorkspace(_FakeWorkspace):
        async def download_file(self, *, file_id: str) -> bytes:
            raise RuntimeError("download failed")

    notifier = _FakeNotifier()
    watcher = DriveReceiptWatcher(
        gemini=_FakeGemini(),
        google_workspace=_BrokenWorkspace(),
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
    assert summary.processed == 0
    assert summary.failed == 1
    assert summary.notified == 0
    assert summary.moved == 0
    assert notifier.progress_calls[0]["status"] == "failed"
    assert notifier.progress_calls[0]["file_name"] == "receipt.jpg"
    assert notifier.progress_calls[0]["remaining_in_route"] == 0
    assert notifier.progress_calls[0]["error_message"] == "download failed"


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
    assert summary.skipped == 0
    assert summary.failed == 1
    assert summary.notified == 0
    assert summary.moved == 0
    assert workspace.rows == []
    assert workspace.moves == []


def test_drive_watcher_sends_progress_for_skipped_duplicates() -> None:
    notifier = _FakeNotifier()
    watcher = DriveReceiptWatcher(
        gemini=_FakeGemini(),
        google_workspace=_FakeWorkspace(),
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
        rescan_existing=False,
    )

    async def fake_names() -> set[str]:
        return {"receipt.jpg"}

    watcher.google_workspace.list_receipt_attachment_names = fake_names  # type: ignore[method-assign]

    summary = asyncio.run(watcher.scan_once())

    assert summary.processed == 0
    assert summary.skipped == 1
    assert summary.moved == 1
    assert notifier.progress_calls[0]["status"] == "skipped"
    assert notifier.progress_calls[0]["file_name"] == "receipt.jpg"


def test_drive_watcher_skips_noop_cycle_summary_notifications() -> None:
    sent_embeds = []
    client = DriveWatcherClient.__new__(DriveWatcherClient)
    client.settings = SimpleNamespace(discord_system_log_channel_id=999)
    client._cycle_summary_state = DriveWatchCycleSummaryState()

    async def fake_build_backlog_snapshot() -> tuple[int, list[str]]:
        return 0, ["Alice: 0"]

    async def fake_send_system_log_embed(embed) -> None:
        sent_embeds.append(embed)

    client._build_backlog_snapshot = fake_build_backlog_snapshot  # type: ignore[method-assign]
    client._send_system_log_embed = fake_send_system_log_embed  # type: ignore[method-assign]
    client._cycle_summary_state.remember(
        summary=DriveWatchScanSummary(),
        backlog_total=0,
        backlog_lines=["Alice: 0"],
    )

    asyncio.run(DriveWatcherClient.send_system_cycle_summary(client, DriveWatchScanSummary()))

    assert sent_embeds == []


def test_drive_watcher_sends_cycle_summary_when_activity_exists() -> None:
    sent_embeds = []
    client = DriveWatcherClient.__new__(DriveWatcherClient)
    client.settings = SimpleNamespace(discord_system_log_channel_id=999)
    client._cycle_summary_state = DriveWatchCycleSummaryState()

    async def fake_build_backlog_snapshot() -> tuple[int, list[str]]:
        return 0, ["Alice: 0"]

    async def fake_send_system_log_embed(embed) -> None:
        sent_embeds.append(embed)

    client._build_backlog_snapshot = fake_build_backlog_snapshot  # type: ignore[method-assign]
    client._send_system_log_embed = fake_send_system_log_embed  # type: ignore[method-assign]

    asyncio.run(
        DriveWatcherClient.send_system_cycle_summary(
            client,
            DriveWatchScanSummary(processed=1, notified=1, moved=1),
        )
    )

    assert len(sent_embeds) == 1
    assert sent_embeds[0].title == "HARINA Scan Summary"


def test_drive_watcher_sends_cycle_summary_when_backlog_changes() -> None:
    sent_embeds = []
    client = DriveWatcherClient.__new__(DriveWatcherClient)
    client.settings = SimpleNamespace(discord_system_log_channel_id=999)
    client._cycle_summary_state = DriveWatchCycleSummaryState()

    async def fake_send_system_log_embed(embed) -> None:
        sent_embeds.append(embed)

    client._send_system_log_embed = fake_send_system_log_embed  # type: ignore[method-assign]
    client._cycle_summary_state.remember(
        summary=DriveWatchScanSummary(),
        backlog_total=0,
        backlog_lines=["Alice: 0"],
    )

    async def fake_build_backlog_snapshot() -> tuple[int, list[str]]:
        return 1, ["Alice: 1"]

    client._build_backlog_snapshot = fake_build_backlog_snapshot  # type: ignore[method-assign]

    asyncio.run(DriveWatcherClient.send_system_cycle_summary(client, DriveWatchScanSummary()))

    assert len(sent_embeds) == 1
    assert sent_embeds[0].title == "HARINA Scan Summary"
