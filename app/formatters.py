from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import discord

from app.models import ReceiptExtraction, ReceiptLineItem


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
    "lineItemsCount",
    "rowType",
    "itemIndex",
    "itemName",
    "itemQuantity",
    "itemUnitPrice",
    "itemTotalPrice",
    "itemJson",
    "lineItemsJson",
]

MAX_EMBED_LINE_ITEMS = 6


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


def build_drive_receipt_context(
    *,
    file_id: str,
    file_name: str,
    file_url: str | None,
    source_name: str = "google-drive-watch",
) -> ReceiptRecordContext:
    return ReceiptRecordContext(
        channel_name=source_name,
        author_tag="google-drive",
        attachment_id=file_id,
        attachment_name=file_name,
        attachment_url=file_url or "",
    )


def build_drive_file_name(original_filename: str, extraction: ReceiptExtraction) -> str:
    merchant = sanitize_segment(extraction.merchant_name or "merchant") or "merchant"
    purchase_date = sanitize_segment(extraction.purchase_date or datetime.now(UTC).date().isoformat()) or "unknown-date"
    suffix = re.sub(r"[^\w.\-]+", "-", original_filename)
    return f"{purchase_date}_{merchant}_{suffix}"


def build_receipt_rows(
    *,
    context: ReceiptRecordContext,
    extraction: ReceiptExtraction,
    drive_file_id: str,
    drive_file_url: str | None,
) -> list[list[str]]:
    line_items = normalize_line_items(extraction.line_items)
    serialized_line_items = json.dumps([item.model_dump(mode="json") for item in line_items], ensure_ascii=False)
    base_cells = build_base_receipt_cells(
        context=context,
        extraction=extraction,
        drive_file_id=drive_file_id,
        drive_file_url=drive_file_url,
    )

    if not line_items:
        return [
            base_cells
            + [
                "0",
                "receipt_fallback",
                "",
                "",
                "",
                "",
                "",
                "",
                serialized_line_items,
            ]
        ]

    rows: list[list[str]] = []
    for index, item in enumerate(line_items, start=1):
        rows.append(
            base_cells
            + [
                str(len(line_items)),
                "line_item",
                str(index),
                item.name or "",
                number_cell(item.quantity),
                number_cell(item.unit_price),
                number_cell(item.total_price),
                json.dumps(item.model_dump(mode="json"), ensure_ascii=False),
                serialized_line_items,
            ]
        )

    return rows


def format_receipt_summary(extraction: ReceiptExtraction, drive_file_url: str | None) -> str:
    merchant = extraction.merchant_name or "Unknown merchant"
    total = f"{extraction.total} {extraction.currency or ''}".strip() if extraction.total is not None else "total unknown"
    purchase_date = extraction.purchase_date or "date unknown"
    item_count = len(normalize_line_items(extraction.line_items))
    parts = [merchant, total, purchase_date, f"Items: {item_count}"]
    if drive_file_url:
        parts.append(f"Drive: {drive_file_url}")
    return " | ".join(parts)


def build_receipt_embed(
    *,
    title: str,
    extraction: ReceiptExtraction,
    drive_file_url: str | None,
    source_label: str | None = None,
    image_url: str | None = None,
) -> discord.Embed:
    merchant = extraction.merchant_name or "Unknown merchant"
    total = f"{extraction.total} {extraction.currency or ''}".strip() if extraction.total is not None else "unknown"
    purchase_date = extraction.purchase_date or "unknown"
    confidence = format_confidence(extraction.confidence)
    item_count = len(normalize_line_items(extraction.line_items))

    embed = discord.Embed(
        title=title,
        description=format_receipt_summary(extraction, drive_file_url=None),
        color=receipt_embed_color(extraction.confidence),
    )
    embed.add_field(name="Store", value=merchant, inline=True)
    embed.add_field(name="Total", value=total, inline=True)
    embed.add_field(name="Date", value=purchase_date, inline=True)
    embed.add_field(name="Items", value=str(item_count), inline=True)
    embed.add_field(name="Confidence", value=confidence, inline=True)
    if source_label:
        embed.add_field(name="Source", value=source_label, inline=True)
    if drive_file_url:
        embed.add_field(name="Drive", value=drive_file_url, inline=False)

    item_preview = format_line_item_preview(extraction.line_items)
    if item_preview:
        embed.add_field(name="Line Items", value=item_preview, inline=False)

    if extraction.notes:
        embed.add_field(name="Notes", value=truncate_field(extraction.notes), inline=False)
    if extraction.receipt_number:
        embed.set_footer(text=f"Receipt No. {extraction.receipt_number}")
    if image_url:
        embed.set_image(url=image_url)

    return embed


def build_base_receipt_cells(
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
    ]


def normalize_line_items(items: list[ReceiptLineItem]) -> list[ReceiptLineItem]:
    return [item for item in items if item.has_meaningful_data()]


def format_line_item_preview(items: list[ReceiptLineItem]) -> str | None:
    normalized_items = normalize_line_items(items)
    if not normalized_items:
        return None

    preview_lines: list[str] = []
    for index, item in enumerate(normalized_items[:MAX_EMBED_LINE_ITEMS], start=1):
        quantity = f" x{item.quantity:g}" if item.quantity is not None else ""
        total = f" ({item.total_price:g})" if item.total_price is not None else ""
        preview_lines.append(f"{index}. {item.name or 'Unnamed item'}{quantity}{total}")

    remaining = len(normalized_items) - len(preview_lines)
    if remaining > 0:
        preview_lines.append(f"...and {remaining} more")

    return truncate_field("\n".join(preview_lines))


def receipt_embed_color(confidence: float | None) -> discord.Color:
    if confidence is None:
        return discord.Color.from_rgb(88, 101, 242)
    if confidence >= 0.9:
        return discord.Color.from_rgb(46, 204, 113)
    if confidence >= 0.7:
        return discord.Color.from_rgb(241, 196, 15)
    return discord.Color.from_rgb(230, 126, 34)


def format_confidence(confidence: float | None) -> str:
    if confidence is None:
        return "unknown"
    return f"{confidence:.0%}"


def truncate_field(value: str, *, limit: int = 1024) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def number_cell(value: float | None) -> str:
    return "" if value is None else str(value)


def sanitize_segment(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^\w.\-]+", "-", value, flags=re.UNICODE)
    return value.strip("-")[:48]
