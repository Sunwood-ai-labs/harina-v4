# Overview

Harina Receipt Bot is a self-hosted automation stack for receipt capture, OCR, and bookkeeping exports.
It supports both Discord-first and Google Drive-first intake.

## Two operating modes

### 1. Discord receipt intake

- Watch Discord channels for image attachments
- Send each receipt image to Gemini for structured extraction
- Upload the original image to Google Drive
- Append one row per receipt into Google Sheets
- Reply in Discord with a short processing summary

### 2. Google Drive watcher intake

- Poll a Google Drive inbox folder for new image uploads
- Download the image directly from Drive
- Extract fields with Gemini and append them into Google Sheets
- Post the image and summary into a Discord notification channel
- Move the file into a processed Drive folder after success

## CLI-first packaging

HARINA V4 is organized around a Python package CLI surface:

- `harina bot run` starts the always-on Discord intake bot
- `harina drive watch` runs the Google Drive watcher
- `harina google init-resources` creates the main Drive folder and spreadsheet
- `harina google init-drive-watch` creates the Drive watcher inbox and processed folders
- `harina dataset download` exports Discord images into a dataset
- `harina dataset smoke-test` checks a few local dataset images with Gemini
- `harina bot upload-test` uploads a real receipt image to Discord and waits for the bot reply

## Architecture diagram

![Harina V4 architecture flow](../architecture/harina-v4-flow.svg)

## Processing flow

### Discord bot flow

1. A user uploads a receipt image to a watched Discord channel.
2. The bot downloads the image bytes directly from Discord.
3. Gemini returns normalized JSON using a strict prompt.
4. The image is copied into Google Drive for source retention.
5. A matching data row is written into Google Sheets.
6. The bot posts a summary reply back into Discord.

### Drive watcher flow

1. A user uploads a receipt image into the Drive inbox folder.
2. The watcher polls Drive and downloads new image files.
3. Gemini extracts normalized receipt fields.
4. HARINA appends one row into Google Sheets.
5. The watcher posts the image and summary into `DISCORD_NOTIFY_CHANNEL_ID`.
6. The Drive file is moved into the processed folder.

### Downloader flow

1. You pass a Discord channel URL into `app.dataset_downloader`.
2. The downloader walks message history with the bot token.
3. Image attachments are saved into a dataset folder tree.
4. `metadata.jsonl` is generated for replay, auditing, or downstream batch processing.

## Runtime stack

- Python 3.12
- `discord.py`
- `google-genai`
- Google Drive API and Google Sheets API
- `uv` for local dependency management
- Docker Compose for always-on deployment

## Why this shape works

- Discord stays the operator-friendly notification surface
- Gemini handles OCR plus structured extraction
- Drive keeps original evidence and supports inbox-style uploads
- Sheets stays easy to audit and export
- The dataset downloader gives you a safe migration and regression path

## Next steps

- Read [CLI](./cli.md) for the operator commands
- Read [Google Setup](./google-setup.md) before the live bot or Drive watcher flow
- Read [Deployment](./deployment.md) when you are ready to run continuously
- Read [Dataset Downloader](./dataset-downloader.md) if you are migrating from V1, V2, or V3
- Read [Gemini Smoke Test](./gemini-smoke-test.md) for quick dataset verification
