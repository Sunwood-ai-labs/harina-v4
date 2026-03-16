from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from io import BytesIO

import discord

from app.config import Settings
from app.formatters import (
    build_drive_intake_embed,
    build_drive_receipt_context,
    build_receipt_embed,
    build_receipt_links_view,
    build_receipt_rows,
)
from app.gemini_client import GeminiReceiptExtractor
from app.google_workspace import DriveImageFile, GoogleWorkspaceClient
from app.models import ReceiptExtraction
from app.team_intake import DriveWatchRoute


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DriveWatchScanSummary:
    scanned: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    moved: int = 0
    notified: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


class DriveReceiptWatcher:
    def __init__(
        self,
        *,
        gemini: GeminiReceiptExtractor,
        google_workspace: GoogleWorkspaceClient,
        notifier,
        routes: list[DriveWatchRoute],
        rescan_existing: bool = False,
    ) -> None:
        self.gemini = gemini
        self.google_workspace = google_workspace
        self.notifier = notifier
        self.routes = routes
        self.rescan_existing = rescan_existing

    async def ensure_receipt_sheet(self) -> None:
        await self.google_workspace.ensure_receipt_sheet()

    async def scan_once(self) -> DriveWatchScanSummary:
        summary = DriveWatchScanSummary()
        recorded_attachment_names = set()
        if not self.rescan_existing:
            recorded_attachment_names = await self.google_workspace.list_receipt_attachment_names()

        for route in self.routes:
            files = await self.google_workspace.list_image_files(folder_id=route.source_folder_id)
            summary.scanned += len(files)

            for drive_file in files:
                try:
                    normalized_attachment_name = _normalize_attachment_name(drive_file.name)
                    if (
                        not self.rescan_existing
                        and normalized_attachment_name
                        and normalized_attachment_name in recorded_attachment_names
                    ):
                        logger.info(
                            "Skipping Drive file %s on route %s because attachment name '%s' is already recorded.",
                            drive_file.file_id,
                            route.key,
                            drive_file.name,
                        )
                        await self.google_workspace.move_file(
                            file_id=drive_file.file_id,
                            destination_folder_id=route.processed_folder_id,
                        )
                        summary.skipped += 1
                        summary.moved += 1
                        continue

                    await self._process_file(route, drive_file)
                except Exception:  # noqa: BLE001
                    summary.failed += 1
                    logger.exception("Drive watcher failed for file %s on route %s", drive_file.file_id, route.key)
                    continue

                if normalized_attachment_name:
                    recorded_attachment_names.add(normalized_attachment_name)
                summary.processed += 1
                summary.notified += 1
                summary.moved += 1

        return summary

    async def _process_file(self, route: DriveWatchRoute, drive_file: DriveImageFile) -> None:
        image_bytes = await self.google_workspace.download_file(file_id=drive_file.file_id)
        category_options = await self.google_workspace.list_receipt_categories()
        extraction = await self.gemini.extract(
            image_bytes=image_bytes,
            mime_type=drive_file.mime_type,
            filename=drive_file.name,
            category_options=category_options,
        )
        await self.google_workspace.append_receipt_categories(
            [item.category or "" for item in extraction.line_items],
            source="gemini",
        )

        rows = build_receipt_rows(
            context=build_drive_receipt_context(
                file_id=drive_file.file_id,
                file_name=drive_file.name,
                file_url=drive_file.web_view_link,
                source_name=f"google-drive:{route.key}",
                author_tag=route.label,
            ),
            extraction=extraction,
            drive_file_id=drive_file.file_id,
            drive_file_url=drive_file.web_view_link,
        )

        await self.notifier.send_receipt_notification(
            route=route,
            file_name=drive_file.name,
            image_bytes=image_bytes,
            extraction=extraction,
            drive_file_url=drive_file.web_view_link,
        )
        await self.google_workspace.append_receipt_rows(rows)
        await self.google_workspace.move_file(
            file_id=drive_file.file_id,
            destination_folder_id=route.processed_folder_id,
        )


class DriveWatcherClient(discord.Client):
    def __init__(self, *, settings: Settings, run_once: bool, rescan_existing: bool) -> None:
        intents = discord.Intents.default()
        intents.guilds = True

        super().__init__(intents=intents)

        settings.require_drive_watch()
        self.settings = settings
        self.run_once = run_once
        self.rescan_existing = rescan_existing
        self.run_error: Exception | None = None
        self.last_summary: DriveWatchScanSummary | None = None
        self._watch_task: asyncio.Task[None] | None = None
        self._routes = settings.drive_watch_routes or [
            DriveWatchRoute(
                key="default",
                label="Default Intake",
                discord_channel_id=settings.discord_notify_channel_id or 0,
                source_folder_id=settings.google_drive_watch_source_folder_id or "",
                processed_folder_id=settings.google_drive_watch_processed_folder_id or "",
            )
        ]
        workspace = GoogleWorkspaceClient(
            credentials=settings.google_credentials,
            drive_folder_id=(
                settings.google_drive_folder_id
                or settings.google_drive_watch_processed_folder_id
                or settings.google_drive_watch_source_folder_id
                or ""
            ),
            spreadsheet_id=settings.google_sheets_spreadsheet_id or "",
            sheet_name=settings.google_sheets_sheet_name,
            category_sheet_name=settings.google_sheets_category_sheet_name,
        )
        self.watcher = DriveReceiptWatcher(
            gemini=GeminiReceiptExtractor(
                api_keys=settings.require_gemini_api_keys(),
                model=settings.gemini_model,
            ),
            google_workspace=workspace,
            notifier=self,
            routes=self._routes,
            rescan_existing=rescan_existing,
        )

    async def setup_hook(self) -> None:
        await self.watcher.ensure_receipt_sheet()

    async def on_ready(self) -> None:
        if self._watch_task is None:
            self._watch_task = asyncio.create_task(self._run_watch_loop())

    async def send_receipt_notification(
        self,
        *,
        route: DriveWatchRoute,
        file_name: str,
        image_bytes: bytes,
        extraction: ReceiptExtraction,
        drive_file_url: str | None,
    ) -> None:
        channel = self.get_channel(route.discord_channel_id)
        if channel is None:
            channel = await self.fetch_channel(route.discord_channel_id)
        if not hasattr(channel, "send"):
            raise RuntimeError(f"Channel {route.discord_channel_id} is not messageable.")

        intake_file = discord.File(BytesIO(image_bytes), filename=file_name)
        intake_message = await channel.send(
            file=intake_file,
            embed=build_drive_intake_embed(
                route_label=route.label,
                file_name=file_name,
                drive_file_url=drive_file_url,
                image_url=f"attachment://{file_name}",
            ),
            view=build_receipt_links_view(
                drive_file_url=drive_file_url,
            ),
        )

        result_embed = build_receipt_embed(
            title=f"Drive Receipt // {route.label}",
            extraction=extraction,
            drive_file_url=drive_file_url,
            spreadsheet_url=self.watcher.google_workspace.spreadsheet_url,
            source_label=f"{route.label} / {file_name}",
        )
        view = build_receipt_links_view(
            drive_file_url=drive_file_url,
            spreadsheet_url=self.watcher.google_workspace.spreadsheet_url,
        )

        response_target: discord.abc.Messageable = channel
        try:
            response_target = await intake_message.create_thread(name=f"drive-{route.key}-{intake_message.id}")
        except discord.HTTPException:
            logger.warning("Could not create thread for drive intake message %s", intake_message.id)

        await response_target.send(embed=result_embed, view=view)

    async def _run_watch_loop(self) -> None:
        try:
            while True:
                self.last_summary = await self.watcher.scan_once()
                if self.run_once:
                    return
                await asyncio.sleep(self.settings.drive_poll_interval_seconds)
        except Exception as exc:  # noqa: BLE001
            self.run_error = exc
        finally:
            await self.close()


async def run_drive_watch(*, settings: Settings, run_once: bool, rescan_existing: bool = False) -> dict[str, int]:
    client = DriveWatcherClient(settings=settings, run_once=run_once, rescan_existing=rescan_existing)
    await client.start(settings.require_discord_token())

    if client.run_error is not None:
        raise client.run_error
    if client.last_summary is None:
        raise RuntimeError("Drive watcher did not produce a scan summary.")

    return client.last_summary.as_dict()


def _normalize_attachment_name(value: str) -> str:
    return value.strip().casefold()
