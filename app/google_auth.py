from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from google.oauth2 import credentials as oauth_credentials
from google.oauth2 import service_account


SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def load_service_account_info(
    *,
    service_account_json: str | None = None,
    service_account_key_file: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    if service_account_json:
        data = json.loads(service_account_json)
    elif service_account_key_file:
        data = json.loads(Path(service_account_key_file).read_text(encoding="utf-8"))
    else:
        raise ValueError("Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_KEY_FILE.")

    if "private_key" in data and isinstance(data["private_key"], str):
        data["private_key"] = data["private_key"].replace("\\n", "\n")

    return data


def load_oauth_client_info(
    *,
    oauth_client_json: str | None = None,
    oauth_client_secret_file: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    if oauth_client_json:
        raw = json.loads(oauth_client_json)
    elif oauth_client_secret_file:
        raw = json.loads(Path(oauth_client_secret_file).read_text(encoding="utf-8"))
    else:
        raise ValueError("Set GOOGLE_OAUTH_CLIENT_JSON or GOOGLE_OAUTH_CLIENT_SECRET_FILE.")

    return raw.get("installed") or raw.get("web") or raw


def build_google_credentials(
    *,
    service_account_info: dict[str, Any] | None = None,
    oauth_client_info: dict[str, Any] | None = None,
    oauth_refresh_token: str | None = None,
):
    if oauth_client_info and oauth_refresh_token:
        return oauth_credentials.Credentials(
            token=None,
            refresh_token=oauth_refresh_token,
            token_uri=oauth_client_info.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=oauth_client_info["client_id"],
            client_secret=oauth_client_info["client_secret"],
            scopes=SCOPES,
        )

    if service_account_info:
        return service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)

    raise ValueError(
        "Configure either a service account (GOOGLE_SERVICE_ACCOUNT_JSON / GOOGLE_SERVICE_ACCOUNT_KEY_FILE) "
        "or OAuth refresh-token credentials (GOOGLE_OAUTH_CLIENT_JSON / GOOGLE_OAUTH_CLIENT_SECRET_FILE plus "
        "GOOGLE_OAUTH_REFRESH_TOKEN)."
    )
