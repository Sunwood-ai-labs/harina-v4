from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.google_auth import build_google_credentials, load_oauth_client_info, load_service_account_info


load_dotenv()


class Settings(BaseModel):
    discord_token: str | None = Field(default=None, alias="DISCORD_TOKEN")
    discord_channel_ids: str | None = Field(default=None, alias="DISCORD_CHANNEL_IDS")
    discord_test_channel_id: int | None = Field(default=None, alias="DISCORD_TEST_CHANNEL_ID")
    discord_test_message_prefix: str = Field(default="[HARINA-TEST]", alias="DISCORD_TEST_MESSAGE_PREFIX")
    discord_notify_channel_id: int | None = Field(default=None, alias="DISCORD_NOTIFY_CHANNEL_ID")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3-flash-preview", alias="GEMINI_MODEL")
    google_service_account_json: str | None = Field(default=None, alias="GOOGLE_SERVICE_ACCOUNT_JSON")
    google_service_account_key_file: str | None = Field(default=None, alias="GOOGLE_SERVICE_ACCOUNT_KEY_FILE")
    google_oauth_client_json: str | None = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_JSON")
    google_oauth_client_secret_file: str | None = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_SECRET_FILE")
    google_oauth_refresh_token: str | None = Field(default=None, alias="GOOGLE_OAUTH_REFRESH_TOKEN")
    google_drive_folder_id: str | None = Field(default=None, alias="GOOGLE_DRIVE_FOLDER_ID")
    google_sheets_spreadsheet_id: str | None = Field(default=None, alias="GOOGLE_SHEETS_SPREADSHEET_ID")
    google_sheets_sheet_name: str = Field(default="Receipts", alias="GOOGLE_SHEETS_SHEET_NAME")
    google_drive_watch_source_folder_id: str | None = Field(default=None, alias="GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID")
    google_drive_watch_processed_folder_id: str | None = Field(
        default=None,
        alias="GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID",
    )
    drive_poll_interval_seconds: int = Field(default=60, alias="DRIVE_POLL_INTERVAL_SECONDS")

    @property
    def allowed_channel_ids(self) -> set[int]:
        if not self.discord_channel_ids:
            return set()

        values = {value.strip() for value in self.discord_channel_ids.split(",") if value.strip()}
        return {int(value) for value in values}

    @property
    def service_account_info(self) -> dict[str, Any]:
        return load_service_account_info(
            service_account_json=self.google_service_account_json,
            service_account_key_file=self.google_service_account_key_file,
        )

    @property
    def oauth_client_info(self) -> dict[str, Any]:
        return load_oauth_client_info(
            oauth_client_json=self.google_oauth_client_json,
            oauth_client_secret_file=self.google_oauth_client_secret_file,
        )

    @property
    def google_credentials(self):
        service_account_info = None
        oauth_client_info = None

        if self.google_service_account_json or self.google_service_account_key_file:
            service_account_info = self.service_account_info

        if self.google_oauth_refresh_token and (self.google_oauth_client_json or self.google_oauth_client_secret_file):
            oauth_client_info = self.oauth_client_info

        return build_google_credentials(
            service_account_info=service_account_info,
            oauth_client_info=oauth_client_info,
            oauth_refresh_token=self.google_oauth_refresh_token,
        )

    @field_validator(
        "discord_test_message_prefix",
    )
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This value must not be blank.")
        return value

    @field_validator(
        "discord_token",
        "discord_channel_ids",
        "discord_test_channel_id",
        "discord_notify_channel_id",
        "gemini_api_key",
        "google_service_account_json",
        "google_service_account_key_file",
        "google_oauth_client_json",
        "google_oauth_client_secret_file",
        "google_oauth_refresh_token",
        "google_drive_folder_id",
        "google_drive_watch_source_folder_id",
        "google_drive_watch_processed_folder_id",
        "google_sheets_spreadsheet_id",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            return value or None

        return value

    def has_google_auth(self) -> bool:
        has_service_account = bool(self.google_service_account_json or self.google_service_account_key_file)
        has_oauth = bool(
            self.google_oauth_refresh_token and (self.google_oauth_client_json or self.google_oauth_client_secret_file)
        )
        return has_service_account or has_oauth

    def require_discord_token(self) -> str:
        if not self.discord_token:
            raise RuntimeError("Set DISCORD_TOKEN in your environment or .env before running Discord commands.")
        return self.discord_token

    def require_gemini_api_key(self) -> str:
        if not self.gemini_api_key:
            raise RuntimeError("Set GEMINI_API_KEY in your environment or .env before running receipt commands.")
        return self.gemini_api_key

    def require_google_workspace(self) -> None:
        if not self.has_google_auth():
            raise RuntimeError(
                "Configure either GOOGLE_SERVICE_ACCOUNT_JSON / GOOGLE_SERVICE_ACCOUNT_KEY_FILE or "
                "GOOGLE_OAUTH_CLIENT_JSON / GOOGLE_OAUTH_CLIENT_SECRET_FILE plus GOOGLE_OAUTH_REFRESH_TOKEN."
            )
        if not self.google_drive_folder_id:
            raise RuntimeError("Set GOOGLE_DRIVE_FOLDER_ID in your environment or .env before writing receipts.")
        if not self.google_sheets_spreadsheet_id:
            raise RuntimeError(
                "Set GOOGLE_SHEETS_SPREADSHEET_ID in your environment or .env before writing receipts."
            )

    def require_drive_watch(self) -> None:
        if not self.discord_token:
            raise RuntimeError("Set DISCORD_TOKEN in your environment or .env before running drive watch commands.")
        if not self.gemini_api_key:
            raise RuntimeError("Set GEMINI_API_KEY in your environment or .env before running drive watch commands.")
        if not self.has_google_auth():
            raise RuntimeError(
                "Configure either GOOGLE_SERVICE_ACCOUNT_JSON / GOOGLE_SERVICE_ACCOUNT_KEY_FILE or "
                "GOOGLE_OAUTH_CLIENT_JSON / GOOGLE_OAUTH_CLIENT_SECRET_FILE plus GOOGLE_OAUTH_REFRESH_TOKEN."
            )
        if not self.google_sheets_spreadsheet_id:
            raise RuntimeError(
                "Set GOOGLE_SHEETS_SPREADSHEET_ID in your environment or .env before running drive watch commands."
            )
        if not self.google_drive_watch_source_folder_id:
            raise RuntimeError(
                "Set GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID in your environment or .env before running drive watch commands."
            )
        if not self.google_drive_watch_processed_folder_id:
            raise RuntimeError(
                "Set GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID in your environment or .env before running drive watch commands."
            )
        if self.discord_notify_channel_id is None:
            raise RuntimeError(
                "Set DISCORD_NOTIFY_CHANNEL_ID in your environment or .env before running drive watch commands."
            )

    @field_validator("drive_poll_interval_seconds")
    @classmethod
    def validate_poll_interval(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("DRIVE_POLL_INTERVAL_SECONDS must be greater than 0.")
        return value

    @model_validator(mode="after")
    def validate_sheet_name(self) -> "Settings":
        self.google_sheets_sheet_name = self.google_sheets_sheet_name.strip()
        if not self.google_sheets_sheet_name:
            raise ValueError("GOOGLE_SHEETS_SHEET_NAME must not be blank.")
        return self


def load_settings(
    *,
    require_discord: bool = False,
    require_gemini: bool = False,
    require_google_workspace: bool = False,
) -> Settings:
    try:
        settings = Settings.model_validate(os.environ)
    except ValidationError as exc:
        raise RuntimeError(f"Environment validation failed:\n{exc}") from exc

    if require_discord:
        settings.require_discord_token()
    if require_gemini:
        settings.require_gemini_api_key()
    if require_google_workspace:
        settings.require_google_workspace()

    return settings
