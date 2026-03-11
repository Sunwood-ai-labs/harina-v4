from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

import discord

from app.models import ReceiptExtraction


RECEIPT_SHEET_HEADERS = [
    "processedAt",
    "guildId",
    "guildName",
    "channelId",
    "channelName",
    "messageId",
    "messageUrl",
    "authorId",
    "authorTag",
    "attachmentId",
    "attachmentName",
    "attachmentUrl",
    "driveFileId",
    "driveFileUrl",
    "merchantName",
    "merchantPhone",
    "purchaseDate",
    "purchaseTime",
    "currency",
    "subtotal",
    "tax",
    "total",
    "paymentMethod",
    "receiptNumber",
    "language",
    "confidence",
    "notes",
    "rawText",
    "lineItemsJson",
]


@dataclass(slots=True)
class ReceiptRecordContext:
    processed_at: str | None = None
    guild_id: str = ""
    guild_name: str = ""
    channel_id: str = ""
    channel_name: str = ""
    message_id: str = ""
    message_url: str = ""
    author_id: str = ""
    author_tag: str = ""
    attachment_id: str = ""
    attachment_name: str = ""
    attachment_url: str = ""


def is_image_attachment(attachment: discord.Attachment) -> bool:
    content_type = attachment.content_type or ""
    return bool(
        content_type.startswith("image/")
        or attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".heif"))
    )


def build_discord_receipt_context(message: discord.Message, attachment: discord.Attachment) -> ReceiptRecordContext:
    channel_name = getattr(message.channel, "name", "")
    author_tag = getattr(message.author, "global_name", None) or str(message.author)

    return ReceiptRecordContext(
        guild_id=str(message.guild.id) if message.guild else "",
        guild_name=message.guild.name if message.guild else "",
        channel_id=str(message.channel.id),
        channel_name=channel_name or "",
        message_id=str(message.id),
        message_url=message.jump_url,
        author_id=str(message.author.id),
        author_tag=author_tag,
        attachment_id=str(attachment.id),
        attachment_name=attachment.filename,
        attachment_url=attachment.url,
    )


def build_local_receipt_context(
    image_path: Path,
    *,
    source_name: str = "cli",
    author_tag: str = "harina-v4",
) -> ReceiptRecordContext:
    return ReceiptRecordContext(
        channel_name=source_name,
        author_tag=author_tag,
        attachment_name=image_path.name,
        attachment_url=str(image_path.resolve()),
    )


def build_drive_file_name(original_filename: str, extraction: ReceiptExtraction) -> str:
    merchant = sanitize_segment(extraction.merchant_name or "merchant") or "merchant"
    purchase_date = sanitize_segment(extraction.purchase_date or datetime.now(UTC).date().isoformat()) or "unknown-date"
    suffix = re.sub(r"[^\w.\-]+", "-", original_filename)
    return f"{purchase_date}_{merchant}_{suffix}"


def build_receipt_row(
    *,
    context: ReceiptRecordContext,
    extraction: ReceiptExtraction,
    drive_file_id: str,
    drive_file_url: str | None,
) -> list[str]:
    return [
        context.processed_at or datetime.now(UTC).isoformat(),
        context.guild_id,
        context.guild_name,
        context.channel_id,
        context.channel_name,
        context.message_id,
        context.message_url,
        context.author_id,
        context.author_tag,
        context.attachment_id,
        context.attachment_name,
        context.attachment_url,
        drive_file_id,
        drive_file_url or "",
        extraction.merchant_name or "",
        extraction.merchant_phone or "",
        extraction.purchase_date or "",
        extraction.purchase_time or "",
        extraction.currency or "",
        number_cell(extraction.subtotal),
        number_cell(extraction.tax),
        number_cell(extraction.total),
        extraction.payment_method or "",
        extraction.receipt_number or "",
        extraction.language or "",
        number_cell(extraction.confidence),
        extraction.notes or "",
        extraction.raw_text or "",
        json.dumps([item.model_dump() for item in extraction.line_items], ensure_ascii=False),
    ]


def format_receipt_summary(extraction: ReceiptExtraction, drive_file_url: str | None) -> str:
    merchant = extraction.merchant_name or "Unknown merchant"
    total = f"{extraction.total} {extraction.currency or ''}".strip() if extraction.total is not None else "total unknown"
    purchase_date = extraction.purchase_date or "date unknown"
    drive_part = f" | Drive: {drive_file_url}" if drive_file_url else ""
    return f"{merchant} | {total} | {purchase_date}{drive_part}"


def number_cell(value: float | None) -> str:
    return "" if value is None else str(value)


def sanitize_segment(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^\w.\-]+", "-", value, flags=re.UNICODE)
    return value.strip("-")[:48]
