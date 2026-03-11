from pathlib import Path

from app.google_oauth import finish_oauth_login, start_oauth_login


class _FakeCredentials:
    def __init__(self, refresh_token: str) -> None:
        self.refresh_token = refresh_token
        self.scopes = ["scope-a", "scope-b"]


class _FakeFlow:
    def __init__(self) -> None:
        self.redirect_uri = ""
        self.code_verifier = "code-verifier"
        self.credentials = _FakeCredentials("refresh-token")
        self.fetched_code: str | None = None

    def authorization_url(self, **kwargs) -> tuple[str, str]:
        assert kwargs["access_type"] == "offline"
        assert kwargs["prompt"] == "consent"
        return ("https://accounts.google.com/o/oauth2/auth?state=session-state", "session-state")

    def fetch_token(self, *, code: str) -> None:
        self.fetched_code = code


def test_start_and_finish_oauth_login(monkeypatch, tmp_path: Path) -> None:
    created_flows: list[_FakeFlow] = []

    def fake_from_client_config(client_config: dict, scopes: list[str], autogenerate_code_verifier: bool = False):
        assert client_config["installed"]["client_id"] == "client-id"
        assert scopes
        assert autogenerate_code_verifier
        flow = _FakeFlow()
        created_flows.append(flow)
        return flow

    monkeypatch.setattr("app.google_oauth.InstalledAppFlow.from_client_config", fake_from_client_config)

    session_file = tmp_path / "oauth-session.json"
    start_result = start_oauth_login(
        oauth_client_info={"client_id": "client-id", "client_secret": "client-secret"},
        host="127.0.0.1",
        port=8765,
        session_file=session_file,
    )

    assert start_result.authorization_url.startswith("https://accounts.google.com/")
    assert start_result.redirect_uri == "http://127.0.0.1:8765/"
    assert session_file.exists()

    finish_result = finish_oauth_login(
        session_file=session_file,
        redirect_url="http://127.0.0.1:8765/?code=auth-code&state=session-state",
    )

    assert finish_result.refresh_token == "refresh-token"
    assert created_flows[-1].fetched_code == "auth-code"
