from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from argparse import Namespace
from pathlib import Path

from googleapiclient.errors import HttpError

from app.bot import ReceiptBot
from app.config import Settings, load_settings
from app.dataset_downloader import DEFAULT_OUTPUT_DIR, run_downloader
from app.discord_upload_test import run_discord_upload_test
from app.gemini_smoke_test import run_smoke_test
from app.google_auth import build_google_credentials, load_oauth_client_info, load_service_account_info
from app.google_oauth import finish_oauth_login, run_oauth_login, start_oauth_login
from app.google_setup import GoogleResourceBootstrapper, build_google_env_updates, upsert_env_file


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harina", description="HARINA V4 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bot_parser = subparsers.add_parser("bot", help="Run the Discord bot or Discord-side bot checks.")
    bot_subparsers = bot_parser.add_subparsers(dest="bot_command", required=True)

    bot_run_parser = bot_subparsers.add_parser("run", help="Run the always-on Discord receipt bot.")
    bot_run_parser.set_defaults(handler=handle_bot_run)

    bot_upload_test_parser = bot_subparsers.add_parser(
        "upload-test",
        help="Upload a real receipt image to Discord and wait for the bot reply.",
    )
    bot_upload_test_parser.add_argument(
        "--channel-id",
        type=int,
        default=None,
        help="Discord channel ID for the test. Defaults to DISCORD_TEST_CHANNEL_ID when set.",
    )
    bot_upload_test_parser.add_argument("--image", required=True, help="Local image file to upload.")
    bot_upload_test_parser.add_argument("--caption", default="CLI upload test", help="Text appended after the test prefix.")
    bot_upload_test_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=60.0,
        help="How long to wait for the reply message. Default: 60",
    )
    bot_upload_test_parser.set_defaults(handler=handle_bot_upload_test)

    dataset_parser = subparsers.add_parser("dataset", help="Dataset acquisition and Gemini checks.")
    dataset_subparsers = dataset_parser.add_subparsers(dest="dataset_command", required=True)

    dataset_download_parser = dataset_subparsers.add_parser(
        "download",
        help="Download image attachments from a Discord channel into a dataset folder.",
    )
    dataset_download_parser.add_argument("channel_url", help="Discord channel URL.")
    dataset_download_parser.add_argument("--output-dir", default=None, help="Optional dataset output directory.")
    dataset_download_parser.add_argument("--limit", type=int, default=None, help="Maximum number of messages to scan.")
    dataset_download_parser.add_argument("--include-bots", action="store_true", help="Include bot-authored images.")
    dataset_download_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    dataset_download_parser.set_defaults(handler=handle_dataset_download)

    dataset_smoke_parser = dataset_subparsers.add_parser(
        "smoke-test",
        help="Run a quick Gemini smoke test against local dataset images.",
    )
    dataset_smoke_parser.add_argument("--dataset-dir", default=None, help="Dataset root to scan recursively.")
    dataset_smoke_parser.add_argument("--limit", type=int, default=2, help="Number of images to test.")
    dataset_smoke_parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Allow duplicate images instead of deduplicating by file hash.",
    )
    dataset_smoke_parser.add_argument("--output", default=None, help="Optional JSON output file.")
    dataset_smoke_parser.set_defaults(handler=handle_dataset_smoke_test)

    google_parser = subparsers.add_parser("google", help="Google Drive and Sheets bootstrap helpers.")
    google_subparsers = google_parser.add_subparsers(dest="google_command", required=True)

    google_init_parser = google_subparsers.add_parser(
        "init-resources",
        help="Create the Drive folder and Sheets spreadsheet used by HARINA.",
    )
    google_init_parser.add_argument(
        "--service-account-key-file",
        default=None,
        help="Path to the service account JSON key file. Defaults to GOOGLE_SERVICE_ACCOUNT_KEY_FILE.",
    )
    google_init_parser.add_argument(
        "--service-account-json",
        default=None,
        help="Raw service account JSON. Defaults to GOOGLE_SERVICE_ACCOUNT_JSON.",
    )
    google_init_parser.add_argument(
        "--oauth-client-secret-file",
        default=None,
        help="Path to the OAuth client secret JSON file. Defaults to GOOGLE_OAUTH_CLIENT_SECRET_FILE.",
    )
    google_init_parser.add_argument(
        "--oauth-client-json",
        default=None,
        help="Raw OAuth client JSON. Defaults to GOOGLE_OAUTH_CLIENT_JSON.",
    )
    google_init_parser.add_argument(
        "--oauth-refresh-token",
        default=None,
        help="OAuth refresh token. Defaults to GOOGLE_OAUTH_REFRESH_TOKEN.",
    )
    google_init_parser.add_argument(
        "--folder-name",
        default="Harina V4 Receipts",
        help="Drive folder name. Default: Harina V4 Receipts",
    )
    google_init_parser.add_argument(
        "--spreadsheet-title",
        default="Harina V4 Receipts",
        help="Spreadsheet title. Default: Harina V4 Receipts",
    )
    google_init_parser.add_argument(
        "--sheet-name",
        default="Receipts",
        help="Sheet tab name for appended rows. Default: Receipts",
    )
    google_init_parser.add_argument(
        "--share-with-email",
        default=None,
        help="Optional Google account email to share the created resources with.",
    )
    google_init_parser.add_argument(
        "--env-file",
        default=None,
        help="Optional .env file to update with the created IDs.",
    )
    google_init_parser.set_defaults(handler=handle_google_init_resources)

    google_oauth_parser = google_subparsers.add_parser(
        "oauth-login",
        help="Run the one-time Google OAuth login flow and save the refresh token for HARINA.",
    )
    google_oauth_parser.add_argument(
        "--oauth-client-secret-file",
        default=None,
        help="Path to the OAuth client secret JSON file. Defaults to GOOGLE_OAUTH_CLIENT_SECRET_FILE.",
    )
    google_oauth_parser.add_argument(
        "--oauth-client-json",
        default=None,
        help="Raw OAuth client JSON. Defaults to GOOGLE_OAUTH_CLIENT_JSON.",
    )
    google_oauth_parser.add_argument("--host", default="127.0.0.1", help="Loopback host for the OAuth callback.")
    google_oauth_parser.add_argument("--port", type=int, default=8765, help="Loopback port for the OAuth callback.")
    google_oauth_parser.add_argument(
        "--no-open-browser",
        action="store_false",
        dest="open_browser",
        help="Do not open a browser automatically. Useful when you want to drive an existing Chrome session yourself.",
    )
    google_oauth_parser.add_argument(
        "--env-file",
        default=None,
        help="Optional .env file to update with the OAuth client path and refresh token.",
    )
    google_oauth_parser.set_defaults(handler=handle_google_oauth_login, open_browser=True)

    google_oauth_start_parser = google_subparsers.add_parser(
        "oauth-start",
        help="Generate an OAuth authorization URL and save a local session file for later completion.",
    )
    google_oauth_start_parser.add_argument(
        "--oauth-client-secret-file",
        default=None,
        help="Path to the OAuth client secret JSON file. Defaults to GOOGLE_OAUTH_CLIENT_SECRET_FILE.",
    )
    google_oauth_start_parser.add_argument(
        "--oauth-client-json",
        default=None,
        help="Raw OAuth client JSON. Defaults to GOOGLE_OAUTH_CLIENT_JSON.",
    )
    google_oauth_start_parser.add_argument("--host", default="127.0.0.1", help="Loopback host for the redirect URI.")
    google_oauth_start_parser.add_argument("--port", type=int, default=8765, help="Loopback port for the redirect URI.")
    google_oauth_start_parser.add_argument(
        "--session-file",
        default=".harina-google-oauth-session.json",
        help="Path to the temporary OAuth session file.",
    )
    google_oauth_start_parser.set_defaults(handler=handle_google_oauth_start)

    google_oauth_finish_parser = google_subparsers.add_parser(
        "oauth-finish",
        help="Exchange the OAuth redirect URL for a refresh token using a saved session file.",
    )
    google_oauth_finish_parser.add_argument(
        "--session-file",
        default=".harina-google-oauth-session.json",
        help="Path to the temporary OAuth session file created by oauth-start.",
    )
    google_oauth_finish_parser.add_argument(
        "--redirect-url",
        required=True,
        help="The full redirect URL that contains the authorization code.",
    )
    google_oauth_finish_parser.add_argument(
        "--oauth-client-secret-file",
        default=None,
        help="Path to the OAuth client secret JSON file. Defaults to GOOGLE_OAUTH_CLIENT_SECRET_FILE.",
    )
    google_oauth_finish_parser.add_argument(
        "--oauth-client-json",
        default=None,
        help="Raw OAuth client JSON. Defaults to GOOGLE_OAUTH_CLIENT_JSON.",
    )
    google_oauth_finish_parser.add_argument(
        "--env-file",
        default=None,
        help="Optional .env file to update with the OAuth client path and refresh token.",
    )
    google_oauth_finish_parser.set_defaults(handler=handle_google_oauth_finish)

    return parser


def handle_bot_run(args: Namespace, settings: Settings | None) -> None:
    del args
    if settings is None:
        raise RuntimeError("Bot settings were not loaded.")
    bot = ReceiptBot(settings=settings)
    bot.run(settings.discord_token, log_handler=None)


def handle_bot_upload_test(args: Namespace, settings: Settings | None) -> None:
    if settings is None:
        raise RuntimeError("Bot settings were not loaded.")
    channel_id = args.channel_id or settings.discord_test_channel_id
    if channel_id is None:
        raise RuntimeError("Set --channel-id or DISCORD_TEST_CHANNEL_ID before running upload-test.")
    summary = asyncio.run(
        run_discord_upload_test(
            settings=settings,
            channel_id=channel_id,
            image_path=Path(args.image),
            caption=args.caption,
            timeout_seconds=args.timeout_seconds,
        )
    )
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def handle_dataset_download(args: Namespace, settings: Settings | None) -> None:
    del settings
    output_dir = args.output_dir or os.getenv("DISCORD_DATASET_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))
    summary = asyncio.run(
        run_downloader(
            Namespace(
                channel_url=args.channel_url,
                output_dir=output_dir,
                limit=args.limit,
                include_bots=args.include_bots,
                overwrite=args.overwrite,
            )
        )
    )
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def handle_dataset_smoke_test(args: Namespace, settings: Settings | None) -> None:
    del settings
    dataset_dir = args.dataset_dir or os.getenv("DISCORD_DATASET_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))
    summary = asyncio.run(
        run_smoke_test(
            Namespace(
                dataset_dir=dataset_dir,
                limit=args.limit,
                allow_duplicates=args.allow_duplicates,
                output=args.output,
            )
        )
    )
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def handle_google_init_resources(args: Namespace, settings: Settings | None) -> None:
    del settings
    service_account_key_file = args.service_account_key_file or os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_FILE")
    service_account_json = args.service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    oauth_client_secret_file = args.oauth_client_secret_file or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE")
    oauth_client_json = args.oauth_client_json or os.getenv("GOOGLE_OAUTH_CLIENT_JSON")
    oauth_refresh_token = args.oauth_refresh_token or os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN")

    service_account_info = (
        load_service_account_info(
            service_account_json=service_account_json,
            service_account_key_file=service_account_key_file,
        )
        if service_account_json or service_account_key_file
        else None
    )
    oauth_client_info = (
        load_oauth_client_info(
            oauth_client_json=oauth_client_json,
            oauth_client_secret_file=oauth_client_secret_file,
        )
        if oauth_refresh_token and (oauth_client_json or oauth_client_secret_file)
        else None
    )
    credentials = build_google_credentials(
        service_account_info=service_account_info,
        oauth_client_info=oauth_client_info,
        oauth_refresh_token=oauth_refresh_token,
    )

    bootstrapper = GoogleResourceBootstrapper(credentials=credentials)
    try:
        result = bootstrapper.bootstrap(
            folder_name=args.folder_name,
            spreadsheet_title=args.spreadsheet_title,
            sheet_name=args.sheet_name,
            share_with_email=args.share_with_email,
        )
    except HttpError as exc:
        if "storageQuotaExceeded" in str(exc) or "Service Accounts do not have storage quota" in str(exc):
            raise RuntimeError(
                "Google rejected the request because service accounts do not have storage quota on personal My Drive. "
                "Use a Google Workspace shared drive or switch HARINA to OAuth refresh-token credentials."
            ) from exc
        raise

    env_updates = build_google_env_updates(
        drive_folder_id=result.folder_id,
        drive_folder_url=result.folder_url,
        spreadsheet_id=result.spreadsheet_id,
        spreadsheet_url=result.spreadsheet_url,
        sheet_name=result.sheet_name,
        service_account_key_file=Path(service_account_key_file).as_posix() if service_account_key_file else None,
        oauth_client_secret_file=Path(oauth_client_secret_file).as_posix() if oauth_client_secret_file else None,
        oauth_refresh_token=oauth_refresh_token,
    )

    if args.env_file:
        upsert_env_file(Path(args.env_file), env_updates)

    summary = result.as_dict()
    summary["env_updates"] = env_updates
    if args.env_file:
        summary["env_file"] = str(Path(args.env_file))

    print(json.dumps(summary, ensure_ascii=True, indent=2))


def handle_google_oauth_login(args: Namespace, settings: Settings | None) -> None:
    del settings
    oauth_client_secret_file = args.oauth_client_secret_file or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE")
    oauth_client_json = args.oauth_client_json or os.getenv("GOOGLE_OAUTH_CLIENT_JSON")
    oauth_client_info = load_oauth_client_info(
        oauth_client_json=oauth_client_json,
        oauth_client_secret_file=oauth_client_secret_file,
    )

    result = run_oauth_login(
        oauth_client_info=oauth_client_info,
        host=args.host,
        port=args.port,
        open_browser=args.open_browser,
    )

    env_updates = {
        "GOOGLE_OAUTH_REFRESH_TOKEN": result.refresh_token,
    }
    if oauth_client_secret_file:
        env_updates["GOOGLE_OAUTH_CLIENT_SECRET_FILE"] = Path(oauth_client_secret_file).as_posix()
    if oauth_client_json:
        env_updates["GOOGLE_OAUTH_CLIENT_JSON"] = oauth_client_json

    if args.env_file:
        upsert_env_file(Path(args.env_file), env_updates)

    summary = result.as_dict()
    summary["env_updates"] = env_updates
    if args.env_file:
        summary["env_file"] = str(Path(args.env_file))

    print(json.dumps(summary, ensure_ascii=True, indent=2))


def handle_google_oauth_start(args: Namespace, settings: Settings | None) -> None:
    del settings
    oauth_client_secret_file = args.oauth_client_secret_file or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE")
    oauth_client_json = args.oauth_client_json or os.getenv("GOOGLE_OAUTH_CLIENT_JSON")
    oauth_client_info = load_oauth_client_info(
        oauth_client_json=oauth_client_json,
        oauth_client_secret_file=oauth_client_secret_file,
    )

    result = start_oauth_login(
        oauth_client_info=oauth_client_info,
        host=args.host,
        port=args.port,
        session_file=Path(args.session_file),
    )
    print(json.dumps(result.as_dict(), ensure_ascii=True, indent=2))


def handle_google_oauth_finish(args: Namespace, settings: Settings | None) -> None:
    del settings
    oauth_client_secret_file = args.oauth_client_secret_file or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE")
    oauth_client_json = args.oauth_client_json or os.getenv("GOOGLE_OAUTH_CLIENT_JSON")
    result = finish_oauth_login(
        session_file=Path(args.session_file),
        redirect_url=args.redirect_url,
    )

    env_updates = {
        "GOOGLE_OAUTH_REFRESH_TOKEN": result.refresh_token,
    }
    if oauth_client_secret_file:
        env_updates["GOOGLE_OAUTH_CLIENT_SECRET_FILE"] = Path(oauth_client_secret_file).as_posix()
    if oauth_client_json:
        env_updates["GOOGLE_OAUTH_CLIENT_JSON"] = oauth_client_json

    if args.env_file:
        upsert_env_file(Path(args.env_file), env_updates)

    summary = result.as_dict()
    summary["env_updates"] = env_updates
    if args.env_file:
        summary["env_file"] = str(Path(args.env_file))

    print(json.dumps(summary, ensure_ascii=True, indent=2))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = load_settings() if args.command == "bot" else None
    args.handler(args, settings)


if __name__ == "__main__":
    main()
