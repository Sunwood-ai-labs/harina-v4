from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.google_workspace import GoogleWorkspaceClient
from app.team_intake import DriveWatchRoute, TeamMemberSpec, build_drive_watch_routes_env_value


FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
SPREADSHEET_MIME_TYPE = "application/vnd.google-apps.spreadsheet"


@dataclass(slots=True)
class GoogleResourceBootstrapResult:
    folder_id: str
    folder_url: str
    spreadsheet_id: str
    spreadsheet_url: str
    sheet_name: str
    shared_with_email: str | None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(slots=True)
class GoogleDriveWatchBootstrapResult:
    source_folder_id: str
    source_folder_url: str
    processed_folder_id: str
    processed_folder_url: str
    parent_folder_id: str | None
    shared_with_email: str | None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(slots=True)
class GoogleDriveWatchRouteResource:
    key: str
    label: str
    source_folder_id: str
    source_folder_url: str
    processed_folder_id: str
    processed_folder_url: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class GoogleTeamDriveWatchBootstrapResult:
    parent_folder_id: str | None
    parent_folder_url: str | None
    routes: list[GoogleDriveWatchRouteResource]
    shared_with_email: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "parent_folder_id": self.parent_folder_id,
            "parent_folder_url": self.parent_folder_url,
            "routes": [route.as_dict() for route in self.routes],
            "shared_with_email": self.shared_with_email,
        }


class GoogleResourceBootstrapper:
    def __init__(self, *, credentials) -> None:
        self._drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self._credentials = credentials

    def bootstrap(
        self,
        *,
        folder_name: str,
        spreadsheet_title: str,
        sheet_name: str,
        share_with_email: str | None = None,
    ) -> GoogleResourceBootstrapResult:
        folder = self._ensure_drive_folder(folder_name)
        spreadsheet = self._ensure_spreadsheet(spreadsheet_title, sheet_name)

        if share_with_email:
            self._share_file(folder["id"], share_with_email)
            self._share_file(spreadsheet["spreadsheetId"], share_with_email)

        GoogleWorkspaceClient(
            credentials=self._credentials,
            drive_folder_id=folder["id"],
            spreadsheet_id=spreadsheet["spreadsheetId"],
            sheet_name=sheet_name,
        )._ensure_receipt_sheet_sync()

        return GoogleResourceBootstrapResult(
            folder_id=folder["id"],
            folder_url=folder.get("webViewLink") or f"https://drive.google.com/drive/folders/{folder['id']}",
            spreadsheet_id=spreadsheet["spreadsheetId"],
            spreadsheet_url=spreadsheet.get("spreadsheetUrl")
            or f"https://docs.google.com/spreadsheets/d/{spreadsheet['spreadsheetId']}/edit",
            sheet_name=sheet_name,
            shared_with_email=share_with_email,
        )

    def bootstrap_drive_watch(
        self,
        *,
        source_folder_name: str,
        processed_folder_name: str,
        parent_folder_id: str | None = None,
        share_with_email: str | None = None,
    ) -> GoogleDriveWatchBootstrapResult:
        source_folder = self._ensure_drive_folder(source_folder_name, parent_folder_id=parent_folder_id)
        processed_folder = self._ensure_drive_folder(processed_folder_name, parent_folder_id=parent_folder_id)

        if share_with_email:
            self._share_file(source_folder["id"], share_with_email)
            self._share_file(processed_folder["id"], share_with_email)

        return GoogleDriveWatchBootstrapResult(
            source_folder_id=source_folder["id"],
            source_folder_url=source_folder.get("webViewLink")
            or f"https://drive.google.com/drive/folders/{source_folder['id']}",
            processed_folder_id=processed_folder["id"],
            processed_folder_url=processed_folder.get("webViewLink")
            or f"https://drive.google.com/drive/folders/{processed_folder['id']}",
            parent_folder_id=parent_folder_id,
            shared_with_email=share_with_email,
        )

    def bootstrap_team_drive_watch(
        self,
        *,
        members: list[TeamMemberSpec],
        parent_folder_id: str | None = None,
        parent_folder_name: str | None = None,
        share_with_email: str | None = None,
    ) -> GoogleTeamDriveWatchBootstrapResult:
        resolved_parent_folder: dict[str, str] | None = None
        if parent_folder_id:
            resolved_parent_folder = {
                "id": parent_folder_id,
                "webViewLink": f"https://drive.google.com/drive/folders/{parent_folder_id}",
            }
        elif parent_folder_name:
            resolved_parent_folder = self._ensure_drive_folder(parent_folder_name)

        routes: list[GoogleDriveWatchRouteResource] = []
        for member in members:
            source_folder = self._ensure_drive_folder(
                member.source_folder_name,
                parent_folder_id=resolved_parent_folder["id"] if resolved_parent_folder else None,
            )
            processed_folder = self._ensure_drive_folder(
                member.processed_folder_name,
                parent_folder_id=source_folder["id"],
            )

            if share_with_email:
                self._share_file(source_folder["id"], share_with_email)
                self._share_file(processed_folder["id"], share_with_email)

            routes.append(
                GoogleDriveWatchRouteResource(
                    key=member.key,
                    label=member.label,
                    source_folder_id=source_folder["id"],
                    source_folder_url=source_folder.get("webViewLink")
                    or f"https://drive.google.com/drive/folders/{source_folder['id']}",
                    processed_folder_id=processed_folder["id"],
                    processed_folder_url=processed_folder.get("webViewLink")
                    or f"https://drive.google.com/drive/folders/{processed_folder['id']}",
                )
            )

        if share_with_email and resolved_parent_folder is not None:
            self._share_file(resolved_parent_folder["id"], share_with_email)

        return GoogleTeamDriveWatchBootstrapResult(
            parent_folder_id=resolved_parent_folder["id"] if resolved_parent_folder else None,
            parent_folder_url=resolved_parent_folder.get("webViewLink") if resolved_parent_folder else None,
            routes=routes,
            shared_with_email=share_with_email,
        )

    def _ensure_drive_folder(self, folder_name: str, *, parent_folder_id: str | None = None) -> dict[str, str]:
        query = (
            f"mimeType = '{FOLDER_MIME_TYPE}' and trashed = false and name = '{_escape_drive_query(folder_name)}'"
        )
        if parent_folder_id:
            query = f"{query} and '{_escape_drive_query(parent_folder_id)}' in parents"

        existing = (
            self._drive.files()
            .list(
                q=query,
                fields="files(id,name,webViewLink)",
                pageSize=1,
            )
            .execute()
        )

        files = existing.get("files", [])
        if files:
            return files[0]

        return (
            self._drive.files()
            .create(
                body=_folder_create_body(folder_name, parent_folder_id=parent_folder_id),
                fields="id,name,webViewLink",
            )
            .execute()
        )

    def _ensure_spreadsheet(self, spreadsheet_title: str, sheet_name: str) -> dict[str, str]:
        del sheet_name
        existing = (
            self._drive.files()
            .list(
                q=(
                    f"mimeType = '{SPREADSHEET_MIME_TYPE}' and trashed = false "
                    f"and name = '{_escape_drive_query(spreadsheet_title)}'"
                ),
                fields="files(id,name,webViewLink)",
                pageSize=1,
            )
            .execute()
        )

        files = existing.get("files", [])
        if files:
            return {
                "spreadsheetId": files[0]["id"],
                "spreadsheetUrl": f"https://docs.google.com/spreadsheets/d/{files[0]['id']}/edit",
            }

        created = (
            self._drive.files()
            .create(
                body={"name": spreadsheet_title, "mimeType": SPREADSHEET_MIME_TYPE},
                fields="id,webViewLink",
            )
            .execute()
        )
        return {
            "spreadsheetId": created["id"],
            "spreadsheetUrl": f"https://docs.google.com/spreadsheets/d/{created['id']}/edit",
        }

    def _share_file(self, file_id: str, email: str) -> None:
        try:
            self._drive.permissions().create(
                fileId=file_id,
                body={"type": "user", "role": "writer", "emailAddress": email},
                fields="id",
                sendNotificationEmail=False,
            ).execute()
        except HttpError as exc:
            if getattr(exc, "status_code", None) == 409:
                return
            if getattr(exc, "resp", None) is not None and getattr(exc.resp, "status", None) == 409:
                return
            raise


def build_google_env_updates(
    *,
    drive_folder_id: str,
    drive_folder_url: str,
    spreadsheet_id: str,
    spreadsheet_url: str,
    sheet_name: str,
    service_account_key_file: str | None = None,
    oauth_client_secret_file: str | None = None,
    oauth_refresh_token: str | None = None,
) -> dict[str, str]:
    values = {
        "GOOGLE_DRIVE_FOLDER_ID": drive_folder_id,
        "GOOGLE_DRIVE_FOLDER_URL": drive_folder_url,
        "GOOGLE_SHEETS_SPREADSHEET_ID": spreadsheet_id,
        "GOOGLE_SHEETS_SPREADSHEET_URL": spreadsheet_url,
        "GOOGLE_SHEETS_SHEET_NAME": sheet_name,
    }
    if service_account_key_file:
        values["GOOGLE_SERVICE_ACCOUNT_KEY_FILE"] = service_account_key_file
    if oauth_client_secret_file:
        values["GOOGLE_OAUTH_CLIENT_SECRET_FILE"] = oauth_client_secret_file
    if oauth_refresh_token:
        values["GOOGLE_OAUTH_REFRESH_TOKEN"] = oauth_refresh_token
    return values


def build_drive_watch_env_updates(
    *,
    source_folder_id: str,
    source_folder_url: str,
    processed_folder_id: str,
    processed_folder_url: str,
    poll_interval_seconds: int | None = None,
) -> dict[str, str]:
    if poll_interval_seconds is not None and poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be greater than 0.")

    values = {
        "GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID": source_folder_id,
        "GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_URL": source_folder_url,
        "GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID": processed_folder_id,
        "GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_URL": processed_folder_url,
    }
    if poll_interval_seconds is not None:
        values["DRIVE_POLL_INTERVAL_SECONDS"] = str(poll_interval_seconds)
    return values


def build_team_drive_watch_env_updates(
    *,
    routes: list[DriveWatchRoute],
    poll_interval_seconds: int | None = None,
) -> dict[str, str]:
    if poll_interval_seconds is not None and poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be greater than 0.")

    values = {
        "DRIVE_WATCH_ROUTES_JSON": build_drive_watch_routes_env_value(routes),
    }
    if poll_interval_seconds is not None:
        values["DRIVE_POLL_INTERVAL_SECONDS"] = str(poll_interval_seconds)
    return values


def upsert_env_file(env_file: Path, values: Mapping[str, str]) -> None:
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    seen_keys: set[str] = set()
    updated_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            updated_lines.append(line)
            continue

        key, _, _value = line.partition("=")
        normalized_key = key.strip()
        replacement = values.get(normalized_key)
        if replacement is None:
            updated_lines.append(line)
            continue

        updated_lines.append(f"{normalized_key}={replacement}")
        seen_keys.add(normalized_key)

    if updated_lines and updated_lines[-1] != "":
        updated_lines.append("")

    for key, value in values.items():
        if key not in seen_keys:
            updated_lines.append(f"{key}={value}")

    env_file.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")


def _escape_drive_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _folder_create_body(folder_name: str, *, parent_folder_id: str | None) -> dict[str, object]:
    body: dict[str, object] = {"name": folder_name, "mimeType": FOLDER_MIME_TYPE}
    if parent_folder_id:
        body["parents"] = [parent_folder_id]
    return body
