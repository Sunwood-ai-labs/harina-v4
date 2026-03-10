import type { Attachment, Message } from "discord.js";

import { appConfig } from "../config.js";
import type { ReceiptExtraction } from "../receipt-schema.js";
import { buildDriveFileName, buildReceiptRow, formatReceiptSummary, isImageAttachment } from "../utils/receipt-format.js";
import { downloadAttachmentBuffer } from "../utils/download.js";
import { extractReceiptData } from "./gemini.js";
import { uploadReceiptImage } from "./drive.js";
import { appendReceiptRow } from "./sheets.js";

export type ProcessedReceiptResult = {
  extraction: ReceiptExtraction;
  driveFileId: string;
  driveFileUrl: string | null;
};

export async function processReceiptAttachment(
  message: Message,
  attachment: Attachment
): Promise<ProcessedReceiptResult> {
  if (!isImageAttachment(attachment)) {
    throw new Error("Attachment is not a supported image.");
  }

  const downloaded = await downloadAttachmentBuffer({
    url: attachment.url,
    fileName: attachment.name ?? `receipt-${attachment.id}`,
    fallbackMimeType: attachment.contentType ?? undefined
  });

  const extraction = await extractReceiptData({
    data: downloaded.buffer,
    mimeType: downloaded.mimeType,
    fileName: downloaded.fileName
  });

  const driveFile = await uploadReceiptImage({
    fileName: buildDriveFileName(downloaded.fileName, extraction),
    mimeType: downloaded.mimeType,
    buffer: downloaded.buffer,
    folderId: appConfig.googleDriveFolderId
  });

  const row = buildReceiptRow({
    processedAt: new Date().toISOString(),
    message,
    attachment,
    extraction,
    driveFileId: driveFile.fileId,
    driveFileUrl: driveFile.webViewLink
  });

  await appendReceiptRow(appConfig.googleSheetsSpreadsheetId, appConfig.googleSheetsSheetName, row);

  return {
    extraction,
    driveFileId: driveFile.fileId,
    driveFileUrl: driveFile.webViewLink
  };
}

export function getReceiptAttachments(message: Message) {
  return message.attachments.filter((attachment) => isImageAttachment(attachment));
}

export function buildSuccessReply(results: ProcessedReceiptResult[]) {
  return results
    .map((result, index) => {
      const prefix = results.length > 1 ? `Receipt ${index + 1}` : "Receipt";
      return `${prefix}: ${formatReceiptSummary(result.extraction, result.driveFileUrl)}`;
    })
    .join("\n");
}
