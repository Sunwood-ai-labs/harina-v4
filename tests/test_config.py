import pytest

from app.config import Settings
from app.google_auth import load_oauth_client_info


def test_load_oauth_client_info_unwraps_installed_payload() -> None:
    client_info = load_oauth_client_info(
        oauth_client_json=(
            '{"installed":{"client_id":"client-id","client_secret":"client-secret",'
            '"token_uri":"https://oauth2.googleapis.com/token"}}'
        )
    )

    assert client_info["client_id"] == "client-id"
    assert client_info["client_secret"] == "client-secret"


def test_settings_accepts_oauth_refresh_token_credentials() -> None:
    settings = Settings.model_validate(
        {
            "GEMINI_API_KEY": "gemini-key",
            "GOOGLE_OAUTH_CLIENT_JSON": (
                '{"installed":{"client_id":"client-id","client_secret":"client-secret",'
                '"token_uri":"https://oauth2.googleapis.com/token"}}'
            ),
            "GOOGLE_OAUTH_REFRESH_TOKEN": "refresh-token",
            "GOOGLE_DRIVE_FOLDER_ID": "folder-id",
            "GOOGLE_SHEETS_SPREADSHEET_ID": "sheet-id",
        }
    )

    credentials = settings.google_credentials

    assert credentials.client_id == "client-id"
    assert credentials.client_secret == "client-secret"
    assert credentials.refresh_token == "refresh-token"


def test_settings_can_power_receipt_cli_without_discord_token() -> None:
    settings = Settings.model_validate(
        {
            "GEMINI_API_KEY": "gemini-key",
        }
    )

    assert settings.require_gemini_api_key() == "gemini-key"


def test_require_google_workspace_rejects_missing_drive_targets() -> None:
    settings = Settings.model_validate(
        {
            "GEMINI_API_KEY": "gemini-key",
            "GOOGLE_OAUTH_CLIENT_JSON": (
                '{"installed":{"client_id":"client-id","client_secret":"client-secret",'
                '"token_uri":"https://oauth2.googleapis.com/token"}}'
            ),
            "GOOGLE_OAUTH_REFRESH_TOKEN": "refresh-token",
        }
    )

    with pytest.raises(RuntimeError, match="GOOGLE_DRIVE_FOLDER_ID"):
        settings.require_google_workspace()
