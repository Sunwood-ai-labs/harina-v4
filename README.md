[日本語](./README.ja.md)

# Harina Receipt Bot

Discord bot that watches uploaded receipt images, extracts structured data with Gemini 3, stores the original image in Google Drive, and appends the parsed result to Google Sheets.

## Features

- Detects receipt images posted in a Discord channel
- Extracts merchant, total, date, taxes, payment method, and line items with Gemini 3
- Uploads the original image to a Google Drive folder
- Appends normalized receipt data to a Google Spreadsheet
- Creates the spreadsheet header row automatically on first boot

## Architecture

1. A Discord user uploads a receipt image.
2. The bot downloads the attachment and sends it to Gemini.
3. Gemini returns structured JSON for the receipt.
4. The bot uploads the source image to Google Drive.
5. The bot appends one row per receipt to Google Sheets.
6. The bot replies in Discord with a short processing summary.

## Setup

### 1. Discord bot

- Create an application in the [Discord Developer Portal](https://discord.com/developers/applications)
- Create a bot user and copy the bot token
- Enable the `MESSAGE CONTENT INTENT`
- Invite the bot with permissions to read messages, read attachments, add reactions, and send messages

### 2. Gemini API

- Create an API key in [Google AI Studio](https://aistudio.google.com/)
- Put the key into `GEMINI_API_KEY`
- The default model is `gemini-3-flash-preview`

### 3. Google Drive and Sheets

- Create a Google Cloud service account with Drive and Sheets API enabled
- Download the JSON key or store its JSON text in an environment variable
- Create a Drive folder for receipt images
- Create a Google Spreadsheet for receipt rows
- Share both the folder and spreadsheet with the service account email

### 4. Environment variables

Copy `.env.example` to `.env` and fill in:

```bash
DISCORD_TOKEN=...
DISCORD_CHANNEL_IDS=123456789012345678,234567890123456789
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3-flash-preview
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
GOOGLE_DRIVE_FOLDER_ID=...
GOOGLE_SHEETS_SPREADSHEET_ID=...
GOOGLE_SHEETS_SHEET_NAME=Receipts
```

You can use `GOOGLE_SERVICE_ACCOUNT_KEY_FILE` instead of `GOOGLE_SERVICE_ACCOUNT_JSON`.

## Development

```bash
npm install
npm run test
npm run build
npm run dev
```

## Spreadsheet columns

The bot writes these columns:

- Discord source metadata
- Original attachment information
- Google Drive file information
- Merchant fields from Gemini
- Totals, tax, currency, payment method, and receipt number
- Raw OCR-like text and serialized line items

## Notes

- Restrict channels with `DISCORD_CHANNEL_IDS`. Leave it empty to process every accessible channel.
- If Gemini cannot read a field confidently, the bot leaves the field blank instead of guessing.
- For production, prefer storing the service account JSON in a secret manager rather than a plaintext `.env`.

## License

[MIT](./LICENSE)
