from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class TeamMemberSpec:
    key: str
    label: str
    channel_name: str
    source_folder_name: str
    processed_folder_name: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DriveWatchRoute:
    key: str
    label: str
    discord_channel_id: int
    source_folder_id: str
    processed_folder_id: str
    channel_name: str | None = None
    source_folder_url: str | None = None
    processed_folder_url: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def slugify_name(value: str, *, fallback: str = "member") -> str:
    normalized = re.sub(r"[^0-9A-Za-z]+", "-", value.strip()).strip("-").lower()
    return normalized or fallback


def build_team_member_spec(label: str) -> TeamMemberSpec:
    normalized_label = label.strip()
    if not normalized_label:
        raise ValueError("Member label must not be blank.")

    key = slugify_name(normalized_label)
    return TeamMemberSpec(
        key=key,
        label=normalized_label,
        channel_name=key,
        source_folder_name=normalized_label,
        processed_folder_name="_processed",
    )


def parse_drive_watch_routes_json(raw_value: str | None) -> list[DriveWatchRoute]:
    if raw_value is None or not raw_value.strip():
        return []

    loaded = json.loads(raw_value)
    if not isinstance(loaded, list):
        raise ValueError("DRIVE_WATCH_ROUTES_JSON must be a JSON array.")

    routes: list[DriveWatchRoute] = []
    for item in loaded:
        if not isinstance(item, dict):
            raise ValueError("Each drive watch route must be a JSON object.")
        routes.append(
            DriveWatchRoute(
                key=str(item["key"]).strip(),
                label=str(item.get("label") or item["key"]).strip(),
                discord_channel_id=int(item["discord_channel_id"]),
                source_folder_id=str(item["source_folder_id"]).strip(),
                processed_folder_id=str(item["processed_folder_id"]).strip(),
                channel_name=_optional_string(item.get("channel_name")),
                source_folder_url=_optional_string(item.get("source_folder_url")),
                processed_folder_url=_optional_string(item.get("processed_folder_url")),
            )
        )

    return routes


def build_drive_watch_routes_env_value(routes: list[DriveWatchRoute]) -> str:
    return json.dumps([route.as_dict() for route in routes], ensure_ascii=True, separators=(",", ":"))


def _optional_string(value: object) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None
