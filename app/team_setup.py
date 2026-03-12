from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.discord_setup import DiscordTeamProvisionResult, run_discord_team_setup
from app.google_setup import (
    GoogleResourceBootstrapper,
    GoogleTeamDriveWatchBootstrapResult,
    build_team_drive_watch_env_updates,
    upsert_env_file,
)
from app.team_intake import DriveWatchRoute, TeamMemberSpec, build_team_member_spec


@dataclass(frozen=True, slots=True)
class TeamIntakeSetupResult:
    category_name: str
    discord: DiscordTeamProvisionResult
    google: GoogleTeamDriveWatchBootstrapResult
    routes: list[DriveWatchRoute]
    env_updates: dict[str, str]

    def as_dict(self) -> dict[str, object]:
        return {
            "category_name": self.category_name,
            "discord": self.discord.as_dict(),
            "google": self.google.as_dict(),
            "routes": [route.as_dict() for route in self.routes],
            "env_updates": self.env_updates,
        }


def build_team_members(labels: list[str]) -> list[TeamMemberSpec]:
    members = [build_team_member_spec(label) for label in labels]
    if not members:
        raise RuntimeError("Provide at least one --member value.")

    keys = [member.key for member in members]
    if len(keys) != len(set(keys)):
        raise RuntimeError("Member names must resolve to unique keys/channel names.")

    return members


async def run_team_intake_setup(
    *,
    settings: Settings,
    guild_id: int,
    category_name: str,
    member_labels: list[str],
    drive_parent_folder_id: str | None,
    drive_parent_folder_name: str | None,
    share_with_email: str | None,
    poll_interval_seconds: int,
    env_file: Path | None,
) -> dict[str, object]:
    members = build_team_members(member_labels)

    discord_result = await run_discord_team_setup(
        token=settings.require_discord_token(),
        guild_id=guild_id,
        category_name=category_name,
        members=members,
    )

    bootstrapper = GoogleResourceBootstrapper(credentials=settings.google_credentials)
    google_result = bootstrapper.bootstrap_team_drive_watch(
        members=members,
        parent_folder_id=drive_parent_folder_id,
        parent_folder_name=drive_parent_folder_name,
        share_with_email=share_with_email,
    )

    channel_by_key = {channel.key: channel for channel in discord_result.channels}
    google_by_key = {route.key: route for route in google_result.routes}
    routes = [
        DriveWatchRoute(
            key=member.key,
            label=member.label,
            discord_channel_id=channel_by_key[member.key].channel_id,
            channel_name=channel_by_key[member.key].channel_name,
            source_folder_id=google_by_key[member.key].source_folder_id,
            source_folder_url=google_by_key[member.key].source_folder_url,
            processed_folder_id=google_by_key[member.key].processed_folder_id,
            processed_folder_url=google_by_key[member.key].processed_folder_url,
        )
        for member in members
    ]

    env_updates = {
        "DISCORD_CHANNEL_IDS": ",".join(str(channel_by_key[member.key].channel_id) for member in members),
        **build_team_drive_watch_env_updates(
            routes=routes,
            poll_interval_seconds=poll_interval_seconds,
        ),
    }

    if env_file is not None:
        upsert_env_file(env_file, env_updates)

    summary = TeamIntakeSetupResult(
        category_name=category_name,
        discord=discord_result,
        google=google_result,
        routes=routes,
        env_updates=env_updates,
    ).as_dict()
    if env_file is not None:
        summary["env_file"] = str(env_file)
    return summary
