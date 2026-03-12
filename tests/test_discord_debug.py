from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import discord

from app.discord_debug import DiscordDebugSession, serialize_message


def test_discord_debug_session_writes_event_and_snapshot(tmp_path: Path) -> None:
    session = DiscordDebugSession.create(base_dir=tmp_path, purpose="Upload Test")

    events_path = session.write_event("started", channel_id=123)
    snapshot_path = session.write_snapshot("sample.json", {"ok": True})

    assert events_path.exists()
    assert snapshot_path.exists()
    payload = json.loads(events_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["event"] == "started"
    assert payload["channel_id"] == 123
    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == {"ok": True}


def test_serialize_message_includes_content_author_and_attachments() -> None:
    guild = SimpleNamespace(id=10, name="Guild")
    channel = SimpleNamespace(
        id=20,
        name="receipts",
        type="text",
        guild=guild,
        parent_id=None,
        jump_url="https://discord.com/channels/10/20",
    )
    author = SimpleNamespace(
        id=30,
        name="Harina",
        display_name="Harina",
        global_name="Harina",
        bot=True,
    )
    attachment = SimpleNamespace(
        id=40,
        filename="receipt.jpg",
        content_type="image/jpeg",
        size=128,
        url="https://cdn.discordapp.com/receipt.jpg",
        proxy_url="https://media.discordapp.net/receipt.jpg",
    )
    message = SimpleNamespace(
        id=50,
        channel=channel,
        author=author,
        content="debug",
        created_at=datetime(2026, 3, 12, 11, 0, tzinfo=UTC),
        edited_at=None,
        jump_url="https://discord.com/channels/10/20/50",
        attachments=[attachment],
        embeds=[discord.Embed(title="Receipt")],
        reference=None,
        thread=None,
    )

    payload = serialize_message(message)

    assert payload["id"] == 50
    assert payload["author"]["id"] == 30
    assert payload["channel"]["id"] == 20
    assert payload["attachments"][0]["filename"] == "receipt.jpg"
    assert payload["embeds"][0]["title"] == "Receipt"
