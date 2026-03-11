from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google_auth_oauthlib.flow import InstalledAppFlow

from app.google_auth import SCOPES


@dataclass(slots=True)
class GoogleOAuthLoginResult:
    client_id: str
    refresh_token: str
    scopes: list[str]

    def as_dict(self) -> dict[str, str | list[str]]:
        return asdict(self)


@dataclass(slots=True)
class GoogleOAuthStartResult:
    authorization_url: str
    redirect_uri: str
    session_file: str
    state: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def run_oauth_login(
    *,
    oauth_client_info: dict,
    host: str,
    port: int,
    open_browser: bool,
) -> GoogleOAuthLoginResult:
    flow = InstalledAppFlow.from_client_config({"installed": oauth_client_info}, SCOPES)
    credentials = flow.run_local_server(
        host=host,
        port=port,
        open_browser=open_browser,
        authorization_prompt_message=(
            "Open this URL to authorize HARINA with Google Drive and Google Sheets:\n{url}\n"
        ),
        success_message="HARINA Google OAuth setup completed. You can close this tab.",
    )

    if not credentials.refresh_token:
        raise RuntimeError(
            "Google did not return a refresh token. Revoke the existing HARINA grant and retry, or add prompt=consent."
        )

    return GoogleOAuthLoginResult(
        client_id=oauth_client_info["client_id"],
        refresh_token=credentials.refresh_token,
        scopes=list(credentials.scopes or SCOPES),
    )


def start_oauth_login(
    *,
    oauth_client_info: dict,
    host: str,
    port: int,
    session_file: Path,
) -> GoogleOAuthStartResult:
    flow = InstalledAppFlow.from_client_config({"installed": oauth_client_info}, SCOPES, autogenerate_code_verifier=True)
    flow.redirect_uri = f"http://{host}:{port}/"
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    session_payload = {
        "oauth_client_info": oauth_client_info,
        "redirect_uri": flow.redirect_uri,
        "state": state,
        "code_verifier": flow.code_verifier,
    }
    session_file.write_text(json.dumps(session_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    return GoogleOAuthStartResult(
        authorization_url=authorization_url,
        redirect_uri=flow.redirect_uri,
        session_file=str(session_file),
        state=state,
    )


def finish_oauth_login(*, session_file: Path, redirect_url: str) -> GoogleOAuthLoginResult:
    session_payload = json.loads(session_file.read_text(encoding="utf-8"))
    parsed = urlparse(redirect_url)
    query = parse_qs(parsed.query)
    code = _require_query_value(query, "code")
    state = _require_query_value(query, "state")

    if state != session_payload["state"]:
        raise RuntimeError("OAuth state mismatch while finishing the HARINA Google login flow.")

    flow = InstalledAppFlow.from_client_config(
        {"installed": session_payload["oauth_client_info"]},
        SCOPES,
        autogenerate_code_verifier=True,
    )
    flow.redirect_uri = session_payload["redirect_uri"]
    flow.code_verifier = session_payload["code_verifier"]
    flow.fetch_token(code=code)

    credentials = flow.credentials
    if not credentials.refresh_token:
        raise RuntimeError(
            "Google did not return a refresh token. Revoke the existing HARINA grant and retry the consent flow."
        )

    return GoogleOAuthLoginResult(
        client_id=session_payload["oauth_client_info"]["client_id"],
        refresh_token=credentials.refresh_token,
        scopes=list(credentials.scopes or SCOPES),
    )


def _require_query_value(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key)
    if not values or not values[0]:
        raise RuntimeError(f"OAuth redirect URL did not include `{key}`.")
    return values[0]
