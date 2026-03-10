from __future__ import annotations

import json
import re
from datetime import datetime, UTC

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


def is_image_attachment(attachment: discord.Attachment) -> bool:
    content_type = attachment.content_type or ""
    return bool(
        content_type.startswith("image/")
        or attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".heif"))
    )


def build_drive_file_name(original_filename: str, extraction: ReceiptExtraction) -> str:
    merchant = sanitize_segment(extraction.merchant_name or "merchant") or "merchant"
    purchase_date = sanitize_segment(extraction.purchase_date or datetime.now(UTC).date().isoformat()) or "unknown-date"
    suffix = re.sub(r"[^\w.\-]+", "-", original_filename)
    return f"{purchase_date}_{merchant}_{suffix}"


def build_receipt_row(
    *,
    message: discord.Message,
    attachment: discord.Attachment,
    extraction: ReceiptExtraction,
    drive_file_id: str,
    drive_file_url: str | None,
) -> list[str]:
    channel_name = getattr(message.channel, "name", "")
    author_tag = getattr(message.author, "global_name", None) or str(message.author)

    return [
        datetime.now(UTC).isoformat(),
        str(message.guild.id) if message.guild else "",
        message.guild.name if message.guild else "",
        str(message.channel.id),
        channel_name or "",
        str(message.id),
        message.jump_url,
        str(message.author.id),
        author_tag,
        str(attachment.id),
        attachment.filename,
        attachment.url,
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
