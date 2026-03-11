from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.google_auth import build_google_credentials, load_oauth_client_info, load_service_account_info


load_dotenv()

class Settings(BaseModel):
    discord_token: str = Field(alias="DISCORD_TOKEN")
    discord_channel_ids: str | None = Field(default=None, alias="DISCORD_CHANNEL_IDS")
    discord_test_channel_id: int | None = Field(default=None, alias="DISCORD_TEST_CHANNEL_ID")
    discord_test_message_prefix: str = Field(default="[HARINA-TEST]", alias="DISCORD_TEST_MESSAGE_PREFIX")
    gemini_api_key: str = Field(alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3-flash-preview", alias="GEMINI_MODEL")
    google_service_account_json: str | None = Field(default=None, alias="GOOGLE_SERVICE_ACCOUNT_JSON")
    google_service_account_key_file: str | None = Field(default=None, alias="GOOGLE_SERVICE_ACCOUNT_KEY_FILE")
    google_oauth_client_json: str | None = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_JSON")
    google_oauth_client_secret_file: str | None = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_SECRET_FILE")
    google_oauth_refresh_token: str | None = Field(default=None, alias="GOOGLE_OAUTH_REFRESH_TOKEN")
    google_drive_folder_id: str = Field(alias="GOOGLE_DRIVE_FOLDER_ID")
    google_sheets_spreadsheet_id: str = Field(alias="GOOGLE_SHEETS_SPREADSHEET_ID")
    google_sheets_sheet_name: str = Field(default="Receipts", alias="GOOGLE_SHEETS_SHEET_NAME")

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
        "discord_token",
        "discord_test_message_prefix",
        "gemini_api_key",
        "google_drive_folder_id",
        "google_sheets_spreadsheet_id",
    )
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This value must not be blank.")
        return value

    @field_validator(
        "discord_channel_ids",
        "discord_test_channel_id",
        "google_service_account_json",
        "google_service_account_key_file",
        "google_oauth_client_json",
        "google_oauth_client_secret_file",
        "google_oauth_refresh_token",
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

    @model_validator(mode="after")
    def validate_google_auth(self) -> "Settings":
        has_service_account = bool(self.google_service_account_json or self.google_service_account_key_file)
        has_oauth = bool(
            self.google_oauth_refresh_token and (self.google_oauth_client_json or self.google_oauth_client_secret_file)
        )

        if not has_service_account and not has_oauth:
            raise ValueError(
                "Configure either GOOGLE_SERVICE_ACCOUNT_JSON / GOOGLE_SERVICE_ACCOUNT_KEY_FILE or "
                "GOOGLE_OAUTH_CLIENT_JSON / GOOGLE_OAUTH_CLIENT_SECRET_FILE plus GOOGLE_OAUTH_REFRESH_TOKEN."
            )

        return self


def load_settings() -> Settings:
    try:
        return Settings.model_validate(os.environ)
    except ValidationError as exc:
        raise RuntimeError(f"Environment validation failed:\n{exc}") from exc
