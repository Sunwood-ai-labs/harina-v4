from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import discord

from app.bot import ERROR_EMBED_TITLE, ReceiptBot, build_receipt_thread_name
from app.config import Settings
from app.discord_debug import DiscordDebugSession, collect_debug_snapshot, serialize_message
from app.formatters import build_debug_status_embed


logger = logging.getLogger(__name__)


class DiscordUploadTestBot(ReceiptBot):
    def __init__(
        self,
        *,
        settings: Settings,
        channel_id: int,
        image_paths: list[Path],
        caption: str | None,
        timeout_seconds: float,
    ) -> None:
        super().__init__(settings=settings)
        self.debug_session = DiscordDebugSession.create(
            base_dir=settings.discord_debug_log_dir_path,
            purpose="upload-test",
        )
        self.channel_id = channel_id
        self.image_paths = image_paths
        self.caption = caption or "CLI upload test"
        self.timeout_seconds = timeout_seconds
        self._result_event = asyncio.Event()
        self._send_complete_event = asyncio.Event()
        self.sent_message: discord.Message | None = None
        self.reply_messages: list[discord.Message] = []
        self.response_thread: discord.Thread | None = None
        self.run_error: Exception | None = None
        self.debug_snapshot_path: Path | None = None

    async def on_ready(self) -> None:
        await super().on_ready()

        try:
            channel = await self.fetch_channel(self.channel_id)
            if not hasattr(channel, "send"):
                raise RuntimeError(f"Channel {self.channel_id} is not messageable.")

            prefix = self.settings.discord_test_message_prefix
            content = prefix
            files = [discord.File(image_path, filename=image_path.name) for image_path in self.image_paths]
            logger.info(
                "Sending Discord upload test to channel %s with %s image(s): %s",
                self.channel_id,
                len(self.image_paths),
                ", ".join(image_path.name for image_path in self.image_paths),
            )
            self.debug_session.write_event(
                "upload_test_start",
                channel_id=self.channel_id,
                timeout_seconds=self.timeout_seconds,
                image_paths=[str(image_path.resolve()) for image_path in self.image_paths],
                caption=self.caption,
            )
            self.sent_message = await channel.send(
                content=content,
                files=files,
                embed=build_debug_status_embed(
                    test_prefix=prefix,
                    caption=self.caption,
                    image_count=len(self.image_paths),
                    timeout_seconds=self.timeout_seconds,
                ),
            )
            logger.info("Sent Discord upload test message %s", self.sent_message.id)
            self.debug_session.write_event("upload_test_message_sent", message=serialize_message(self.sent_message))

            await asyncio.wait_for(self._result_event.wait(), timeout=self.timeout_seconds)
            try:
                await asyncio.wait_for(self._send_complete_event.wait(), timeout=15.0)
            except asyncio.TimeoutError:
                logger.warning("Timed out waiting for Discord send completion after observing the reply thread.")
                self.debug_session.write_event("upload_test_send_completion_timeout")
        except Exception as exc:  # noqa: BLE001
            self.run_error = exc
            self.debug_session.write_event("upload_test_failed", error=repr(exc))
            self.debug_snapshot_path = await self._write_debug_snapshot(reason=exc.__class__.__name__)
        finally:
            await self.close()

    async def on_message(self, message: discord.Message) -> None:
        should_skip_self_processing = bool(
            self.user
            and message.author.id == self.user.id
            and not isinstance(message.channel, discord.Thread)
            and message.channel.id == self.channel_id
            and (message.content or "").startswith(self.settings.discord_test_message_prefix)
        )
        if not should_skip_self_processing:
            await super().on_message(message)

        if not self.sent_message or not self.user:
            return
        if message.author.id != self.user.id:
            return
        if not isinstance(message.channel, discord.Thread):
            return
        if not message.embeds and not (message.content or "").strip():
            return

        expected_thread_name = build_receipt_thread_name(
            message_id=self.sent_message.id,
            attachment_count=len(self.image_paths),
        )
        if message.channel.name != expected_thread_name:
            return

        self.response_thread = message.channel
        self.reply_messages.append(message)
        logger.info(
            "Observed Discord thread reply in %s (%s embed(s))",
            self.response_thread.id,
            len(message.embeds),
        )
        self.debug_session.write_event("upload_test_reply_observed", message=serialize_message(message))
        observed_embed_count = sum(len(reply_message.embeds) for reply_message in self.reply_messages)
        if observed_embed_count >= len(self.image_paths):
            self._result_event.set()

    async def _reply_with_outcomes(self, *, target: discord.abc.Messageable, outcomes) -> None:
        try:
            await super()._reply_with_outcomes(target=target, outcomes=outcomes)
        finally:
            self._send_complete_event.set()

    async def _send_error_embed(
        self,
        *,
        message: discord.Message,
        error_embed: discord.Embed,
        attachment_count: int,
    ) -> None:
        try:
            await super()._send_error_embed(
                message=message,
                error_embed=error_embed,
                attachment_count=attachment_count,
            )
        finally:
            self._send_complete_event.set()

    async def _write_debug_snapshot(self, *, reason: str) -> Path | None:
        try:
            snapshot = await collect_debug_snapshot(
                client=self,
                channel_id=self.channel_id,
                history_limit=50,
                message_id=self.sent_message.id if self.sent_message else None,
                thread_id=self.response_thread.id if self.response_thread else None,
            )
            snapshot["reason"] = reason
            snapshot["image_paths"] = [str(image_path.resolve()) for image_path in self.image_paths]
            snapshot["timeout_seconds"] = self.timeout_seconds
            snapshot_path = self.debug_session.write_snapshot("failure-snapshot.json", snapshot)
            self.debug_session.write_event("upload_test_snapshot_written", snapshot_path=str(snapshot_path.resolve()))
            logger.info("Collected Discord debug snapshot at %s", snapshot_path.resolve())
            return snapshot_path
        except Exception as exc:  # noqa: BLE001
            logger.exception("Could not collect Discord debug snapshot.")
            self.debug_session.write_event("upload_test_snapshot_failed", error=repr(exc))
            return None


async def run_discord_upload_test(
    *,
    settings: Settings,
    channel_id: int,
    image_path: Path | None = None,
    image_paths: list[Path] | None = None,
    caption: str | None = None,
    timeout_seconds: float = 60.0,
) -> dict[str, object]:
    selected_paths = image_paths or ([image_path] if image_path is not None else [])
    if not selected_paths:
        raise RuntimeError("Provide at least one image path for the Discord upload test.")

    for selected_path in selected_paths:
        if not selected_path.exists():
            raise RuntimeError(f"Image file does not exist: {selected_path}")

    client = DiscordUploadTestBot(
        settings=settings,
        channel_id=channel_id,
        image_paths=selected_paths,
        caption=caption,
        timeout_seconds=timeout_seconds,
    )
    await client.start(settings.require_discord_token())

    if client.run_error is not None:
        if client.debug_snapshot_path is not None:
            raise RuntimeError(
                f"{client.run_error.__class__.__name__}: {client.run_error}. "
                f"Discord debug snapshot: {client.debug_snapshot_path.resolve()}"
            ) from client.run_error
        raise client.run_error

    if client.sent_message is None:
        raise RuntimeError(f"Test message was not sent. Debug log: {client.debug_session.session_dir.resolve()}")

    if client.response_thread is None:
        raise RuntimeError(
            f"Did not observe a response thread before timeout. Debug log: {client.debug_session.session_dir.resolve()}"
        )

    if not client.reply_messages:
        raise RuntimeError(
            "Did not receive a bot message inside the response thread before timeout. "
            f"Debug log: {client.debug_session.session_dir.resolve()}"
        )

    reply_embed_titles = [
        embed.title
        for reply_message in client.reply_messages
        for embed in reply_message.embeds
    ]
    if not reply_embed_titles:
        raise RuntimeError(
            f"Did not receive any embeds inside response thread {client.response_thread.id}. "
            f"Debug log: {client.debug_session.session_dir.resolve()}"
        )
    if ERROR_EMBED_TITLE in reply_embed_titles or any(
        title is not None and title.endswith("Failed") for title in reply_embed_titles
    ):
        raise RuntimeError(
            f"Bot replied with a failure embed in thread {client.response_thread.id}: "
            f"{client.reply_messages[0].jump_url}. "
            f"Debug log: {client.debug_session.session_dir.resolve()}"
        )

    return {
        "channel_id": channel_id,
        "image_paths": [str(selected_path.resolve()) for selected_path in selected_paths],
        "sent_message_id": client.sent_message.id,
        "sent_message_url": client.sent_message.jump_url,
        "thread_id": client.response_thread.id,
        "thread_name": client.response_thread.name,
        "thread_message_count": len(client.reply_messages),
        "reply_message_ids": [reply_message.id for reply_message in client.reply_messages],
        "reply_message_urls": [reply_message.jump_url for reply_message in client.reply_messages],
        "reply_embed_count": sum(len(reply_message.embeds) for reply_message in client.reply_messages),
        "reply_embed_titles": reply_embed_titles,
        "debug_log_dir": str(client.debug_session.session_dir.resolve()),
    }
