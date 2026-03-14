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
    "itemCategory",
    "itemQuantity",
    "itemUnitPrice",
    "itemTotalPrice",
    "itemJson",
    "lineItemsJson",
]

MAX_EMBED_LINE_ITEMS = 6
DEBUG_EMBED_PALETTE = (
    (255, 99, 132),
    (54, 162, 235),
    (75, 192, 192),
    (255, 159, 64),
    (153, 102, 255),
)


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
    author_tag: str = "google-drive",
) -> ReceiptRecordContext:
    return ReceiptRecordContext(
        channel_name=source_name,
        author_tag=author_tag,
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
                item.category or "",
                number_cell(item.quantity),
                number_cell(item.unit_price),
                number_cell(item.total_price),
                json.dumps(item.model_dump(mode="json"), ensure_ascii=False),
                serialized_line_items,
            ]
        )

    return rows


def format_receipt_summary(extraction: ReceiptExtraction, drive_file_url: str | None) -> str:
    merchant = extraction.merchant_name or "店舗不明"
    total = f"{extraction.total} {extraction.currency or ''}".strip() if extraction.total is not None else "合計不明"
    purchase_date = extraction.purchase_date or "日付不明"
    item_count = len(normalize_line_items(extraction.line_items))
    parts = [merchant, total, purchase_date, f"商品数: {item_count}"]
    if drive_file_url:
        parts.append(f"Drive: {drive_file_url}")
    return " | ".join(parts)


def build_receipt_embed(
    *,
    title: str,
    extraction: ReceiptExtraction,
    drive_file_url: str | None,
    spreadsheet_url: str | None = None,
    source_label: str | None = None,
    image_url: str | None = None,
) -> discord.Embed:
    merchant = extraction.merchant_name or "店舗不明"
    total = f"{extraction.total} {extraction.currency or ''}".strip() if extraction.total is not None else "不明"
    purchase_date = extraction.purchase_date or "不明"
    confidence = format_confidence(extraction.confidence)
    item_count = len(normalize_line_items(extraction.line_items))

    embed = discord.Embed(
        title=title,
        description=format_receipt_summary(extraction, drive_file_url=None),
        color=receipt_embed_color(extraction.confidence),
    )
    embed.add_field(name="店舗", value=merchant, inline=True)
    embed.add_field(name="合計", value=total, inline=True)
    embed.add_field(name="日付", value=purchase_date, inline=True)
    embed.add_field(name="商品数", value=str(item_count), inline=True)
    embed.add_field(name="信頼度", value=confidence, inline=True)
    if source_label:
        embed.add_field(name="元画像", value=source_label, inline=True)
    if drive_file_url or spreadsheet_url:
        destinations: list[str] = []
        if drive_file_url:
            destinations.append("Google Drive")
        if spreadsheet_url:
            destinations.append("Google Sheets")
        embed.add_field(name="保存先", value=", ".join(destinations), inline=False)

    category_preview = format_category_preview(extraction.line_items)
    if category_preview:
        embed.add_field(name="カテゴリ", value=category_preview, inline=False)

    item_category_preview = format_item_category_preview(extraction.line_items)
    if item_category_preview:
        embed.add_field(name="商品カテゴリ", value=item_category_preview, inline=False)

    item_preview = format_line_item_preview(extraction.line_items)
    if item_preview:
        embed.add_field(name="明細", value=item_preview, inline=False)

    if extraction.notes:
        embed.add_field(name="メモ", value=truncate_field(extraction.notes), inline=False)
    if extraction.receipt_number:
        embed.set_footer(text=f"レシート番号 {extraction.receipt_number}")
    if image_url:
        embed.set_image(url=image_url)

    return embed


def build_drive_intake_embed(
    *,
    route_label: str,
    file_name: str,
    drive_file_url: str | None,
    image_url: str | None = None,
) -> discord.Embed:
    del drive_file_url
    embed = discord.Embed(
        title=f"HARINA V4 Intake // {route_label}",
        description="Google Drive watcher が新しい画像を検知し、レシート処理を開始しました。",
        color=discord.Color.from_rgb(52, 152, 219),
    )
    embed.add_field(name="担当", value=route_label, inline=True)
    embed.add_field(name="画像", value=file_name, inline=True)
    embed.add_field(name="状態", value="処理中", inline=True)
    if image_url:
        embed.set_image(url=image_url)
    embed.set_footer(text="HARINA V4 Drive Watch")
    return embed


def build_debug_status_embed(
    *,
    test_prefix: str,
    caption: str,
    image_count: int,
    timeout_seconds: float,
) -> discord.Embed:
    localized_caption = localize_debug_caption(caption)
    embed = discord.Embed(
        title=localized_caption,
        description="画像を送信し、処理スレッドからの応答を待っています。",
        color=_pick_debug_color(f"{test_prefix} {localized_caption}".strip()),
    )
    embed.add_field(name="モード", value="Discord送信確認", inline=True)
    embed.add_field(name="画像数", value=f"{image_count}枚", inline=True)
    embed.add_field(name="待機時間", value=f"{timeout_seconds:.0f}秒", inline=True)
    embed.set_footer(text="HARINA V4 デバッグパイプライン")
    return embed


def build_receipt_links_view(
    *,
    drive_file_url: str | None,
    spreadsheet_url: str | None = None,
) -> discord.ui.View | None:
    buttons: list[discord.ui.Button] = []
    if drive_file_url:
        buttons.append(discord.ui.Button(label="Open Drive", style=discord.ButtonStyle.link, url=drive_file_url))
    if spreadsheet_url:
        buttons.append(discord.ui.Button(label="Open Sheet", style=discord.ButtonStyle.link, url=spreadsheet_url))

    if not buttons:
        return None

    view = discord.ui.View(timeout=None)
    for button in buttons:
        view.add_item(button)
    return view


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
        category = f" [{item.category}]" if item.category else ""
        preview_lines.append(f"{index}. {item.name or 'Unnamed item'}{category}{quantity}{total}")

    remaining = len(normalized_items) - len(preview_lines)
    if remaining > 0:
        preview_lines.append(f"...and {remaining} more")

    return truncate_field("\n".join(preview_lines))


def format_category_preview(items: list[ReceiptLineItem]) -> str | None:
    normalized_items = normalize_line_items(items)
    if not normalized_items:
        return None

    category_counts: dict[str, int] = {}
    uncategorized_count = 0
    for item in normalized_items:
        category_name = (item.category or "").strip()
        if not category_name:
            uncategorized_count += 1
            continue
        category_counts[category_name] = category_counts.get(category_name, 0) + 1

    preview_lines = [f"{category_name}: {count}件" for category_name, count in category_counts.items()]
    if uncategorized_count:
        preview_lines.append(f"未分類: {uncategorized_count}件")
    if not preview_lines:
        return None

    return truncate_field("\n".join(preview_lines))


def format_item_category_preview(items: list[ReceiptLineItem]) -> str | None:
    normalized_items = normalize_line_items(items)
    if not normalized_items:
        return None

    preview_lines: list[str] = []
    for index, item in enumerate(normalized_items[:MAX_EMBED_LINE_ITEMS], start=1):
        item_name = item.name or "Unnamed item"
        category_name = (item.category or "").strip() or "未分類"
        preview_lines.append(f"{index}. {item_name}: {category_name}")

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


def localize_debug_caption(caption: str) -> str:
    normalized = caption.strip().lower().replace("_", "-")
    if normalized == "debug-log-check":
        return "デバッグログ確認"
    if normalized == "cli-upload-test":
        return "アップロード確認"
    return caption.strip() or "デバッグ確認"


def _pick_debug_color(seed: str) -> discord.Color:
    index = sum(ord(character) for character in seed) % len(DEBUG_EMBED_PALETTE)
    red, green, blue = DEBUG_EMBED_PALETTE[index]
    return discord.Color.from_rgb(red, green, blue)
