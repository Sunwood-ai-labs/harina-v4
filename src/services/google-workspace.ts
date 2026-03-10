import { google } from "googleapis";

import { appConfig } from "../config.js";

const auth = new google.auth.GoogleAuth({
  credentials: appConfig.serviceAccountCredentials,
  scopes: ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
});

export const drive = google.drive({
  version: "v3",
  auth
});

export const sheets = google.sheets({
  version: "v4",
  auth
});
