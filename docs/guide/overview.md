# Overview

Harina Receipt Bot is a self-hosted Discord bot for receipt capture workflows, plus a one-shot dataset downloader for migration and replay jobs.

## Two operating modes

### 1. Always-on receipt intake

- Monitor Discord messages for image attachments
- Send each receipt image to Gemini for structured extraction
- Upload the original image to a Google Drive folder
- Append one row per receipt into a Google Spreadsheet
- Reply in Discord with a short processing summary

### 2. Historical backfill and re-scan

- Download historical receipt images from Discord into a local dataset
- Preserve the original uploaded filename
- Rebuild datasets from V1, V2, or V3 channels before retiring older workflows
- Replay older receipts after changing Gemini models, prompts, schemas, or downstream logic
- Run a quick Gemini smoke test on a few sample images before larger backfills

## CLI-first packaging

HARINA V4 is now organized around a Python package CLI surface:

- `harina bot run` starts the always-on Discord bot
- `harina dataset download` exports Discord images into a dataset
- `harina dataset smoke-test` checks a few local dataset images with Gemini
- `harina bot upload-test` uploads a real receipt image to Discord and waits for the bot reply

## Processing flow

### Live bot flow

1. A user uploads a receipt image to a watched Discord channel.
2. The bot downloads the image bytes directly from Discord.
3. Gemini returns normalized JSON using a strict prompt.
4. The image is copied into Google Drive for source retention.
5. A matching data row is written into Google Sheets.
6. The bot posts a summary reply back into Discord.

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

This repository is optimized for small-team or personal bookkeeping automation:

- Discord is the input surface people already use
- Gemini handles low-friction OCR plus field extraction
- Drive keeps the original evidence
- Sheets stays friendly for bookkeeping and exports
- The dataset downloader gives you a safe migration and regression path when the system evolves

## Next steps

- Read [CLI](./cli.md) for the operator commands
- Read [Dataset Downloader](./dataset-downloader.md) if you are migrating from V1, V2, or V3
- Read [Gemini Smoke Test](./gemini-smoke-test.md) if you want a quick verification pass on sampled dataset images
- Read [Google Setup](./google-setup.md) before the live bot flow
- Read [Deployment](./deployment.md) when you are ready to run continuously
