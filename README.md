<div align="center">
  <img src="./docs/public/brand/harina-hero.webp" alt="Harina Receipt Bot hero" width="280" />
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
uv run harina bot run
```

Required environment variables:

- `DISCORD_TOKEN`
- `GEMINI_API_KEY`
- `GOOGLE_DRIVE_FOLDER_ID`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON` or `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`
- or `GOOGLE_OAUTH_CLIENT_JSON` / `GOOGLE_OAUTH_CLIENT_SECRET_FILE` plus `GOOGLE_OAUTH_REFRESH_TOKEN`

## 🧰 HARINA CLI

This repository now exposes a Python package CLI called `harina`.

```bash
uv run harina --help
```

Core commands:

```bash
uv run harina bot run
uv run harina google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
uv run harina google init-resources --service-account-key-file ./secrets/harina-v4-bot.json --env-file .env
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 50
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
uv run harina bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

Why this shape is useful:

- The CLI becomes the stable operator surface for V4 workflows
- The Discord bot can reuse the same package logic instead of hiding behavior only inside event handlers
- Migration, replay, and Discord-side verification can all run from one installed tool

## ☁ Google Bootstrap

You only need browser-based Google login once to create the Cloud project, enable APIs, and download the service account JSON key. After that, HARINA can create its own Drive folder and spreadsheet from the CLI.

If you are operating HARINA through Codex, the browser-side Google Cloud Console work can also be driven with the `logged-in-google-chrome` skill so project creation, OAuth client setup, and token issuance stay reproducible.

For personal Gmail setups, OAuth refresh tokens are usually the right path:

```bash
uv run harina google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
uv run harina google init-resources --env-file .env
```

```bash
uv run harina google init-resources --service-account-key-file ./secrets/harina-v4-bot.json --env-file .env
```

Useful examples:

```bash
uv run harina google init-resources --service-account-key-file ./secrets/harina-v4-bot.json
uv run harina google init-resources --service-account-key-file ./secrets/harina-v4-bot.json --share-with-email you@example.com
uv run harina google init-resources --service-account-key-file ./secrets/harina-v4-bot.json --folder-name "Harina V4 Receipts" --spreadsheet-title "Harina V4 Receipts" --sheet-name Receipts --env-file .env
```

What this command does:

- Creates or reuses a Drive folder owned by the service account
- Creates or reuses a spreadsheet owned by the service account
- Ensures the target sheet tab and header row exist
- Optionally shares both resources with your Google account
- Prints the environment values and can write IDs plus URLs into `.env`

Important note:

- Personal Google Drive accounts often reject service-account-owned uploads because service accounts do not have Drive storage quota there
- If you are using a personal Gmail account, prefer an OAuth refresh-token flow for Drive and Sheets
- Keep service accounts for Google Workspace shared drives or admin-managed environments

Recommended `.env` metadata for later lookup:

- `GOOGLE_CLOUD_PROJECT_ID`
- `GOOGLE_CLOUD_PROJECT_NUMBER`
- `GOOGLE_CLOUD_CONSOLE_URL`
- `GOOGLE_CLOUD_CREDENTIALS_URL`
- `GOOGLE_CLOUD_AUTH_OVERVIEW_URL`
- `GOOGLE_OAUTH_CLIENT_ID`

## 📦 Dataset Downloader

You can also use the repo as a one-shot Discord image dataset downloader for migrations and replay jobs.

```bash
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>"
```

Useful examples:

```bash
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 5
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --output-dir ./dataset/v3-backfill
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --overwrite
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

## 🧪 Gemini Smoke Test

After downloading a dataset, you can run a quick Gemini receipt-recognition check against about 2 sample images.

```bash
uv run harina dataset smoke-test --limit 2
```

Useful examples:

```bash
uv run harina dataset smoke-test --limit 2
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2 --output ./artifacts/gemini-smoke-test.json
```

Notes:

- The smoke test uses `GEMINI_API_KEY` and `GEMINI_MODEL`
- The default model in this repo is `gemini-3-flash-preview`
- Duplicate files are skipped by content hash unless you add `--allow-duplicates`
- Results are printed as JSON and can optionally be written to a file

## 🤖 Discord Upload Test

You can also test the live Discord bot path from the CLI by uploading a real receipt image to a Discord channel and waiting for the bot reply.

```bash
uv run harina bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

Notes:

- The command uploads an actual message into the target Discord channel
- The bot processes that message using the same package logic as the always-on runtime
- Test messages are prefixed with `DISCORD_TEST_MESSAGE_PREFIX`, which defaults to `[HARINA-TEST]`
- `DISCORD_TEST_CHANNEL_ID` lets you omit `--channel-id` for a fixed test channel
- This command is intended for real environment verification, so run it against a safe test channel

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
- [CLI](./docs/guide/cli.md)
- [Dataset Downloader](./docs/guide/dataset-downloader.md)
- [Gemini Smoke Test](./docs/guide/gemini-smoke-test.md)
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
- `DISCORD_TEST_CHANNEL_ID` sets the default Discord channel for `harina bot upload-test`
- `DISCORD_TEST_MESSAGE_PREFIX` controls which self-authored Discord messages are treated as CLI test uploads

## 💻 Development

```bash
uv sync
uv run pytest
uv run harina --help
npm --prefix docs install
npm --prefix docs run docs:build
```

## 📄 License

[MIT](./LICENSE)
