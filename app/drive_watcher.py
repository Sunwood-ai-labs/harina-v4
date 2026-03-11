from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from io import BytesIO

import discord

from app.config import Settings
from app.formatters import build_drive_receipt_context, build_receipt_row, format_receipt_summary
from app.gemini_client import GeminiReceiptExtractor
from app.google_workspace import DriveImageFile, GoogleWorkspaceClient


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DriveWatchScanSummary:
    scanned: int = 0
    processed: int = 0
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
        source_folder_id: str,
        processed_folder_id: str,
    ) -> None:
        self.gemini = gemini
        self.google_workspace = google_workspace
        self.notifier = notifier
        self.source_folder_id = source_folder_id
        self.processed_folder_id = processed_folder_id

    async def ensure_receipt_sheet(self) -> None:
        await self.google_workspace.ensure_receipt_sheet()

    async def scan_once(self) -> DriveWatchScanSummary:
        files = await self.google_workspace.list_image_files(folder_id=self.source_folder_id)
        summary = DriveWatchScanSummary(scanned=len(files))

        for drive_file in files:
            try:
                await self._process_file(drive_file)
            except Exception:  # noqa: BLE001
                summary.failed += 1
                logger.exception("Drive watcher failed for file %s", drive_file.file_id)
                continue

            summary.processed += 1
            summary.notified += 1
            summary.moved += 1

        return summary

    async def _process_file(self, drive_file: DriveImageFile) -> None:
        image_bytes = await self.google_workspace.download_file(file_id=drive_file.file_id)
        extraction = await self.gemini.extract(
            image_bytes=image_bytes,
            mime_type=drive_file.mime_type,
            filename=drive_file.name,
        )

        row = build_receipt_row(
            context=build_drive_receipt_context(
                file_id=drive_file.file_id,
                file_name=drive_file.name,
                file_url=drive_file.web_view_link,
            ),
            extraction=extraction,
            drive_file_id=drive_file.file_id,
            drive_file_url=drive_file.web_view_link,
        )
        await self.google_workspace.append_receipt_row(row)

        summary = format_receipt_summary(extraction, drive_file.web_view_link)
        await self.notifier.send_receipt_notification(
            file_name=drive_file.name,
            image_bytes=image_bytes,
            summary=summary,
            drive_file_url=drive_file.web_view_link,
        )
        await self.google_workspace.move_file(
            file_id=drive_file.file_id,
            destination_folder_id=self.processed_folder_id,
        )


class DriveWatcherClient(discord.Client):
    def __init__(self, *, settings: Settings, run_once: bool) -> None:
        intents = discord.Intents.default()
        intents.guilds = True

        super().__init__(intents=intents)

        settings.require_drive_watch()
        self.settings = settings
        self.run_once = run_once
        self.run_error: Exception | None = None
        self.last_summary: DriveWatchScanSummary | None = None
        self._watch_task: asyncio.Task[None] | None = None
        self._notify_channel = settings.discord_notify_channel_id or 0
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
        )
        self.watcher = DriveReceiptWatcher(
            gemini=GeminiReceiptExtractor(
                api_key=settings.require_gemini_api_key(),
                model=settings.gemini_model,
            ),
            google_workspace=workspace,
            notifier=self,
            source_folder_id=settings.google_drive_watch_source_folder_id or "",
            processed_folder_id=settings.google_drive_watch_processed_folder_id or "",
        )

    async def setup_hook(self) -> None:
        await self.watcher.ensure_receipt_sheet()

    async def on_ready(self) -> None:
        if self._watch_task is None:
            self._watch_task = asyncio.create_task(self._run_watch_loop())

    async def send_receipt_notification(
        self,
        *,
        file_name: str,
        image_bytes: bytes,
        summary: str,
        drive_file_url: str | None,
    ) -> None:
        channel = self.get_channel(self._notify_channel)
        if channel is None:
            channel = await self.fetch_channel(self._notify_channel)
        if not hasattr(channel, "send"):
            raise RuntimeError(f"Channel {self._notify_channel} is not messageable.")

        content = f"[Drive Watch] {summary}"
        if drive_file_url:
            content = f"{content}\nDrive: {drive_file_url}"

        await channel.send(
            content=content,
            file=discord.File(BytesIO(image_bytes), filename=file_name),
        )

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


async def run_drive_watch(*, settings: Settings, run_once: bool) -> dict[str, int]:
    client = DriveWatcherClient(settings=settings, run_once=run_once)
    await client.start(settings.require_discord_token())

    if client.run_error is not None:
        raise client.run_error
    if client.last_summary is None:
        raise RuntimeError("Drive watcher did not produce a scan summary.")

    return client.last_summary.as_dict()
