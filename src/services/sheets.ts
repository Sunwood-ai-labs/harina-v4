import { sheets } from "./google-workspace.js";

export const receiptSheetHeaders = [
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
  "lineItemsJson"
] as const;

export async function ensureReceiptSheet(spreadsheetId: string, sheetName: string) {
  const spreadsheet = await sheets.spreadsheets.get({
    spreadsheetId,
    fields: "sheets.properties.title"
  });

  const hasSheet = spreadsheet.data.sheets?.some((sheet) => sheet.properties?.title === sheetName);

  if (!hasSheet) {
    await sheets.spreadsheets.batchUpdate({
      spreadsheetId,
      requestBody: {
        requests: [
          {
            addSheet: {
              properties: {
                title: sheetName
              }
            }
          }
        ]
      }
    });
  }

  const headerRange = `'${sheetName}'!1:1`;
  const currentHeader = await sheets.spreadsheets.values.get({
    spreadsheetId,
    range: headerRange
  });

  const headerValues = currentHeader.data.values?.[0] ?? [];

  const hasMatchingHeader =
    headerValues.length === receiptSheetHeaders.length &&
    headerValues.every((value, index) => value === receiptSheetHeaders[index]);

  if (hasMatchingHeader) {
    return;
  }

  await sheets.spreadsheets.values.update({
    spreadsheetId,
    range: `'${sheetName}'!A1`,
    valueInputOption: "RAW",
    requestBody: {
      values: [Array.from(receiptSheetHeaders)]
    }
  });
}

export async function appendReceiptRow(spreadsheetId: string, sheetName: string, row: string[]) {
  await sheets.spreadsheets.values.append({
    spreadsheetId,
    range: `'${sheetName}'!A1`,
    valueInputOption: "USER_ENTERED",
    insertDataOption: "INSERT_ROWS",
    requestBody: {
      values: [row]
    }
  });
}
