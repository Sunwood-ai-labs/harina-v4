# Overview

Harina Receipt Bot is a self-hosted Discord bot for receipt capture workflows.

## What it does

- Monitors Discord messages for image attachments
- Sends each receipt image to Gemini for structured extraction
- Uploads the original image to a Google Drive folder
- Appends one row per receipt into a Google Spreadsheet
- Replies in Discord with a short processing summary

## Processing flow

1. A user uploads a receipt image to a watched Discord channel.
2. The bot downloads the image bytes directly from Discord.
3. Gemini returns normalized JSON using a strict prompt.
4. The image is copied into Google Drive for source retention.
5. A matching data row is written into Google Sheets.
6. The bot posts a summary reply back into Discord.

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
