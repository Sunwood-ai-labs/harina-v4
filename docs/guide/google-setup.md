# Google Setup

## 1. Create a service account

Create a Google Cloud service account in the same project where you enable:

- Google Drive API
- Google Sheets API

Download the JSON key, or copy its JSON payload into a secret store.

## 2. Prepare Drive

Create a folder that will hold the original receipt images.

- Copy the folder ID from the URL
- Share the folder with the service account email
- Set `GOOGLE_DRIVE_FOLDER_ID` to that folder ID

## 3. Prepare Sheets

Create a spreadsheet for extracted receipt rows.

- Copy the spreadsheet ID from the URL
- Share the spreadsheet with the same service account email
- Set `GOOGLE_SHEETS_SPREADSHEET_ID` to that spreadsheet ID
- Optional: set `GOOGLE_SHEETS_SHEET_NAME` if you do not want the default `Receipts`

## 4. Choose how to provide credentials

Use one of these approaches:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
  Put the JSON payload directly into an environment variable
- `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`
  Mount the JSON file and provide its in-container path

For Docker Compose, the repository expects file-based secrets under `./secrets`, mounted to `/app/secrets`.
