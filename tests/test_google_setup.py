from pathlib import Path

from app.google_setup import GoogleResourceBootstrapper, build_google_env_updates, upsert_env_file


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

    def list(self, *, q: str, fields: str, pageSize: int) -> _Execute:
        del fields, pageSize
        if "application/vnd.google-apps.folder" in q:
            return _Execute({"files": self.folder_files})
        return _Execute({"files": self.spreadsheet_files})

    def create(self, *, body: dict, fields: str) -> _Execute:
        del fields
        self.created.append(body)
        created_id = "folder-123" if body["mimeType"] == "application/vnd.google-apps.folder" else "sheet-123"
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
    ensured: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        "app.google_setup.build",
        lambda service_name, version, credentials, cache_discovery: drive,
    )

    class _FakeWorkspaceClient:
        def __init__(self, *, credentials, drive_folder_id: str, spreadsheet_id: str, sheet_name: str) -> None:
            del credentials
            ensured.append((drive_folder_id, spreadsheet_id, sheet_name))

        def _ensure_receipt_sheet_sync(self) -> None:
            return None

    monkeypatch.setattr("app.google_setup.GoogleWorkspaceClient", _FakeWorkspaceClient)

    result = GoogleResourceBootstrapper(credentials=object()).bootstrap(
        folder_name="Harina V4 Receipts",
        spreadsheet_title="Harina V4 Receipts",
        sheet_name="Receipts",
        share_with_email="owner@example.com",
    )

    assert result.folder_id == "folder-123"
    assert result.spreadsheet_id == "sheet-123"
    assert result.shared_with_email == "owner@example.com"
    assert drive.files_service.created == [
        {"name": "Harina V4 Receipts", "mimeType": "application/vnd.google-apps.folder"},
        {
            "name": "Harina V4 Receipts",
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }
    ]
    assert drive.permissions_service.calls == [("folder-123", "owner@example.com"), ("sheet-123", "owner@example.com")]
    assert ensured == [("folder-123", "sheet-123", "Receipts")]


def test_upsert_env_file_replaces_existing_keys(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DISCORD_TOKEN=test-token\nGOOGLE_SERVICE_ACCOUNT_KEY_FILE=\nGOOGLE_DRIVE_FOLDER_ID=\nOTHER=value\n",
        encoding="utf-8",
    )

    updates = build_google_env_updates(
        drive_folder_id="folder-123",
        spreadsheet_id="sheet-123",
        sheet_name="Receipts",
        service_account_key_file="D:/Prj/harina-v3/secrets/harina-v4-bot-service-account.json",
    )
    upsert_env_file(env_file, updates)

    contents = env_file.read_text(encoding="utf-8")
    assert "GOOGLE_SERVICE_ACCOUNT_KEY_FILE=D:/Prj/harina-v3/secrets/harina-v4-bot-service-account.json" in contents
    assert "GOOGLE_DRIVE_FOLDER_ID=folder-123" in contents
    assert "GOOGLE_SHEETS_SPREADSHEET_ID=sheet-123" in contents
    assert "GOOGLE_SHEETS_SHEET_NAME=Receipts" in contents
    assert "OTHER=value" in contents


def test_build_google_env_updates_supports_oauth() -> None:
    updates = build_google_env_updates(
        drive_folder_id="folder-123",
        spreadsheet_id="sheet-123",
        sheet_name="Receipts",
        oauth_client_secret_file="D:/Prj/harina-v3/secrets/harina-oauth.json",
        oauth_refresh_token="refresh-token",
    )

    assert updates["GOOGLE_OAUTH_CLIENT_SECRET_FILE"] == "D:/Prj/harina-v3/secrets/harina-oauth.json"
    assert updates["GOOGLE_OAUTH_REFRESH_TOKEN"] == "refresh-token"
