from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator


load_dotenv()


class Settings(BaseModel):
    discord_token: str = Field(alias="DISCORD_TOKEN")
    discord_channel_ids: str | None = Field(default=None, alias="DISCORD_CHANNEL_IDS")
    gemini_api_key: str = Field(alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3-flash-preview", alias="GEMINI_MODEL")
    google_service_account_json: str | None = Field(default=None, alias="GOOGLE_SERVICE_ACCOUNT_JSON")
    google_service_account_key_file: str | None = Field(default=None, alias="GOOGLE_SERVICE_ACCOUNT_KEY_FILE")
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
        if self.google_service_account_json:
            data = json.loads(self.google_service_account_json)
        elif self.google_service_account_key_file:
            data = json.loads(Path(self.google_service_account_key_file).read_text(encoding="utf-8"))
        else:
            raise ValueError("Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_KEY_FILE.")

        if "private_key" in data and isinstance(data["private_key"], str):
            data["private_key"] = data["private_key"].replace("\\n", "\n")

        return data

    @field_validator("discord_token", "gemini_api_key", "google_drive_folder_id", "google_sheets_spreadsheet_id")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This value must not be blank.")
        return value

    @field_validator("discord_channel_ids", "google_service_account_json", "google_service_account_key_file", mode="before")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()
        return value or None


def load_settings() -> Settings:
    try:
        return Settings.model_validate(os.environ)
    except ValidationError as exc:
        raise RuntimeError(f"Environment validation failed:\n{exc}") from exc
