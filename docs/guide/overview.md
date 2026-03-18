# Overview

Harina Receipt Bot is a self-hosted automation stack for receipt capture, OCR, and bookkeeping exports.
It supports both Discord-first and Google Drive-first intake.

Every receipt uses a staged Gemini workflow:

1. extract normalized receipt fields and line items
2. categorize each line item against a Google Sheets-backed category catalog

## Two operating modes

### 1. Discord receipt intake

- Watch Discord channels for image attachments
- Skip duplicate filenames already recorded in Google Sheets unless you explicitly rerun with `--rescan`
- Send each receipt image through extraction and categorization
- Upload the original image to the main Google Drive archive under `YYYY/MM`
- Append one row per line item into Google Sheets
- Reply in Discord with category summary, per-item categories, and priced line items

### 2. Google Drive watcher intake

- Poll a Google Drive inbox folder for new image uploads
- Skip duplicate filenames already recorded in Google Sheets before notifying Discord
- Download the image directly from Drive
- Extract fields, categorize the line items, and append them into Google Sheets
- Post the image and summary into a Discord notification channel
- Move the file into a processed `YYYY/MM` Drive folder after success

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
3. If `attachmentName` is already present in Google Sheets, the bot stops early and replies with `Receipt Skipped`.
4. Gemini returns normalized JSON using a strict prompt.
5. Gemini receives the extracted JSON plus the current `Categories` sheet and assigns one category per line item.
6. The image is copied into Google Drive for source retention under a `YYYY/MM` folder path.
7. One row per line item is written into a year-based receipt tab such as `2025`, and any new category can be appended into `Categories`.
8. The bot posts a summary reply back into Discord with `カテゴリ`, `商品カテゴリ`, and `明細`.

### Drive watcher flow

1. A user uploads a receipt image into the Drive inbox folder.
2. The watcher polls Drive and downloads new image files.
3. If the filename is already present in Google Sheets, HARINA skips Discord notification and row writes, then moves the duplicate file into the matching `processed/YYYY/MM` folder.
4. Gemini extracts normalized receipt fields and then categorizes each line item.
5. HARINA appends one row per line item into a year-based receipt tab such as `2025`.
6. HARINA can append newly proposed categories into `Categories`.
7. The watcher posts the image and summary into `DISCORD_NOTIFY_CHANNEL_ID`, and the Drive result embed can include `Gemini Model` plus `API Cost (est.)` when Gemini usage metadata is available.
8. The Drive file is moved into a `YYYY/MM` folder under the route's processed folder.
9. If processing fails before completion, the file stays in the source folder for a later retry.
10. When `DISCORD_SYSTEM_LOG_CHANNEL_ID` is configured, unchanged idle scan cycles do not post a fresh `HARINA Scan Summary`; activity and backlog changes still appear in the system log.

### Downloader flow

1. You pass a Discord channel URL into `app.dataset_downloader`.
2. The downloader walks message history with the bot token.
3. Image attachments are saved into a dataset folder tree.
4. `metadata.jsonl` is generated for replay, auditing, or downstream batch processing.

## Duplicate attachment protection

- HARINA uses `attachmentName` as the receipt-image primary key across the year-based receipt tabs in Google Sheets.
- `receipt process` and Discord intake skip duplicates by default and only replay them when `--rescan` is enabled.
- `drive watch` skips duplicates before Discord notification, avoids duplicate row writes, and still routes the file into the matching `processed/YYYY/MM` folder.
- Duplicate lookup scans every non-`Categories` receipt tab, not just the fallback `Receipts` tab.
- The duplicate guard is intentionally filename-based, so keep source filenames stable when you want idempotent re-runs.

## Drive archive layout

- Discord and CLI uploads are copied into the main Drive archive folder as `GOOGLE_DRIVE_FOLDER_ID/YYYY/MM`.
- Discord and CLI uploads choose `YYYY/MM` from `purchaseDate` when available and otherwise fall back to the current processing month.
- Drive watcher intake keeps the original Drive file and moves it into `processed_folder/YYYY/MM` after success or duplicate-skip.
- Successful Drive watcher moves use `purchaseDate` when Gemini extracts one and otherwise fall back to the Drive file timestamp.
- Duplicate-skip Drive moves use the Drive file timestamp because extraction is skipped.

## Gemini model lanes

- `bot run` and `drive watch` use `GEMINI_MODEL`.
- `receipt process`, `bot upload-test`, `dataset smoke-test`, and the CLI/Discord verification paths under `test docs-public` use `GEMINI_TEST_MODEL`.
- `GEMINI_API_KEY_ROTATION_LIST` adds additional fallback keys after the primary `GEMINI_API_KEY`.
- HARINA retries transient Gemini errors up to 5 times per key with a 60-second local backoff.
- Daily quota exhaustion rotates to the next key immediately.
- After all configured keys are exhausted, `receipt-bot` waits 1 hour once and `drive-watcher` waits 12 hours once before restarting from the first key; the watcher reports that pause through `HARINA Watch Status`.

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
- Google Sheets provides the live approved category catalog
- Drive keeps original evidence and supports inbox-style uploads
- Sheets stays easy to audit and export, with year-based receipt tabs plus a separate `Categories` catalog
- The dataset downloader gives you a safe migration and regression path

## Next steps

- Read [CLI](./cli.md) for the operator commands
- Read [Google Setup](./google-setup.md) before the live bot or Drive watcher flow
- Read [Deployment](./deployment.md) when you are ready to run continuously
- Read [Release Notes v4.3.0](./release-notes-v4.3.0.md) for the latest shipped changes
- Read [What's New In Harina v4.3.0](./whats-new-v4.3.0.md) for the operator-facing walkthrough
- Read [Dataset Downloader](./dataset-downloader.md) if you are migrating from V1, V2, or V3
- Read [Gemini Smoke Test](./gemini-smoke-test.md) for quick dataset verification
