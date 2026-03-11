<div align="center">
  <img src="./docs/public/brand/harina-hero.svg" alt="Harina Receipt Bot hero" width="100%" />
  <h1>Harina Receipt Bot</h1>
  <p>Discord receipt intake for Gemini, Google Drive, Google Sheets, and migration-friendly dataset backfills.</p>
</div>

[日本語](./README.ja.md)

![Python](https://img.shields.io/badge/Python-3.12-1E3A34?style=for-the-badge&logo=python&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-Receipt%20Extraction-E68B2C?style=for-the-badge)
![Docker Compose](https://img.shields.io/badge/Docker%20Compose-Self--Hosted-36544C?style=for-the-badge&logo=docker&logoColor=white)
![CI](https://img.shields.io/github/actions/workflow/status/Sunwood-ai-labs/harina-v4/ci.yml?branch=main&style=for-the-badge&label=CI)
![License](https://img.shields.io/github/license/Sunwood-ai-labs/harina-v4?style=for-the-badge)

## ✨ Overview

Harina Receipt Bot is a self-hosted Python Discord bot for receipt workflows. It supports two complementary jobs:

- Always-on receipt intake from Discord into Gemini, Google Drive, and Google Sheets
- One-shot historical image backfills for V1, V2, V3 migrations and re-scans after prompt or model updates

## 🚀 Highlights

- Watches receipt images posted in Discord channels
- Extracts merchant, date, totals, tax, payment method, OCR-like text, and line items with Gemini
- Uploads the original image into Google Drive
- Appends one receipt row per image into Google Sheets
- Downloads historical Discord images into a local dataset for migration and replay workflows
- Runs locally with `uv` and on home servers with Docker Compose

## 🔄 Typical Workflows

1. Real-time intake: users upload receipt images and the bot processes them automatically.
2. Data migration: pull historical images from V1, V2, or V3 Discord channels into a local dataset.
3. Re-scan pipeline: rerun older receipts after changing prompts, models, schemas, or extraction logic.

## ⚡ Quick Start

```bash
cp .env.example .env
uv sync
uv run pytest
uv run python -m app.main
```

Required environment variables:

- `DISCORD_TOKEN`
- `GEMINI_API_KEY`
- `GOOGLE_DRIVE_FOLDER_ID`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON` or `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`

## 📦 Dataset Downloader

You can also use the repo as a one-shot Discord image dataset downloader for migrations and replay jobs.

```bash
uv run python -m app.dataset_downloader "https://discord.com/channels/<guild_id>/<channel_id>"
```

Useful examples:

```bash
uv run python -m app.dataset_downloader "https://discord.com/channels/<guild_id>/<channel_id>" --limit 5
uv run python -m app.dataset_downloader "https://discord.com/channels/<guild_id>/<channel_id>" --output-dir ./dataset/v3-backfill
uv run python -m app.dataset_downloader "https://discord.com/channels/<guild_id>/<channel_id>" --overwrite
```

Optional flags:

- `--output-dir ./dataset/discord-images`
- `--limit 500`
- `--include-bots`
- `--overwrite`

The downloader keeps the uploaded filename unchanged. Files are stored under `guild-<name-or-id>/channel-<name-or-id>/message-<id>/attachment-<id>/`, and a `metadata.jsonl` file is written beside the dataset root. If a server or channel name contains Japanese characters, that name segment is skipped and the folder falls back to the numeric ID.

Common use cases:

- Migrate historical images from V1, V2, or V3 before retiring an older workflow
- Build a fixed dataset snapshot for regression tests and evaluation
- Re-scan old receipts after switching Gemini models, prompts, or output schemas

Bot requirements:

- The bot must be in the target server
- The bot needs access to the channel and message history
- `MESSAGE CONTENT INTENT` should be enabled in the Discord Developer Portal so attachment data is available consistently

## 🐳 Docker Compose

```bash
docker compose up -d --build
docker compose logs -f
```

If you use a file-based Google service account key, place it under `./secrets` and set `GOOGLE_SERVICE_ACCOUNT_KEY_FILE=/app/secrets/your-key.json`.

## 📚 Documentation

- [Docs site](https://sunwood-ai-labs.github.io/harina-v4/)
- [Overview](./docs/guide/overview.md)
- [Dataset Downloader](./docs/guide/dataset-downloader.md)
- [Google setup](./docs/guide/google-setup.md)
- [Deployment guide](./docs/guide/deployment.md)

## 🗂 Repository Layout

```text
app/                  Python bot implementation
docs/                 VitePress documentation site
.github/workflows/    CI and GitHub Pages deployment
Dockerfile            Container image definition
docker-compose.yml    Self-hosted runtime
```

## 🛠 Operations Notes

- Leave `DISCORD_CHANNEL_IDS` empty to process every accessible channel
- Use a comma-separated `DISCORD_CHANNEL_IDS` value to restrict intake
- The bot creates the destination sheet header row automatically on startup
- Startup fails fast when required Google settings are missing
- `DISCORD_DATASET_OUTPUT_DIR` sets the default dataset output path for downloader runs

## 💻 Development

```bash
uv sync
uv run pytest
npm --prefix docs install
npm --prefix docs run docs:build
```

## 📄 License

[MIT](./LICENSE)
