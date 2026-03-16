# Google Setup

## 1. Choose credentials

Enable these APIs in the same Google Cloud project:

- Google Drive API
- Google Sheets API

Use one of these approaches:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`
- `GOOGLE_OAUTH_CLIENT_JSON` + `GOOGLE_OAUTH_REFRESH_TOKEN`
- `GOOGLE_OAUTH_CLIENT_SECRET_FILE` + `GOOGLE_OAUTH_REFRESH_TOKEN`

Useful sheet-related settings:

- `GOOGLE_SHEETS_SHEET_NAME` defaults to `Receipts`
- `GOOGLE_SHEETS_CATEGORY_SHEET_NAME` defaults to `Categories`

For Docker Compose, file-based secrets are expected under `./secrets`, mounted to `/app/secrets`.

## 2. Prefer OAuth refresh tokens on personal Gmail

If HARINA writes into a personal Google Drive account, prefer OAuth refresh-token credentials instead of a service account.

```bash
uv run harina-v4 google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
```

After the refresh token is saved, HARINA can refresh access automatically.

## 3. Bootstrap Drive and Sheets from the CLI

Create or reuse the main receipt Drive folder and spreadsheet:

```bash
uv run harina-v4 google init-resources --env-file .env
```

Useful flags:

- `--folder-name "Harina V4 Receipts"`
- `--spreadsheet-title "Harina V4 Receipts"`
- `--sheet-name Receipts`
- `--share-with-email you@example.com`
- `--env-file .env`

The command will:

- create or reuse the main Drive folder
- create or reuse the spreadsheet
- ensure the `Receipts` and `Categories` sheet tabs and headers exist
- seed `Categories` with short single-word labels when the sheet is empty
- optionally write IDs and URLs into `.env`

`Categories` is the live category catalog used by Gemini on every write-enabled run.
Legacy labels such as `惣菜・弁当` or `惣菜/弁当` are normalized into the current short form such as `惣菜`.

## 4. Bootstrap Drive watcher folders

Create or reuse the Drive inbox and processed folders:

```bash
uv run harina-v4 google init-drive-watch --env-file .env
```

Useful flags:

- `--source-folder-name "Harina V4 Drive Inbox"`
- `--processed-folder-name "Harina V4 Drive Processed"`
- `--parent-folder-id <folder_id>`
- `--poll-interval-seconds 60`
- `--share-with-email you@example.com`
- `--env-file .env`

The command writes these keys when `--env-file` is used:

- `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID`
- `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_URL`
- `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID`
- `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_URL`
- `DRIVE_POLL_INTERVAL_SECONDS`

If `GOOGLE_DRIVE_FOLDER_ID` is already set, HARINA uses it as the default parent folder for the watcher folders.
The watcher creates `YYYY/MM` subfolders inside `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID` lazily during processing.

## 5. Important notes

- HARINA stores one row per line item in `Receipts`, not one row per receipt
- `itemCategory` is written into `Receipts` for every categorized line item
- Gemini reads `Categories` before categorization and can append a short new category when no approved option fits
- Personal Google Drive accounts often reject service-account-owned uploads because service accounts do not have Drive storage quota there
- For personal Gmail environments, prefer OAuth refresh tokens instead of pure service-account uploads
- If you configure resources manually, make sure both the main Drive folder and the watcher folders are writable by the chosen credential
