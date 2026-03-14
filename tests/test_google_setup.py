from pathlib import Path

from app.google_setup import (
    GoogleResourceBootstrapper,
    build_drive_watch_env_updates,
    build_google_env_updates,
    build_team_drive_watch_env_updates,
    upsert_env_file,
)
from app.team_intake import DriveWatchRoute, build_team_member_spec


class _Execute:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def execute(self) -> dict:
        return self._payload


class _FakeDriveFiles:
    def __init__(self, *, folder_files: list[dict], spreadsheet_files: list[dict]) -> None:
        self.folder_files = folder_files
        self.spreadsheet_files = spreadsheet_files
        self.created: list[dict] = []
        self.list_queries: list[str] = []
        self._folder_counter = 0
        self._sheet_counter = 0

    def list(self, *, q: str, fields: str, pageSize: int) -> _Execute:
        del fields, pageSize
        self.list_queries.append(q)
        if "application/vnd.google-apps.folder" in q:
            return _Execute({"files": self.folder_files})
        return _Execute({"files": self.spreadsheet_files})

    def create(self, *, body: dict, fields: str) -> _Execute:
        del fields
        self.created.append(body)
        if body["mimeType"] == "application/vnd.google-apps.folder":
            self._folder_counter += 1
            created_id = f"folder-{self._folder_counter}"
        else:
            self._sheet_counter += 1
            created_id = f"sheet-{self._sheet_counter}"
        return _Execute({"id": created_id, "name": body["name"], "webViewLink": f"https://example.com/{created_id}"})


class _FakeDrivePermissions:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def create(self, *, fileId: str, body: dict, fields: str, sendNotificationEmail: bool) -> _Execute:
        del fields, sendNotificationEmail
        self.calls.append((fileId, body["emailAddress"]))
        return _Execute({"id": f"perm-{fileId}"})


class _FakeDriveService:
    def __init__(self, *, folder_files: list[dict], spreadsheet_files: list[dict]) -> None:
        self.files_service = _FakeDriveFiles(folder_files=folder_files, spreadsheet_files=spreadsheet_files)
        self.permissions_service = _FakeDrivePermissions()

    def files(self) -> _FakeDriveFiles:
        return self.files_service

    def permissions(self) -> _FakeDrivePermissions:
        return self.permissions_service


def test_bootstrap_creates_resources_and_shares(monkeypatch) -> None:
    drive = _FakeDriveService(folder_files=[], spreadsheet_files=[])
    ensured: list[tuple[str, str, str, str]] = []

    monkeypatch.setattr(
        "app.google_setup.build",
        lambda service_name, version, credentials, cache_discovery: drive,
    )

    class _FakeWorkspaceClient:
        def __init__(
            self,
            *,
            credentials,
            drive_folder_id: str,
            spreadsheet_id: str,
            sheet_name: str,
            category_sheet_name: str,
        ) -> None:
            del credentials
            ensured.append((drive_folder_id, spreadsheet_id, sheet_name, category_sheet_name))

        def _ensure_receipt_sheet_sync(self) -> None:
            return None

    monkeypatch.setattr("app.google_setup.GoogleWorkspaceClient", _FakeWorkspaceClient)

    result = GoogleResourceBootstrapper(credentials=object()).bootstrap(
        folder_name="Harina V4 Receipts",
        spreadsheet_title="Harina V4 Receipts",
        sheet_name="Receipts",
        share_with_email="owner@example.com",
    )

    assert result.folder_id == "folder-1"
    assert result.spreadsheet_id == "sheet-1"
    assert result.shared_with_email == "owner@example.com"
    assert drive.files_service.created == [
        {"name": "Harina V4 Receipts", "mimeType": "application/vnd.google-apps.folder"},
        {
            "name": "Harina V4 Receipts",
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }
    ]
    assert drive.permissions_service.calls == [("folder-1", "owner@example.com"), ("sheet-1", "owner@example.com")]
    assert ensured == [("folder-1", "sheet-1", "Receipts", "Categories")]


def test_bootstrap_drive_watch_creates_parented_folders_and_shares(monkeypatch) -> None:
    drive = _FakeDriveService(folder_files=[], spreadsheet_files=[])

    monkeypatch.setattr(
        "app.google_setup.build",
        lambda service_name, version, credentials, cache_discovery: drive,
    )

    result = GoogleResourceBootstrapper(credentials=object()).bootstrap_drive_watch(
        source_folder_name="Inbox",
        processed_folder_name="Processed",
        parent_folder_id="parent-123",
        share_with_email="owner@example.com",
    )

    assert result.source_folder_id == "folder-1"
    assert result.processed_folder_id == "folder-2"
    assert result.parent_folder_id == "parent-123"
    assert drive.files_service.created == [
        {
            "name": "Inbox",
            "mimeType": "application/vnd.google-apps.folder",
            "parents": ["parent-123"],
        },
        {
            "name": "Processed",
            "mimeType": "application/vnd.google-apps.folder",
            "parents": ["parent-123"],
        },
    ]
    assert drive.permissions_service.calls == [("folder-1", "owner@example.com"), ("folder-2", "owner@example.com")]
    assert "'parent-123' in parents" in drive.files_service.list_queries[0]


def test_upsert_env_file_replaces_existing_keys(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DISCORD_TOKEN=test-token\nGOOGLE_SERVICE_ACCOUNT_KEY_FILE=\nGOOGLE_DRIVE_FOLDER_ID=\nOTHER=value\n",
        encoding="utf-8",
    )

    updates = build_google_env_updates(
        drive_folder_id="folder-123",
        drive_folder_url="https://drive.google.com/drive/folders/folder-123",
        spreadsheet_id="sheet-123",
        spreadsheet_url="https://docs.google.com/spreadsheets/d/sheet-123/edit",
        sheet_name="Receipts",
        service_account_key_file="D:/Prj/harina-v3/secrets/harina-v4-bot-service-account.json",
    )
    upsert_env_file(env_file, updates)

    contents = env_file.read_text(encoding="utf-8")
    assert "GOOGLE_SERVICE_ACCOUNT_KEY_FILE=D:/Prj/harina-v3/secrets/harina-v4-bot-service-account.json" in contents
    assert "GOOGLE_DRIVE_FOLDER_ID=folder-123" in contents
    assert "GOOGLE_DRIVE_FOLDER_URL=https://drive.google.com/drive/folders/folder-123" in contents
    assert "GOOGLE_SHEETS_SPREADSHEET_ID=sheet-123" in contents
    assert "GOOGLE_SHEETS_SPREADSHEET_URL=https://docs.google.com/spreadsheets/d/sheet-123/edit" in contents
    assert "GOOGLE_SHEETS_SHEET_NAME=Receipts" in contents
    assert "GOOGLE_SHEETS_CATEGORY_SHEET_NAME=Categories" in contents
    assert "OTHER=value" in contents


def test_build_google_env_updates_supports_oauth() -> None:
    updates = build_google_env_updates(
        drive_folder_id="folder-123",
        drive_folder_url="https://drive.google.com/drive/folders/folder-123",
        spreadsheet_id="sheet-123",
        spreadsheet_url="https://docs.google.com/spreadsheets/d/sheet-123/edit",
        sheet_name="Receipts",
        oauth_client_secret_file="D:/Prj/harina-v3/secrets/harina-oauth.json",
        oauth_refresh_token="refresh-token",
    )

    assert updates["GOOGLE_OAUTH_CLIENT_SECRET_FILE"] == "D:/Prj/harina-v3/secrets/harina-oauth.json"
    assert updates["GOOGLE_OAUTH_REFRESH_TOKEN"] == "refresh-token"
    assert updates["GOOGLE_DRIVE_FOLDER_URL"] == "https://drive.google.com/drive/folders/folder-123"
    assert updates["GOOGLE_SHEETS_SPREADSHEET_URL"] == "https://docs.google.com/spreadsheets/d/sheet-123/edit"
    assert updates["GOOGLE_SHEETS_CATEGORY_SHEET_NAME"] == "Categories"


def test_build_drive_watch_env_updates_includes_urls_and_poll_interval() -> None:
    updates = build_drive_watch_env_updates(
        source_folder_id="source-123",
        source_folder_url="https://drive.google.com/drive/folders/source-123",
        processed_folder_id="processed-123",
        processed_folder_url="https://drive.google.com/drive/folders/processed-123",
        poll_interval_seconds=45,
    )

    assert updates["GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID"] == "source-123"
    assert updates["GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_URL"] == "https://drive.google.com/drive/folders/source-123"
    assert updates["GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID"] == "processed-123"
    assert updates["GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_URL"] == "https://drive.google.com/drive/folders/processed-123"
    assert updates["DRIVE_POLL_INTERVAL_SECONDS"] == "45"


def test_build_drive_watch_env_updates_rejects_non_positive_poll_interval() -> None:
    try:
        build_drive_watch_env_updates(
            source_folder_id="source-123",
            source_folder_url="https://drive.google.com/drive/folders/source-123",
            processed_folder_id="processed-123",
            processed_folder_url="https://drive.google.com/drive/folders/processed-123",
            poll_interval_seconds=0,
        )
    except ValueError as exc:
        assert "greater than 0" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-positive poll interval")


def test_bootstrap_team_drive_watch_creates_member_folders(monkeypatch) -> None:
    drive = _FakeDriveService(folder_files=[], spreadsheet_files=[])

    monkeypatch.setattr(
        "app.google_setup.build",
        lambda service_name, version, credentials, cache_discovery: drive,
    )

    members = [build_team_member_spec("Alice"), build_team_member_spec("Bob")]
    result = GoogleResourceBootstrapper(credentials=object()).bootstrap_team_drive_watch(
        members=members,
        parent_folder_name="Harina V4 Team Intake",
        share_with_email="owner@example.com",
    )

    assert result.parent_folder_id == "folder-1"
    assert [route.key for route in result.routes] == ["alice", "bob"]
    assert drive.files_service.created == [
        {"name": "Harina V4 Team Intake", "mimeType": "application/vnd.google-apps.folder"},
        {"name": "Alice", "mimeType": "application/vnd.google-apps.folder", "parents": ["folder-1"]},
        {"name": "_processed", "mimeType": "application/vnd.google-apps.folder", "parents": ["folder-2"]},
        {"name": "Bob", "mimeType": "application/vnd.google-apps.folder", "parents": ["folder-1"]},
        {"name": "_processed", "mimeType": "application/vnd.google-apps.folder", "parents": ["folder-4"]},
    ]
    assert drive.permissions_service.calls == [
        ("folder-2", "owner@example.com"),
        ("folder-3", "owner@example.com"),
        ("folder-4", "owner@example.com"),
        ("folder-5", "owner@example.com"),
        ("folder-1", "owner@example.com"),
    ]


def test_build_team_drive_watch_env_updates_serializes_routes() -> None:
    updates = build_team_drive_watch_env_updates(
        routes=[
            DriveWatchRoute(
                key="alice",
                label="Alice",
                discord_channel_id=111,
                channel_name="alice",
                source_folder_id="source-1",
                source_folder_url="https://drive.example/source-1",
                processed_folder_id="processed-1",
                processed_folder_url="https://drive.example/processed-1",
            )
        ],
        poll_interval_seconds=75,
    )

    assert '"key":"alice"' in updates["DRIVE_WATCH_ROUTES_JSON"]
    assert '"discord_channel_id":111' in updates["DRIVE_WATCH_ROUTES_JSON"]
    assert updates["DRIVE_POLL_INTERVAL_SECONDS"] == "75"
