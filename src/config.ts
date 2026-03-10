import { config as loadDotEnv } from "dotenv";
import { readFileSync } from "node:fs";
import { z } from "zod";

loadDotEnv();

const envSchema = z
  .object({
    DISCORD_TOKEN: z.string().min(1),
    DISCORD_CHANNEL_IDS: z.string().optional(),
    GEMINI_API_KEY: z.string().min(1),
    GEMINI_MODEL: z.string().min(1).default("gemini-3-flash-preview"),
    GOOGLE_SERVICE_ACCOUNT_JSON: z.string().optional(),
    GOOGLE_SERVICE_ACCOUNT_KEY_FILE: z.string().optional(),
    GOOGLE_DRIVE_FOLDER_ID: z.string().min(1),
    GOOGLE_SHEETS_SPREADSHEET_ID: z.string().min(1),
    GOOGLE_SHEETS_SHEET_NAME: z.string().min(1).default("Receipts")
  })
  .superRefine((value, ctx) => {
    if (!value.GOOGLE_SERVICE_ACCOUNT_JSON && !value.GOOGLE_SERVICE_ACCOUNT_KEY_FILE) {
      ctx.addIssue({
        code: "custom",
        message:
          "Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_KEY_FILE so the bot can access Drive and Sheets.",
        path: ["GOOGLE_SERVICE_ACCOUNT_JSON"]
      });
    }
  });

function parseServiceAccountCredential(rawEnv: {
  GOOGLE_SERVICE_ACCOUNT_JSON?: string;
  GOOGLE_SERVICE_ACCOUNT_KEY_FILE?: string;
}) {
  const inlineJson = rawEnv.GOOGLE_SERVICE_ACCOUNT_JSON?.trim();

  if (inlineJson) {
    return normalizeServiceAccountJson(JSON.parse(inlineJson));
  }

  const keyFile = rawEnv.GOOGLE_SERVICE_ACCOUNT_KEY_FILE?.trim();

  if (!keyFile) {
    throw new Error("Missing Google service account credentials.");
  }

  const fileContents = readFileSync(keyFile, "utf8");
  return normalizeServiceAccountJson(JSON.parse(fileContents));
}

function normalizeServiceAccountJson(raw: unknown) {
  const credentialSchema = z.object({
    client_email: z.string().email(),
    private_key: z.string().min(1),
    project_id: z.string().min(1).optional()
  });

  const parsed = credentialSchema.parse(raw);
  return {
    ...parsed,
    private_key: parsed.private_key.replace(/\\n/g, "\n")
  };
}

const parsedEnv = envSchema.parse(process.env);

export const appConfig = {
  discordToken: parsedEnv.DISCORD_TOKEN,
  allowedChannelIds: new Set(
    parsedEnv.DISCORD_CHANNEL_IDS?.split(",")
      .map((value) => value.trim())
      .filter(Boolean) ?? []
  ),
  geminiApiKey: parsedEnv.GEMINI_API_KEY,
  geminiModel: parsedEnv.GEMINI_MODEL,
  googleDriveFolderId: parsedEnv.GOOGLE_DRIVE_FOLDER_ID,
  googleSheetsSpreadsheetId: parsedEnv.GOOGLE_SHEETS_SPREADSHEET_ID,
  googleSheetsSheetName: parsedEnv.GOOGLE_SHEETS_SHEET_NAME,
  serviceAccountCredentials: parseServiceAccountCredential(parsedEnv)
};

export type AppConfig = typeof appConfig;
