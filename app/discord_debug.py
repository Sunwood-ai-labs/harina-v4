from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import discord

from app.dataset_downloader import ChannelReference


DEFAULT_DISCORD_DEBUG_LOG_DIR = Path("logs/discord")
DEFAULT_HISTORY_LIMIT = 50


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_session_slug(value: str) -> str:
    normalized = "".join(character.lower() if character.isalnum() else "-" for character in value.strip())
    normalized = "-".join(segment for segment in normalized.split("-") if segment)
    return normalized or "session"


def serialize_attachment(attachment: discord.Attachment) -> dict[str, object]:
    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "size": attachment.size,
        "url": attachment.url,
        "proxy_url": attachment.proxy_url,
    }


def serialize_author(author: discord.abc.User) -> dict[str, object]:
    return {
        "id": author.id,
        "name": author.name,
        "display_name": getattr(author, "display_name", author.name),
        "global_name": getattr(author, "global_name", None),
        "bot": author.bot,
    }


def serialize_channel(channel: discord.abc.Snowflake) -> dict[str, object]:
    return {
        "id": getattr(channel, "id", None),
        "name": getattr(channel, "name", None),
        "type": str(getattr(channel, "type", "unknown")),
        "guild_id": getattr(getattr(channel, "guild", None), "id", None),
        "guild_name": getattr(getattr(channel, "guild", None), "name", None),
        "parent_id": getattr(channel, "parent_id", None),
        "jump_url": getattr(channel, "jump_url", None),
    }


def serialize_message(message: discord.Message) -> dict[str, object]:
    return {
        "id": message.id,
        "channel": serialize_channel(message.channel),
        "author": serialize_author(message.author),
        "content": message.content,
        "created_at": message.created_at.isoformat(),
        "edited_at": message.edited_at.isoformat() if message.edited_at else None,
        "jump_url": message.jump_url,
        "attachments": [serialize_attachment(attachment) for attachment in message.attachments],
        "embeds": [embed.to_dict() for embed in message.embeds],
        "reference": {
            "message_id": getattr(message.reference, "message_id", None),
            "channel_id": getattr(message.reference, "channel_id", None),
            "guild_id": getattr(message.reference, "guild_id", None),
        }
        if message.reference
        else None,
        "thread": serialize_channel(message.thread) if message.thread else None,
    }


async def collect_channel_history(
    channel: discord.abc.Messageable,
    *,
    history_limit: int,
) -> list[dict[str, object]]:
    if not hasattr(channel, "history"):
        return []

    messages: list[dict[str, object]] = []
    async for message in channel.history(limit=history_limit, oldest_first=False):
        messages.append(serialize_message(message))
    messages.reverse()
    return messages


async def collect_debug_snapshot(
    *,
    client: discord.Client,
    channel_id: int,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    message_id: int | None = None,
    thread_id: int | None = None,
) -> dict[str, object]:
    channel = await client.fetch_channel(channel_id)
    snapshot: dict[str, object] = {
        "collected_at": utc_timestamp(),
        "channel": serialize_channel(channel),
        "channel_messages": await collect_channel_history(channel, history_limit=history_limit),
    }

    focus_message: discord.Message | None = None
    if message_id is not None and hasattr(channel, "fetch_message"):
        focus_message = await channel.fetch_message(message_id)
        snapshot["focus_message"] = serialize_message(focus_message)
        if thread_id is None and focus_message.thread is not None:
            thread_id = focus_message.thread.id

    if thread_id is not None:
        thread_channel = await client.fetch_channel(thread_id)
        snapshot["thread"] = serialize_channel(thread_channel)
        snapshot["thread_messages"] = await collect_channel_history(thread_channel, history_limit=history_limit)

    return snapshot


@dataclass(frozen=True)
class DiscordDebugSession:
    session_dir: Path
    events_path: Path
    snapshots_dir: Path

    @classmethod
    def create(cls, *, base_dir: Path, purpose: str) -> "DiscordDebugSession":
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        session_dir = base_dir / f"{timestamp}-{build_session_slug(purpose)}"
        snapshots_dir = session_dir / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        events_path = session_dir / "events.jsonl"
        return cls(session_dir=session_dir, events_path=events_path, snapshots_dir=snapshots_dir)

    def write_event(self, event: str, **data: Any) -> Path:
        payload = {"timestamp": utc_timestamp(), "event": event, **data}
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return self.events_path

    def write_snapshot(self, name: str, payload: dict[str, Any]) -> Path:
        target_path = self.snapshots_dir / name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return target_path


class DiscordLogCollectorClient(discord.Client):
    def __init__(
        self,
        *,
        reference: ChannelReference,
        history_limit: int,
        session: DiscordDebugSession,
    ) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True

        super().__init__(intents=intents)

        self.reference = reference
        self.history_limit = history_limit
        self.session = session
        self.snapshot_path: Path | None = None
        self.run_error: Exception | None = None

    async def on_ready(self) -> None:
        try:
            self.session.write_event(
                "collector_started",
                channel_id=self.reference.channel_id,
                message_id=self.reference.message_id,
                history_limit=self.history_limit,
            )
            snapshot = await collect_debug_snapshot(
                client=self,
                channel_id=self.reference.channel_id,
                history_limit=self.history_limit,
                message_id=self.reference.message_id,
            )
            self.snapshot_path = self.session.write_snapshot("collected-history.json", snapshot)
            self.session.write_event("collector_completed", snapshot_path=str(self.snapshot_path.resolve()))
        except Exception as exc:  # noqa: BLE001
            self.run_error = exc
            self.session.write_event("collector_failed", error=repr(exc))
        finally:
            await self.close()


async def collect_discord_logs(
    *,
    token: str,
    reference: ChannelReference,
    output_dir: Path,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> dict[str, object]:
    session = DiscordDebugSession.create(
        base_dir=output_dir,
        purpose=f"collect-{reference.channel_id}-{reference.message_id or 'channel'}",
    )
    client = DiscordLogCollectorClient(reference=reference, history_limit=history_limit, session=session)
    await client.start(token)

    if client.run_error is not None:
        raise client.run_error

    return {
        "output_dir": str(session.session_dir.resolve()),
        "events_path": str(session.events_path.resolve()),
        "snapshot_path": str((client.snapshot_path or session.snapshots_dir / "collected-history.json").resolve()),
        "history_limit": history_limit,
        "channel_id": reference.channel_id,
        "message_id": reference.message_id,
    }
