from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.google_workspace import GoogleWorkspaceClient


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

    def _ensure_drive_folder(self, folder_name: str) -> dict[str, str]:
        existing = (
            self._drive.files()
            .list(
                q=f"mimeType = '{FOLDER_MIME_TYPE}' and trashed = false and name = '{_escape_drive_query(folder_name)}'",
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
                body={"name": folder_name, "mimeType": FOLDER_MIME_TYPE},
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
    spreadsheet_id: str,
    sheet_name: str,
    service_account_key_file: str | None = None,
    oauth_client_secret_file: str | None = None,
    oauth_refresh_token: str | None = None,
) -> dict[str, str]:
    values = {
        "GOOGLE_DRIVE_FOLDER_ID": drive_folder_id,
        "GOOGLE_SHEETS_SPREADSHEET_ID": spreadsheet_id,
        "GOOGLE_SHEETS_SHEET_NAME": sheet_name,
    }
    if service_account_key_file:
        values["GOOGLE_SERVICE_ACCOUNT_KEY_FILE"] = service_account_key_file
    if oauth_client_secret_file:
        values["GOOGLE_OAUTH_CLIENT_SECRET_FILE"] = oauth_client_secret_file
    if oauth_refresh_token:
        values["GOOGLE_OAUTH_REFRESH_TOKEN"] = oauth_refresh_token
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
