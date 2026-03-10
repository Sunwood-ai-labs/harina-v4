import { lookup as lookupMimeType } from "mime-types";

export type DownloadedAttachment = {
  buffer: Buffer;
  fileName: string;
  mimeType: string;
};

export async function downloadAttachmentBuffer(input: {
  url: string;
  fileName: string;
  fallbackMimeType?: string;
}): Promise<DownloadedAttachment> {
  const response = await fetch(input.url);

  if (!response.ok) {
    throw new Error(`Failed to download attachment: ${response.status} ${response.statusText}`);
  }

  const arrayBuffer = await response.arrayBuffer();
  const headerMimeType = response.headers.get("content-type")?.split(";")[0]?.trim();
  const extensionMimeType = lookupMimeType(input.fileName) || undefined;

  return {
    buffer: Buffer.from(arrayBuffer),
    fileName: input.fileName,
    mimeType: headerMimeType ?? input.fallbackMimeType ?? extensionMimeType ?? "image/jpeg"
  };
}
