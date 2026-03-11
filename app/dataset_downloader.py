from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePath
from typing import Any

import discord
from dotenv import load_dotenv

from app.formatters import is_image_attachment, sanitize_segment


load_dotenv()


CHANNEL_URL_RE = re.compile(
    r"^https://discord\.com/channels/(?P<guild_id>@me|\d+)/(?P<channel_id>\d+)(?:/(?P<message_id>\d+))?/?$"
)
JAPANESE_TEXT_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")
DEFAULT_OUTPUT_DIR = Path("dataset/discord-images")


@dataclass(frozen=True)
class ChannelReference:
    guild_id: int | None
    channel_id: int
    message_id: int | None = None


@dataclass(frozen=True)
class DownloadRecord:
    guild_id: int | None
    guild_name: str | None
    channel_id: int
    channel_name: str | None
    message_id: int
    message_url: str
    author_id: int
    author_name: str
    created_at: str
    attachment_id: int
    filename: str
    content_type: str | None
    size: int
    relative_path: str
    source_url: str


def parse_channel_url(value: str) -> ChannelReference:
    match = CHANNEL_URL_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(
            "Expected a Discord channel URL like https://discord.com/channels/<guild_id>/<channel_id>."
        )

    guild_id_raw = match.group("guild_id")
    guild_id = None if guild_id_raw == "@me" else int(guild_id_raw)
    message_id_raw = match.group("message_id")
    return ChannelReference(
        guild_id=guild_id,
        channel_id=int(match.group("channel_id")),
        message_id=int(message_id_raw) if message_id_raw else None,
    )


def build_attachment_path(
    *,
    output_dir: Path,
    reference: ChannelReference,
    guild_name: str | None,
    channel_name: str | None,
    message_id: int,
    attachment_id: int,
    filename: str,
) -> Path:
    safe_filename = PurePath(filename).name or f"attachment-{attachment_id}"
    guild_segment = build_named_segment("guild", reference.guild_id, guild_name or "dm")
    channel_segment = build_named_segment("channel", reference.channel_id, channel_name)
    return (
        output_dir
        / guild_segment
        / channel_segment
        / f"message-{message_id}"
        / f"attachment-{attachment_id}"
        / safe_filename
    )


def build_named_segment(prefix: str, identifier: int | None, name: str | None) -> str:
    normalized_name = sanitize_segment(skip_japanese_name(name))
    if identifier is None:
        return f"{prefix}-{normalized_name or 'unknown'}"
    if normalized_name:
        return f"{prefix}-{normalized_name}-{identifier}"
    return f"{prefix}-{identifier}"


def skip_japanese_name(name: str | None) -> str:
    if not name:
        return ""
    return "" if JAPANESE_TEXT_RE.search(name) else name


def build_metadata_path(output_dir: Path) -> Path:
    return output_dir / "metadata.jsonl"


def write_metadata(*, output_dir: Path, records: list[DownloadRecord]) -> Path:
    metadata_path = build_metadata_path(output_dir)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(record), ensure_ascii=False) for record in records]
    metadata_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return metadata_path


def parse_args() -> argparse.Namespace:
    default_output_dir = Path(os.getenv("DISCORD_DATASET_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))
    parser = argparse.ArgumentParser(
        description="Download image attachments from a Discord channel into a local dataset."
    )
    parser.add_argument(
        "channel_url",
        help="Discord channel URL like https://discord.com/channels/<guild_id>/<channel_id>",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_output_dir),
        help=f"Directory where the dataset will be stored. Default: {default_output_dir}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of messages to scan. By default, scans the whole visible history.",
    )
    parser.add_argument(
        "--include-bots",
        action="store_true",
        help="Include attachments posted by bot accounts.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite files that already exist in the dataset directory.",
    )
    return parser.parse_args()


class DatasetDownloader(discord.Client):
    def __init__(
        self,
        *,
        reference: ChannelReference,
        output_dir: Path,
        limit: int | None,
        include_bots: bool,
        overwrite: bool,
    ) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True

        super().__init__(intents=intents)

        self.reference = reference
        self.output_dir = output_dir
        self.limit = limit
        self.include_bots = include_bots
        self.overwrite = overwrite
        self.records: list[DownloadRecord] = []
        self.downloaded_count = 0
        self.skipped_count = 0
        self.scanned_messages = 0
        self.run_error: Exception | None = None
        self.metadata_path: Path | None = None

    async def on_ready(self) -> None:
        try:
            await self._run_download()
        except Exception as exc:  # noqa: BLE001
            self.run_error = exc
        finally:
            await self.close()

    async def _run_download(self) -> None:
        channel = await self.fetch_channel(self.reference.channel_id)
        if self.reference.guild_id is not None:
            channel_guild = getattr(channel, "guild", None)
            actual_guild_id = getattr(channel_guild, "id", None)
            if actual_guild_id is not None and actual_guild_id != self.reference.guild_id:
                raise RuntimeError(
                    f"Channel URL guild ID {self.reference.guild_id} does not match actual guild ID {actual_guild_id}."
                )

        if self.reference.message_id is not None:
            if not hasattr(channel, "fetch_message"):
                raise RuntimeError("This channel type does not support fetching individual messages.")
            message = await channel.fetch_message(self.reference.message_id)
            self.scanned_messages = 1
            await self._collect_message_attachments(message)
        else:
            if not hasattr(channel, "history"):
                raise RuntimeError("This channel type does not support history downloads.")
            async for message in channel.history(limit=self.limit, oldest_first=True):
                self.scanned_messages += 1
                await self._collect_message_attachments(message)

        self.metadata_path = write_metadata(output_dir=self.output_dir, records=self.records)

    async def _collect_message_attachments(self, message: discord.Message) -> None:
        if message.author.bot and not self.include_bots:
            return

        image_attachments = [attachment for attachment in message.attachments if is_image_attachment(attachment)]
        for attachment in image_attachments:
            target_path = build_attachment_path(
                output_dir=self.output_dir,
                reference=self.reference,
                guild_name=getattr(message.guild, "name", None),
                channel_name=getattr(message.channel, "name", None),
                message_id=message.id,
                attachment_id=attachment.id,
                filename=attachment.filename,
            )
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if target_path.exists() and not self.overwrite:
                self.skipped_count += 1
            else:
                payload = await attachment.read()
                target_path.write_bytes(payload)
                self.downloaded_count += 1

            self.records.append(
                DownloadRecord(
                    guild_id=getattr(message.guild, "id", None),
                    guild_name=getattr(message.guild, "name", None),
                    channel_id=message.channel.id,
                    channel_name=getattr(message.channel, "name", None),
                    message_id=message.id,
                    message_url=message.jump_url,
                    author_id=message.author.id,
                    author_name=getattr(message.author, "global_name", None) or str(message.author),
                    created_at=message.created_at.isoformat(),
                    attachment_id=attachment.id,
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    size=attachment.size,
                    relative_path=target_path.relative_to(self.output_dir).as_posix(),
                    source_url=attachment.url,
                )
            )


async def run_downloader(args: argparse.Namespace) -> dict[str, Any]:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Set DISCORD_TOKEN in your environment or .env before running the downloader.")

    reference = parse_channel_url(args.channel_url)
    downloader = DatasetDownloader(
        reference=reference,
        output_dir=Path(args.output_dir),
        limit=args.limit,
        include_bots=args.include_bots,
        overwrite=args.overwrite,
    )
    await downloader.start(token)

    if downloader.run_error is not None:
        raise downloader.run_error

    return {
        "scanned_messages": downloader.scanned_messages,
        "records": len(downloader.records),
        "downloaded": downloader.downloaded_count,
        "skipped": downloader.skipped_count,
        "output_dir": str(downloader.output_dir.resolve()),
        "metadata_path": str((downloader.metadata_path or build_metadata_path(downloader.output_dir)).resolve()),
    }


def main() -> None:
    args = parse_args()
    summary = asyncio.run(run_downloader(args))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
