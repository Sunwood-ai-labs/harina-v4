import asyncio
from types import SimpleNamespace

from app.discord_setup import ensure_discord_team_channels
from app.team_intake import build_team_member_spec


class _FakeGuild:
    def __init__(self) -> None:
        self.id = 999
        self._channels: list[SimpleNamespace] = []
        self.created_categories: list[str] = []
        self.created_text_channels: list[tuple[str, int]] = []
        self._next_id = 1000

    async def fetch_channels(self):
        return list(self._channels)

    async def create_category(self, name: str, reason: str):
        del reason
        category = SimpleNamespace(id=self._allocate_id(), name=name, type="category")
        self._channels.append(category)
        self.created_categories.append(name)
        return category

    async def create_text_channel(self, name: str, *, category, topic: str, reason: str):
        del topic, reason
        channel = SimpleNamespace(
            id=self._allocate_id(),
            name=name,
            type="text",
            category_id=category.id,
        )
        self._channels.append(channel)
        self.created_text_channels.append((name, category.id))
        return channel

    def _allocate_id(self) -> int:
        self._next_id += 1
        return self._next_id


def test_ensure_discord_team_channels_creates_missing_category_and_channels() -> None:
    guild = _FakeGuild()

    result = asyncio.run(
        ensure_discord_team_channels(
            guild=guild,
            category_name="HARINA V4",
            members=[build_team_member_spec("Alice"), build_team_member_spec("Bob")],
        )
    )

    assert result.category_name == "HARINA V4"
    assert [channel.key for channel in result.channels] == ["alice", "bob"]
    assert guild.created_categories == ["HARINA V4"]
    assert [name for name, _category_id in guild.created_text_channels] == ["alice", "bob"]


def test_ensure_discord_team_channels_reuses_existing_structure() -> None:
    guild = _FakeGuild()
    category = SimpleNamespace(id=2001, name="HARINA V4", type="category")
    channel = SimpleNamespace(id=2002, name="alice", type="text", category_id=2001)
    guild._channels.extend([category, channel])

    result = asyncio.run(
        ensure_discord_team_channels(
            guild=guild,
            category_name="HARINA V4",
            members=[build_team_member_spec("Alice")],
        )
    )

    assert result.category_id == 2001
    assert result.channels[0].channel_id == 2002
    assert guild.created_categories == []
    assert guild.created_text_channels == []
