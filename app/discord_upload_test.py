from __future__ import annotations

import asyncio
from pathlib import Path

import discord

from app.bot import ReceiptBot
from app.config import Settings


class DiscordUploadTestBot(ReceiptBot):
    def __init__(
        self,
        *,
        settings: Settings,
        channel_id: int,
        image_path: Path,
        caption: str | None,
        timeout_seconds: float,
    ) -> None:
        super().__init__(settings=settings)
        self.channel_id = channel_id
        self.image_path = image_path
        self.caption = caption or "CLI upload test"
        self.timeout_seconds = timeout_seconds
        self._result_event = asyncio.Event()
        self.sent_message: discord.Message | None = None
        self.reply_message: discord.Message | None = None
        self.run_error: Exception | None = None

    async def on_ready(self) -> None:
        await super().on_ready()

        try:
            channel = await self.fetch_channel(self.channel_id)
            if not hasattr(channel, "send"):
                raise RuntimeError(f"Channel {self.channel_id} is not messageable.")

            prefix = self.settings.discord_test_message_prefix
            content = f"{prefix} {self.caption}"
            file = discord.File(self.image_path, filename=self.image_path.name)
            self.sent_message = await channel.send(content=content, file=file)

            await asyncio.wait_for(self._result_event.wait(), timeout=self.timeout_seconds)
        except Exception as exc:  # noqa: BLE001
            self.run_error = exc
        finally:
            await self.close()

    async def on_message(self, message: discord.Message) -> None:
        await super().on_message(message)

        if not self.sent_message or not self.user:
            return

        if message.id == self.sent_message.id:
            return

        reference = getattr(message, "reference", None)
        if (
            reference is not None
            and reference.message_id == self.sent_message.id
            and message.author.id == self.user.id
        ):
            self.reply_message = message
            self._result_event.set()


async def run_discord_upload_test(
    *,
    settings: Settings,
    channel_id: int,
    image_path: Path,
    caption: str | None = None,
    timeout_seconds: float = 60.0,
) -> dict[str, object]:
    if not image_path.exists():
        raise RuntimeError(f"Image file does not exist: {image_path}")

    client = DiscordUploadTestBot(
        settings=settings,
        channel_id=channel_id,
        image_path=image_path,
        caption=caption,
        timeout_seconds=timeout_seconds,
    )
    await client.start(settings.discord_token)

    if client.run_error is not None:
        raise client.run_error

    if client.sent_message is None:
        raise RuntimeError("Test message was not sent.")

    if client.reply_message is None:
        raise RuntimeError("Did not receive a bot reply before timeout.")

    return {
        "channel_id": channel_id,
        "image_path": str(image_path.resolve()),
        "sent_message_id": client.sent_message.id,
        "sent_message_url": client.sent_message.jump_url,
        "reply_message_id": client.reply_message.id,
        "reply_message_url": client.reply_message.jump_url,
        "reply_content": client.reply_message.content,
    }
