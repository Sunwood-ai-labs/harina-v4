from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from io import BytesIO

import discord
from discord import app_commands

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
WATCHER_EXHAUSTED_KEYS_RETRY_DELAY_SECONDS = 60 * 60 * 12
WATCHER_EXHAUSTED_KEYS_RETRY_COUNT = 1


@dataclass(slots=True)
class DriveWatchWaitState:
    reason: str
    started_at: float
    ends_at: float

    @property
    def remaining_seconds(self) -> int:
        return max(int(self.ends_at - self.started_at), 0)


@dataclass(slots=True)
class DriveWatchResumeResult:
    was_waiting: bool
    reason: str | None
    remaining_seconds: int
    will_skip_next_wait: bool


class DriveWatchResumeController:
    def __init__(self) -> None:
        self._resume_pending = False
        self._wait_event: asyncio.Event | None = None
        self._wait_state: DriveWatchWaitState | None = None

    async def sleep(self, delay_seconds: float, *, reason: str) -> bool:
        if delay_seconds <= 0:
            return False

        if self._resume_pending:
            self._resume_pending = False
            return True

        loop = asyncio.get_running_loop()
        wait_event = asyncio.Event()
        self._wait_event = wait_event
        self._wait_state = DriveWatchWaitState(
            reason=reason,
            started_at=loop.time(),
            ends_at=loop.time() + delay_seconds,
        )

        if self._resume_pending:
            self._resume_pending = False
            wait_event.set()

        try:
            try:
                await asyncio.wait_for(wait_event.wait(), timeout=delay_seconds)
                return True
            except asyncio.TimeoutError:
                return False
        finally:
            if self._wait_event is wait_event:
                self._wait_event = None
                self._wait_state = None

    def request_resume(self) -> DriveWatchResumeResult:
        snapshot = self.snapshot()
        if self._wait_event is not None:
            self._wait_event.set()
            will_skip_next_wait = False
        else:
            self._resume_pending = True
            will_skip_next_wait = True
        return DriveWatchResumeResult(
            was_waiting=snapshot is not None,
            reason=snapshot.reason if snapshot is not None else None,
            remaining_seconds=snapshot.remaining_seconds if snapshot is not None else 0,
            will_skip_next_wait=will_skip_next_wait,
        )

    def snapshot(self) -> DriveWatchWaitState | None:
        state = self._wait_state
        if state is None:
            return None

        loop = asyncio.get_running_loop()
        return DriveWatchWaitState(
            reason=state.reason,
            started_at=loop.time(),
            ends_at=state.ends_at,
        )


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

    def has_activity(self) -> bool:
        return any(value > 0 for value in self.as_dict().values())


@dataclass(slots=True)
class DriveWatchCycleSummaryState:
    last_signature: tuple[int, int, int, int, int, int, int, tuple[str, ...]] | None = None

    def should_notify(
        self,
        *,
        summary: DriveWatchScanSummary,
        backlog_total: int,
        backlog_lines: list[str],
    ) -> bool:
        if summary.has_activity():
            return True
        return self.last_signature != self.build_signature(
            summary=summary,
            backlog_total=backlog_total,
            backlog_lines=backlog_lines,
        )

    def remember(
        self,
        *,
        summary: DriveWatchScanSummary,
        backlog_total: int,
        backlog_lines: list[str],
    ) -> None:
        self.last_signature = self.build_signature(
            summary=summary,
            backlog_total=backlog_total,
            backlog_lines=backlog_lines,
        )

    @staticmethod
    def build_signature(
        *,
        summary: DriveWatchScanSummary,
        backlog_total: int,
        backlog_lines: list[str],
    ) -> tuple[int, int, int, int, int, int, int, tuple[str, ...]]:
        return (
            summary.scanned,
            summary.processed,
            summary.skipped,
            summary.failed,
            summary.moved,
            summary.notified,
            backlog_total,
            tuple(backlog_lines),
        )


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

            for file_index, drive_file in enumerate(files, start=1):
                remaining_in_route = max(len(files) - file_index, 0)
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
                        destination_folder_id = await self.google_workspace.ensure_receipt_storage_folder(
                            root_folder_id=route.processed_folder_id,
                            date_hint=drive_file.created_time,
                        )
                        await self.google_workspace.move_file(
                            file_id=drive_file.file_id,
                            destination_folder_id=destination_folder_id,
                        )
                        summary.skipped += 1
                        summary.moved += 1
                        await self._emit_progress(
                            route=route,
                            status="skipped",
                            file_name=drive_file.name,
                            summary=summary,
                            remaining_in_route=remaining_in_route,
                        )
                        continue

                    await self._process_file(route, drive_file)
                except Exception as exc:  # noqa: BLE001
                    summary.failed += 1
                    logger.exception("Drive watcher failed for file %s on route %s", drive_file.file_id, route.key)
                    await self._emit_progress(
                        route=route,
                        status="failed",
                        file_name=drive_file.name,
                        summary=summary,
                        remaining_in_route=remaining_in_route,
                        error_message=str(exc),
                    )
                    continue

                if normalized_attachment_name:
                    recorded_attachment_names.add(normalized_attachment_name)
                summary.processed += 1
                summary.notified += 1
                summary.moved += 1
                await self._emit_progress(
                    route=route,
                    status="processed",
                    file_name=drive_file.name,
                    summary=summary,
                    remaining_in_route=remaining_in_route,
                )

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
        destination_folder_id = await self.google_workspace.ensure_receipt_storage_folder(
            root_folder_id=route.processed_folder_id,
            date_hint=extraction.purchase_date or drive_file.created_time,
        )
        await self.google_workspace.move_file(
            file_id=drive_file.file_id,
            destination_folder_id=destination_folder_id,
        )

    async def _emit_progress(
        self,
        *,
        route: DriveWatchRoute,
        status: str,
        file_name: str,
        summary: DriveWatchScanSummary,
        remaining_in_route: int,
        error_message: str | None = None,
    ) -> None:
        send_progress = getattr(self.notifier, "send_system_progress", None)
        if send_progress is None:
            return

        try:
            await send_progress(
                route=route,
                status=status,
                file_name=file_name,
                summary=summary,
                remaining_in_route=remaining_in_route,
                error_message=error_message,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Drive watcher could not send a system progress update for %s on route %s",
                file_name,
                route.key,
            )


class DriveWatcherClient(discord.Client):
    def __init__(self, *, settings: Settings, run_once: bool, rescan_existing: bool) -> None:
        intents = discord.Intents.default()
        intents.guilds = True

        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

        settings.require_drive_watch()
        self.settings = settings
        self.run_once = run_once
        self.rescan_existing = rescan_existing
        self.run_error: Exception | None = None
        self.last_summary: DriveWatchScanSummary | None = None
        self._watch_task: asyncio.Task[None] | None = None
        self._commands_synced = False
        self._cycle_summary_state = DriveWatchCycleSummaryState()
        self._resume_controller = DriveWatchResumeController()
        self._scan_lock = asyncio.Lock()
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
                model=settings.production_gemini_model,
                exhausted_keys_retry_delay_seconds=WATCHER_EXHAUSTED_KEYS_RETRY_DELAY_SECONDS,
                exhausted_keys_retry_count=WATCHER_EXHAUSTED_KEYS_RETRY_COUNT,
                sleep_func=self._sleep_for_watcher_wait,
                exhausted_keys_wait_callback=self.send_system_wait,
            ),
            google_workspace=workspace,
            notifier=self,
            routes=self._routes,
            rescan_existing=rescan_existing,
        )
        self._register_app_commands()

    async def setup_hook(self) -> None:
        await self.watcher.ensure_receipt_sheet()

    async def on_ready(self) -> None:
        if not self._commands_synced:
            await self._sync_app_commands()
            self._commands_synced = True
        if self._watch_task is None:
            await self.send_system_startup()
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
        channel = await self._resolve_messageable_channel(route.discord_channel_id)

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
            gemini_usage=extraction.gemini_usage,
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

    async def send_system_startup(self) -> None:
        if self.settings.discord_system_log_channel_id is None:
            return

        backlog_total, backlog_lines = await self._build_backlog_snapshot()
        embed = discord.Embed(
            title="HARINA Drive Watch Restarted",
            description="Drive watcher を起動し、system log 配信を開始しました。",
            color=discord.Color.from_rgb(52, 152, 219),
        )
        embed.add_field(name="Poll Interval", value=f"{self.settings.drive_poll_interval_seconds} sec", inline=True)
        embed.add_field(name="Routes", value=str(len(self._routes)), inline=True)
        embed.add_field(name="Remaining Total", value=str(backlog_total), inline=True)
        if backlog_lines:
            embed.add_field(name="Current Backlog", value="\n".join(backlog_lines), inline=False)
        await self._send_system_log_embed(embed)
        self._cycle_summary_state.remember(
            summary=DriveWatchScanSummary(),
            backlog_total=backlog_total,
            backlog_lines=backlog_lines,
        )

    async def send_system_progress(
        self,
        *,
        route: DriveWatchRoute,
        status: str,
        file_name: str,
        summary: DriveWatchScanSummary,
        remaining_in_route: int,
        error_message: str | None = None,
    ) -> None:
        if self.settings.discord_system_log_channel_id is None:
            return

        color_by_status = {
            "processed": discord.Color.green(),
            "skipped": discord.Color.gold(),
            "failed": discord.Color.red(),
        }
        description_by_status = {
            "processed": "画像を処理して Discord / Sheets / Drive へ反映しました。",
            "skipped": "attachmentName 重複のためスキップしました。",
            "failed": "画像の処理中にエラーが発生しました。",
        }
        embed = discord.Embed(
            title=f"HARINA Progress // {route.label}",
            description=description_by_status.get(status, "Drive watcher の進捗を更新しました。"),
            color=color_by_status.get(status, discord.Color.blurple()),
        )
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="File", value=file_name, inline=True)
        embed.add_field(name="Route Remaining", value=str(remaining_in_route), inline=True)
        embed.add_field(
            name="Totals",
            value=f"processed={summary.processed} skipped={summary.skipped} failed={summary.failed} moved={summary.moved}",
            inline=False,
        )
        if error_message:
            embed.add_field(name="Error", value=error_message[:1024], inline=False)
        await self._send_system_log_embed(embed)

    async def send_system_cycle_summary(self, summary: DriveWatchScanSummary) -> None:
        if self.settings.discord_system_log_channel_id is None:
            return
        backlog_total, backlog_lines = await self._build_backlog_snapshot()
        if not self._cycle_summary_state.should_notify(
            summary=summary,
            backlog_total=backlog_total,
            backlog_lines=backlog_lines,
        ):
            logger.debug("Skipping Drive watcher cycle summary because there was no observable change.")
            return
        embed = discord.Embed(
            title="HARINA Scan Summary",
            description="Drive watcher の scan cycle が完了しました。",
            color=discord.Color.from_rgb(155, 89, 182),
        )
        embed.add_field(name="Scanned", value=str(summary.scanned), inline=True)
        embed.add_field(name="Processed", value=str(summary.processed), inline=True)
        embed.add_field(name="Skipped", value=str(summary.skipped), inline=True)
        embed.add_field(name="Failed", value=str(summary.failed), inline=True)
        embed.add_field(name="Moved", value=str(summary.moved), inline=True)
        embed.add_field(name="Notified", value=str(summary.notified), inline=True)
        embed.add_field(name="Remaining Total", value=str(backlog_total), inline=True)
        if backlog_lines:
            embed.add_field(name="Current Backlog", value="\n".join(backlog_lines), inline=False)
        await self._send_system_log_embed(embed)
        self._cycle_summary_state.remember(
            summary=summary,
            backlog_total=backlog_total,
            backlog_lines=backlog_lines,
        )

    async def send_system_error(self, error: Exception) -> None:
        if self.settings.discord_system_log_channel_id is None:
            return

        embed = discord.Embed(
            title="HARINA Watcher Error",
            description="Drive watcher が停止しました。",
            color=discord.Color.red(),
        )
        embed.add_field(name="Error", value=str(error)[:1024], inline=False)
        await self._send_system_log_embed(embed)

    async def send_system_wait(self, event: dict[str, object]) -> None:
        if self.settings.discord_system_log_channel_id is None:
            return

        retry_delay_seconds = int(event.get("retry_delay_seconds", 0) or 0)
        retry_hours = retry_delay_seconds // 3600 if retry_delay_seconds else 0
        request_name = str(event.get("request_name") or "Gemini request")
        filename = str(event.get("filename") or "")
        key_count = int(event.get("key_count", 0) or 0)

        embed = discord.Embed(
            title="HARINA Watch Status",
            description="Gemini の全ローテーションキーが上限に達したため、watcher は待機中です。",
            color=discord.Color.red(),
        )
        embed.add_field(name="Request", value=request_name, inline=True)
        embed.add_field(name="File", value=filename or "unknown", inline=True)
        embed.add_field(name="Keys Exhausted", value=str(key_count), inline=True)
        embed.add_field(
            name="Wait Window",
            value=f"{retry_hours} hours" if retry_hours else f"{retry_delay_seconds} sec",
            inline=True,
        )
        embed.add_field(
            name="Reason",
            value="daily quota exhausted" if event.get("daily_quota_exhausted") else "retryable Gemini error",
            inline=True,
        )
        embed.add_field(
            name="Retry Cycle",
            value=f"{event.get('retry_cycle_attempt', 0)}/{event.get('retry_cycle_count', 0)}",
            inline=True,
        )
        backlog_total, backlog_lines = await self._build_backlog_snapshot()
        if backlog_lines:
            embed.add_field(name="Remaining Total", value=str(backlog_total), inline=True)
            embed.add_field(name="Current Backlog", value="\n".join(backlog_lines), inline=False)
        await self._send_system_log_embed(embed)

    async def send_system_resume(
        self,
        *,
        requested_by: str,
        result: DriveWatchResumeResult,
    ) -> None:
        if self.settings.discord_system_log_channel_id is None:
            return

        description = (
            "A slash command interrupted the current watcher wait and resumed polling immediately."
            if result.was_waiting
            else "A slash command queued an immediate resume. The next watcher wait will be skipped."
        )
        embed = discord.Embed(
            title="HARINA Watch Resume",
            description=description,
            color=discord.Color.green(),
        )
        embed.add_field(name="Requested By", value=requested_by, inline=True)
        embed.add_field(name="Wait Reason", value=_describe_wait_reason(result.reason), inline=True)
        embed.add_field(name="Remaining", value=_format_wait_window(result.remaining_seconds), inline=True)
        await self._send_system_log_embed(embed)

    async def _build_backlog_snapshot(self) -> tuple[int, list[str]]:
        backlog_lines: list[str] = []
        backlog_total = 0
        for route in self._routes:
            files = await self.watcher.google_workspace.list_image_files(folder_id=route.source_folder_id)
            route_count = len(files)
            backlog_total += route_count
            backlog_lines.append(f"{route.label}: {route_count}")
        return backlog_total, backlog_lines

    async def _send_system_log_embed(self, embed: discord.Embed) -> None:
        if self.settings.discord_system_log_channel_id is None:
            return

        channel = await self._resolve_messageable_channel(self.settings.discord_system_log_channel_id)
        await channel.send(embed=embed)

    async def _resolve_messageable_channel(self, channel_id: int):
        channel = self.get_channel(channel_id)
        if channel is None:
            channel = await self.fetch_channel(channel_id)
        if not hasattr(channel, "send"):
            raise RuntimeError(f"Channel {channel_id} is not messageable.")
        return channel

    async def _sleep_for_watcher_wait(self, delay_seconds: float) -> None:
        await self._resume_controller.sleep(delay_seconds, reason="gemini-wait")

    async def _run_watch_loop(self) -> None:
        try:
            while True:
                async with self._scan_lock:
                    self.last_summary = await self.watcher.scan_once()
                await self.send_system_cycle_summary(self.last_summary)
                if self.run_once:
                    return
                await self._resume_controller.sleep(
                    self.settings.drive_poll_interval_seconds,
                    reason="poll-interval",
                )
        except Exception as exc:  # noqa: BLE001
            self.run_error = exc
            await self.send_system_error(exc)
        finally:
            await self.close()

    def request_polling_resume(self) -> DriveWatchResumeResult:
        return self._resume_controller.request_resume()

    def _register_app_commands(self) -> None:
        @self.tree.command(
            name="resume_polling",
            description="Interrupt the current wait and resume the drive watcher now.",
        )
        @app_commands.guild_only()
        @app_commands.default_permissions(manage_guild=True)
        async def resume_polling(interaction: discord.Interaction) -> None:
            await self._handle_resume_polling_command(interaction)

    async def _handle_resume_polling_command(self, interaction: discord.Interaction) -> None:
        member = interaction.user
        permissions = getattr(member, "guild_permissions", None)
        if permissions is None or not permissions.manage_guild:
            await interaction.response.send_message(
                "You need the Manage Server permission to resume the drive watcher.",
                ephemeral=True,
            )
            return

        if (
            self.settings.discord_system_log_channel_id is not None
            and interaction.channel_id != self.settings.discord_system_log_channel_id
        ):
            await interaction.response.send_message(
                f"Use this command in the system log channel <#{self.settings.discord_system_log_channel_id}>.",
                ephemeral=True,
            )
            return

        scan_in_progress = self._scan_lock.locked()
        result = self.request_polling_resume()
        requester_name = getattr(member, "display_name", str(member))
        await self.send_system_resume(requested_by=requester_name, result=result)

        if result.reason == "poll-interval":
            message = (
                "Poll interval cleared. "
                f"Running a scan now instead of waiting another {_format_wait_window(result.remaining_seconds)}."
            )
        elif result.reason == "gemini-wait":
            message = (
                "Retry wait cleared. "
                f"Watcher resumed immediately instead of waiting another {_format_wait_window(result.remaining_seconds)}."
            )
        elif scan_in_progress:
            message = (
                "Watcher is already active. "
                "Queued an immediate resume so the next wait is skipped after the current scan."
            )
        else:
            message = (
                "No retry wait was active. "
                "Queued an immediate resume so the next scheduled wait is skipped."
            )

        await interaction.response.send_message(message, ephemeral=True)

    async def _sync_app_commands(self) -> None:
        guild_ids = await self._discover_command_guild_ids()
        if not guild_ids:
            synced = await self.tree.sync()
            logger.info("Synced %s global app command(s) for the drive watcher.", len(synced))
            return

        for guild_id in sorted(guild_ids):
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %s guild app command(s) for guild %s.", len(synced), guild_id)

    async def _discover_command_guild_ids(self) -> set[int]:
        channel_ids = {route.discord_channel_id for route in self._routes}
        if self.settings.discord_system_log_channel_id is not None:
            channel_ids.add(self.settings.discord_system_log_channel_id)

        guild_ids: set[int] = set()
        for channel_id in channel_ids:
            try:
                channel = await self._resolve_messageable_channel(channel_id)
            except Exception:  # noqa: BLE001
                logger.exception("Could not resolve channel %s while syncing app commands.", channel_id)
                continue

            guild = getattr(channel, "guild", None)
            guild_id = getattr(guild, "id", None) or getattr(channel, "guild_id", None)
            if guild_id is not None:
                guild_ids.add(int(guild_id))
        return guild_ids


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


def _describe_wait_reason(reason: str | None) -> str:
    if reason == "poll-interval":
        return "poll interval"
    if reason == "gemini-wait":
        return "Gemini retry window"
    return "no active wait"


def _format_wait_window(seconds: int) -> str:
    if seconds <= 0:
        return "0 sec"
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} min"
    return f"{seconds} sec"
