# Google Setup

## 1. Create a service account

Create a Google Cloud service account in the same project where you enable:

- Google Drive API
- Google Sheets API

Download the JSON key, or copy its JSON payload into a secret store.

## 2. Prefer OAuth refresh tokens on personal Gmail

If HARINA writes into a personal Google Drive account, use OAuth refresh-token credentials instead of a service account.

1. Create an OAuth client in Google Cloud.
2. Download the OAuth client JSON into `./secrets`.
3. Run:

```bash
uv run harina google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
```

This flow only needs your browser once. After the refresh token is saved, HARINA can refresh access automatically.

## 3. Bootstrap Drive and Sheets from the CLI

After you have the service account key, HARINA can create the Drive folder and spreadsheet for you.

```bash
uv run harina google init-resources --service-account-key-file ./secrets/harina-v4-bot.json --env-file .env
```

Or, if you already configured OAuth in `.env`:

```bash
uv run harina google init-resources --env-file .env
```

Useful flags:

- `--folder-name "Harina V4 Receipts"`
- `--spreadsheet-title "Harina V4 Receipts"`
- `--sheet-name Receipts`
- `--share-with-email you@example.com`
- `--env-file .env`

The command will:

- create or reuse a Drive folder owned by the service account
- create or reuse a spreadsheet owned by the service account
- ensure the target sheet tab and header row exist
- print the required `GOOGLE_*` values
- optionally write those values into `.env`

When `--env-file` is used, HARINA also records the generated resource URLs such as:

- `GOOGLE_DRIVE_FOLDER_URL`
- `GOOGLE_SHEETS_SPREADSHEET_URL`

For operator-friendly bookkeeping, it is also useful to keep these optional metadata keys in `.env`:

- `GOOGLE_CLOUD_PROJECT_ID`
- `GOOGLE_CLOUD_PROJECT_NUMBER`
- `GOOGLE_CLOUD_CONSOLE_URL`
- `GOOGLE_CLOUD_CREDENTIALS_URL`
- `GOOGLE_CLOUD_AUTH_OVERVIEW_URL`
- `GOOGLE_OAUTH_CLIENT_ID`

Important note:

- Personal Google Drive accounts often reject service-account-owned uploads because service accounts do not have Drive storage quota there
- For personal Gmail environments, prefer OAuth refresh tokens instead of pure service-account uploads

If you prefer to create resources manually, you can still do that:

- create a folder for receipt images and copy its folder ID into `GOOGLE_DRIVE_FOLDER_ID`
- create a spreadsheet for extracted rows and copy its ID into `GOOGLE_SHEETS_SPREADSHEET_ID`
- if you use service accounts, share both resources with the service account email
- optional: set `GOOGLE_SHEETS_SHEET_NAME` if you do not want the default `Receipts`

## 4. Choose how to provide credentials

Use one of these approaches:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
  Put the JSON payload directly into an environment variable
- `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`
  Mount the JSON file and provide its in-container path
- `GOOGLE_OAUTH_CLIENT_JSON` + `GOOGLE_OAUTH_REFRESH_TOKEN`
  Put the OAuth client JSON and one-time refresh token into environment variables
- `GOOGLE_OAUTH_CLIENT_SECRET_FILE` + `GOOGLE_OAUTH_REFRESH_TOKEN`
  Mount the OAuth client JSON file and keep the refresh token in the environment

For Docker Compose, the repository expects file-based secrets under `./secrets`, mounted to `/app/secrets`.
