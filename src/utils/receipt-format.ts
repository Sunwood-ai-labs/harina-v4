import type { Attachment, Message } from "discord.js";

import type { ReceiptExtraction } from "../receipt-schema.js";

export function isImageAttachment(attachment: Attachment) {
  return Boolean(
    attachment.contentType?.startsWith("image/") ||
      attachment.width ||
      attachment.name?.match(/\.(png|jpe?g|webp|gif|heic|heif)$/i)
  );
}

export function buildDriveFileName(originalFileName: string, extraction: ReceiptExtraction) {
  const merchant = sanitizeSegment(extraction.merchantName ?? "merchant") || "merchant";
  const date = sanitizeSegment(extraction.purchaseDate ?? new Date().toISOString().slice(0, 10)) || "unknown-date";
  const suffix = originalFileName.replace(/[^\w.-]+/g, "-");

  return `${date}_${merchant}_${suffix}`;
}

export function buildReceiptRow(input: {
  processedAt: string;
  message: Message;
  attachment: Attachment;
  extraction: ReceiptExtraction;
  driveFileId: string;
  driveFileUrl: string | null;
}) {
  const { message, attachment, extraction } = input;

  return [
    input.processedAt,
    message.guildId ?? "",
    message.guild?.name ?? "",
    message.channelId,
    getChannelName(message),
    message.id,
    message.url,
    message.author.id,
    message.author.tag,
    attachment.id,
    attachment.name ?? "",
    attachment.url,
    input.driveFileId,
    input.driveFileUrl ?? "",
    extraction.merchantName ?? "",
    extraction.merchantPhone ?? "",
    extraction.purchaseDate ?? "",
    extraction.purchaseTime ?? "",
    extraction.currency ?? "",
    toCellValue(extraction.subtotal),
    toCellValue(extraction.tax),
    toCellValue(extraction.total),
    extraction.paymentMethod ?? "",
    extraction.receiptNumber ?? "",
    extraction.language ?? "",
    toCellValue(extraction.confidence),
    extraction.notes ?? "",
    extraction.rawText ?? "",
    JSON.stringify(extraction.lineItems)
  ];
}

export function formatReceiptSummary(extraction: ReceiptExtraction, driveFileUrl: string | null) {
  const merchant = extraction.merchantName ?? "Unknown merchant";
  const total = extraction.total != null ? `${extraction.total} ${extraction.currency ?? ""}`.trim() : "total unknown";
  const date = extraction.purchaseDate ?? "date unknown";
  const drivePart = driveFileUrl ? ` | Drive: ${driveFileUrl}` : "";
  return `${merchant} | ${total} | ${date}${drivePart}`;
}

function sanitizeSegment(value: string) {
  return value
    .trim()
    .replace(/[^\p{L}\p{N}._-]+/gu, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

function getChannelName(message: Message) {
  return "name" in message.channel && typeof message.channel.name === "string" ? message.channel.name : "";
}

function toCellValue(value: number | null) {
  return value == null ? "" : String(value);
}
