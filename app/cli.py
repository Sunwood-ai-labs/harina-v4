from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from argparse import Namespace
from pathlib import Path

from app.bot import ReceiptBot
from app.config import Settings, load_settings
from app.dataset_downloader import DEFAULT_OUTPUT_DIR, run_downloader
from app.discord_upload_test import run_discord_upload_test
from app.gemini_smoke_test import run_smoke_test


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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = load_settings() if args.command == "bot" else None
    args.handler(args, settings)


if __name__ == "__main__":
    main()
