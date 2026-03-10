import { PassThrough } from "node:stream";

import { drive } from "./google-workspace.js";

export type DriveUploadInput = {
  fileName: string;
  mimeType: string;
  buffer: Buffer;
  folderId: string;
};

export type UploadedDriveFile = {
  fileId: string;
  webViewLink: string | null;
};

export async function uploadReceiptImage(input: DriveUploadInput): Promise<UploadedDriveFile> {
  const stream = new PassThrough();
  stream.end(input.buffer);

  const response = await drive.files.create({
    requestBody: {
      name: input.fileName,
      parents: [input.folderId]
    },
    media: {
      mimeType: input.mimeType,
      body: stream
    },
    fields: "id,webViewLink"
  });

  if (!response.data.id) {
    throw new Error("Google Drive did not return a file ID.");
  }

  return {
    fileId: response.data.id,
    webViewLink: response.data.webViewLink ?? null
  };
}
