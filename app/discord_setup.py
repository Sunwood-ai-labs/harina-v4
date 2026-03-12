from __future__ import annotations

from dataclasses import dataclass

import discord

from app.team_intake import TeamMemberSpec


@dataclass(frozen=True, slots=True)
class DiscordProvisionedChannel:
    key: str
    label: str
    channel_id: int
    channel_name: str
    channel_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "channel_url": self.channel_url,
        }


@dataclass(frozen=True, slots=True)
class DiscordTeamProvisionResult:
    guild_id: int
    category_id: int
    category_name: str
    channels: list[DiscordProvisionedChannel]

    def as_dict(self) -> dict[str, object]:
        return {
            "guild_id": self.guild_id,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "channels": [channel.as_dict() for channel in self.channels],
        }


async def ensure_discord_team_channels(
    *,
    guild,
    category_name: str,
    members: list[TeamMemberSpec],
) -> DiscordTeamProvisionResult:
    existing_channels = list(await guild.fetch_channels())
    category = next(
        (
            channel
            for channel in existing_channels
            if _channel_kind(channel) == "category" and channel.name == category_name
        ),
        None,
    )
    if category is None:
        category = await guild.create_category(category_name, reason="HARINA V4 team intake setup")
        existing_channels.append(category)

    provisioned_channels: list[DiscordProvisionedChannel] = []
    for member in members:
        text_channel = next(
            (
                channel
                for channel in existing_channels
                if _channel_kind(channel) == "text"
                and channel.name == member.channel_name
                and getattr(channel, "category_id", None) == category.id
            ),
            None,
        )
        if text_channel is None:
            topic = f"HARINA V4 intake for {member.label} ({member.key})"
            text_channel = await guild.create_text_channel(
                member.channel_name,
                category=category,
                topic=topic,
                reason="HARINA V4 team intake setup",
            )
            existing_channels.append(text_channel)

        provisioned_channels.append(
            DiscordProvisionedChannel(
                key=member.key,
                label=member.label,
                channel_id=text_channel.id,
                channel_name=text_channel.name,
                channel_url=f"https://discord.com/channels/{guild.id}/{text_channel.id}",
            )
        )

    return DiscordTeamProvisionResult(
        guild_id=guild.id,
        category_id=category.id,
        category_name=category.name,
        channels=provisioned_channels,
    )


class DiscordTeamProvisionClient(discord.Client):
    def __init__(self, *, guild_id: int, category_name: str, members: list[TeamMemberSpec]) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)
        self.guild_id = guild_id
        self.category_name = category_name
        self.members = members
        self.result: DiscordTeamProvisionResult | None = None
        self.run_error: Exception | None = None

    async def on_ready(self) -> None:
        try:
            guild = self.get_guild(self.guild_id)
            if guild is None:
                guild = await self.fetch_guild(self.guild_id)
            self.result = await ensure_discord_team_channels(
                guild=guild,
                category_name=self.category_name,
                members=self.members,
            )
        except Exception as exc:  # noqa: BLE001
            self.run_error = exc
        finally:
            await self.close()


async def run_discord_team_setup(
    *,
    token: str,
    guild_id: int,
    category_name: str,
    members: list[TeamMemberSpec],
) -> DiscordTeamProvisionResult:
    client = DiscordTeamProvisionClient(guild_id=guild_id, category_name=category_name, members=members)
    await client.start(token)

    if client.run_error is not None:
        raise client.run_error
    if client.result is None:
        raise RuntimeError("Discord team setup did not produce a result.")
    return client.result


def _channel_kind(channel) -> str:
    channel_type = getattr(channel, "type", "")
    return str(channel_type)
