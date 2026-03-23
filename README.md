<div align="center">
  <img src="./docs/public/brand/harina-hero.webp" alt="Harina Receipt Bot hero" width="280" />
  <h1>Harina Receipt Bot</h1>
  <p>Discord and Google Drive receipt intake for Gemini, Google Drive, and Google Sheets.</p>
</div>

[日本語](./README.ja.md)

![Python](https://img.shields.io/badge/Python-3.12-1E3A34?style=for-the-badge&logo=python&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-Receipt%20Extraction-E68B2C?style=for-the-badge)
![Docker Compose](https://img.shields.io/badge/Docker%20Compose-Self--Hosted-36544C?style=for-the-badge&logo=docker&logoColor=white)
![CI](https://img.shields.io/github/actions/workflow/status/Sunwood-ai-labs/harina-v4/ci.yml?branch=main&style=for-the-badge&label=CI)
![License](https://img.shields.io/github/license/Sunwood-ai-labs/harina-v4?style=for-the-badge)

## Overview

Harina Receipt Bot is a self-hosted Python automation stack for receipt workflows.
It supports two intake paths:

- direct Discord uploads processed by the always-on bot
- Google Drive uploads forwarded into Discord by a watcher service and then processed by the same pipeline

Each receipt goes through a two-stage Gemini pipeline:

1. extract merchant, totals, and line items from the image
2. assign one short bookkeeping category to each line item using a Google Sheets-backed category catalog

## Highlights

- Extract merchant, date, totals, tax, payment method, OCR-like text, and line items with Gemini
- Use a `Categories` sheet as the approved category list for every run
- Normalize categories to short single-word labels such as `野菜`, `惣菜`, and `飲料`
- Allow Gemini to suggest a new category when no existing option fits, then append it back into Sheets
- Store Discord-uploaded images in the main Google Drive archive under `YYYY/MM`
- Move Drive watcher source files into `YYYY/MM` folders inside each processed folder
- Append one bookkeeping row per line item into Google Sheets, including `itemCategory`
- Build formula-driven `Analysis YYYY`, `Analysis All Years`, and `重複確認` Sheets surfaces for dashboards and duplicate review
- Skip duplicate receipts when the same `attachmentName` is already recorded in Google Sheets, with `--rescan` available for intentional reprocessing
- Forward new Google Drive images into a Discord notification channel
- Reply in Discord with category summary, per-item categories, and priced line items
- Move processed Google Drive files into `processed/YYYY/MM` after success
- Resume watcher waits from Discord with `/resume_polling` when the long-running service is paused between scans
- Run locally with `uv` or continuously with Docker Compose

## Typical workflows

1. Discord intake: users upload receipt images to a watched Discord channel and the bot replies with a summary, category totals, and per-item categories.
2. Drive intake: users upload images to a Google Drive inbox folder and the watcher posts them into Discord, writes Sheets line-item rows, and moves the original Drive file into a `processed/YYYY/MM` path.
3. Backfill and replay: operators download historical Discord images into a local dataset and rerun Gemini checks after prompt or model changes.

## Duplicate attachment protection

- HARINA treats `attachmentName` as the primary key for receipt images across the receipt tabs in Google Sheets.
- Discord intake replies with `Receipt Skipped` instead of writing duplicate rows when the same filename is already recorded.
- `drive watch` skips duplicate filenames before Discord notification, avoids writing duplicate rows, and moves the duplicate file into the matching `processed/YYYY/MM` folder.
- `receipt process --rescan` and `drive watch --rescan` bypass the duplicate guard when you intentionally want a replay or backfill.
- If a Drive watcher run fails before processing completes, the file stays in the source folder so it can be retried safely.

## Architecture

![Harina V4 architecture flow](./docs/architecture/harina-v4-flow.svg)

Source: [docs/architecture/harina-v4-flow.drawio](./docs/architecture/harina-v4-flow.drawio)

## Quick start

```bash
cp .env.example .env
uv sync
uv run pytest
uv run harina-v4 google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
uv run harina-v4 google init-resources --env-file .env
uv run harina-v4 google init-drive-watch --env-file .env
uv run harina-v4 bot run
```

Required environment variables for the bot:

- `DISCORD_TOKEN`
- `GEMINI_API_KEY`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SHEETS_CATEGORY_SHEET_NAME` optional, defaults to `Categories`
- `GOOGLE_SERVICE_ACCOUNT_JSON` or `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`
- or `GOOGLE_OAUTH_CLIENT_JSON` / `GOOGLE_OAUTH_CLIENT_SECRET_FILE` plus `GOOGLE_OAUTH_REFRESH_TOKEN`

Required environment variables for the Drive watcher:

- `DISCORD_NOTIFY_CHANNEL_ID`
- `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID`
- `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID`
- `DRIVE_POLL_INTERVAL_SECONDS`

Relevant Gemini model settings:

- `GEMINI_MODEL` powers the always-on `bot run` and `drive watch` services
- `GEMINI_TEST_MODEL` powers verification flows such as `bot upload-test`, `receipt process`, `dataset smoke-test`, and the CLI side of `test docs-public`
- `GEMINI_API_KEY_ROTATION_LIST` adds comma/newline-separated fallback keys for quota rotation and delayed retry handling

## CLI

```bash
uv run harina-v4 --help
```

Core commands:

```bash
uv run harina-v4 bot run
uv run harina-v4 bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
uv run harina-v4 receipt process ./sample-receipt.jpg --skip-google-write
uv run harina-v4 receipt process ./sample-receipt.jpg --rescan
uv run harina-v4 google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
uv run harina-v4 google init-resources --env-file .env
uv run harina-v4 google init-drive-watch --env-file .env
uv run harina-v4 google sync-analysis
uv run harina-v4 drive watch --once
uv run harina-v4 drive watch --once --rescan
uv run harina-v4 dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 50
uv run harina-v4 dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
uv run harina-v4 test docs-public
```

## Google setup

Use OAuth refresh tokens for personal Gmail accounts whenever possible.
After the one-time browser login, HARINA can bootstrap both the receipt storage targets and the Drive watcher folders from the CLI.

```bash
uv run harina-v4 google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
uv run harina-v4 google init-resources --env-file .env
uv run harina-v4 google init-drive-watch --env-file .env
```

For a dedicated Google agent account, move the OAuth consent screen to `In production` before long-lived operations. Google documents that external apps left in `Testing` can issue refresh tokens that expire after 7 days, which shows up in HARINA as `invalid_grant: Token has been expired or revoked.` See the [Google OAuth 2.0 guide](https://developers.google.com/identity/protocols/oauth2).

If you need to recover an expired or revoked refresh token, you can still use `google oauth-login`, or you can split the flow into `oauth-start` and `oauth-finish` when you want to drive an already logged-in browser session:

```bash
uv run harina-v4 google oauth-start --oauth-client-secret-file ./secrets/harina-oauth-client.json --session-file .harina-google-oauth-session.json
uv run harina-v4 google oauth-finish --session-file .harina-google-oauth-session.json --redirect-url "http://127.0.0.1:8765/?state=...&code=..."
```

When you operate HARINA from Codex, the [`logged-in-google-chrome` helper](https://github.com/Sunwood-ai-labs/logged-in-google-chrome-skill) can automate the dedicated Chrome launch and consent-screen steps for this recovery flow.

`google init-drive-watch` creates or reuses:

- a Drive inbox folder for new uploads
- a Drive processed folder for files already handled
- optional `.env` entries for folder IDs, URLs, and poll interval

During live watcher runs, HARINA creates `YYYY/MM` subfolders under the processed folder on demand.

Useful flags:

- `--source-folder-name "Harina V4 Drive Inbox"`
- `--processed-folder-name "Harina V4 Drive Processed"`
- `--parent-folder-id <folder_id>`
- `--poll-interval-seconds 60`
- `--share-with-email you@example.com`
- `--env-file .env`

`google init-resources` also ensures two bootstrap spreadsheet tabs:

- `Receipts` as the fallback/bootstrap receipt tab name stored in `.env`
- `Categories` for the approved category catalog that Gemini reads on every write-enabled run

HARINA can also rebuild analysis-only tabs such as `Analysis 2025`, `Analysis 2026`, `Analysis All Years`, and the persistent duplicate-control sheet `重複確認`. Use `uv run harina-v4 google sync-analysis` when you want to refresh those analysis surfaces manually.

When HARINA appends receipt rows, it auto-creates year-based tabs such as `2025` and `2026`. It chooses the purchase year when available, falls back to the processed timestamp when needed, and still uses `attachmentName` dedup checks across all receipt tabs except `Categories`.

The default category seed uses short single-word labels such as `野菜`, `肉`, `惣菜`, `飲料`, and `手数料`.
If Gemini returns a category that is not already in `Categories`, HARINA can append it automatically for future runs.

## Category workflow

1. Stage 1 extracts normalized receipt fields and line items from the image.
2. Stage 2 reads the current `Categories` sheet and asks Gemini to assign one category per line item.
3. If no existing category fits, Gemini may propose one short new category name.
4. HARINA appends any new category into `Categories` and writes `itemCategory` into year-based receipt tabs such as `2025`.
5. Discord replies show both a category summary and a `商品カテゴリ` section so each product-category pair is visible.

## Gemini model lanes

- `bot run` and `drive watch` use `GEMINI_MODEL` as the production lane.
- `bot upload-test`, `receipt process`, `dataset smoke-test`, and `test docs-public` use `GEMINI_TEST_MODEL` as the verification lane.
- `GEMINI_API_KEY_ROTATION_LIST` extends the retry lane with additional keys after the primary `GEMINI_API_KEY`.
- HARINA retries transient Gemini failures locally for up to 5 attempts per key with a 60-second backoff.
- Daily quota exhaustion rotates to the next key immediately.
- After every configured key is exhausted, `receipt-bot` waits 1 hour once and `drive-watcher` waits 12 hours once before retrying from the first key again.

## Drive watcher flow

1. Upload an image into `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID`.
2. Run `uv run harina-v4 drive watch --once` for a one-shot check, or keep the watcher running continuously.
3. HARINA downloads the Drive image, runs extraction plus categorization, writes line-item rows into year-based receipt tabs, posts the image into `DISCORD_NOTIFY_CHANNEL_ID`, and moves the original Drive file into `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID/YYYY/MM`.
4. If the same filename is already recorded in Sheets, HARINA skips Discord notification and row writes, then moves the duplicate directly into the matching `YYYY/MM` processed folder.
5. On successful processing, HARINA chooses the processed subfolder from `purchaseDate` when available and otherwise falls back to the Drive file timestamp. Duplicate-skip moves use the Drive file timestamp because extraction is skipped.
6. If processing fails before completion, HARINA leaves the source file in place for a later retry.

When `DISCORD_SYSTEM_LOG_CHANNEL_ID` is configured, repeated `HARINA Scan Summary` posts are suppressed for idle scan cycles when both the scan counters and backlog snapshot are unchanged. Summaries still post when files are processed, skipped, or failed, or when the backlog changes.
When Gemini usage metadata is available, the Drive watcher's `Drive Receipt // ...` embed also includes `Gemini Model` and `API Cost (est.)`. If every rotation key is exhausted, the watcher posts `HARINA Watch Status` before its delayed retry window.
The watcher also exposes `/resume_polling`, which lets operators with `Manage Server` permission clear the current poll wait or delayed Gemini retry wait from Discord without restarting the containers.

## Docker Compose

```bash
docker compose up -d --build
docker compose logs -f receipt-bot
docker compose logs -f drive-watcher
```

When `.env` changes, especially `GOOGLE_OAUTH_REFRESH_TOKEN`, recreate the services instead of using `docker compose restart`, because existing containers keep their original environment snapshot:

```bash
docker compose up -d --force-recreate receipt-bot drive-watcher
```

If you changed code as well as `.env`, rebuild and recreate together:

```bash
docker compose up -d --build --force-recreate receipt-bot drive-watcher
```

The Compose stack runs two services:

- `receipt-bot` for direct Discord intake
- `drive-watcher` for polling the Google Drive inbox folder

If you use file-based Google credentials, place them under `./secrets` and point `GOOGLE_OAUTH_CLIENT_SECRET_FILE` or `GOOGLE_SERVICE_ACCOUNT_KEY_FILE` at the mounted `/app/secrets/...` path.
For a production-like smoke test, upload one unique image into a route such as `Bob`, then confirm a new `HARINA V4 Intake // Bob` post, a matching `HARINA Progress // Bob` system-log entry, and a move into `Bob/_processed/YYYY/MM`.
For long-running watcher deployments, do not expect a heartbeat-style `HARINA Scan Summary` on every poll. Idle polls with no observable change stay quiet, so use startup/progress messages or `docker compose logs` when you need to confirm the service is alive.

## Documentation

- [Docs site](https://sunwood-ai-labs.github.io/harina-v4/)
- [Overview](./docs/guide/overview.md)
- [CLI](./docs/guide/cli.md)
- [Google setup](./docs/guide/google-setup.md)
- [Deployment](./docs/guide/deployment.md)
- [Dataset Downloader](./docs/guide/dataset-downloader.md)
- [Gemini Smoke Test](./docs/guide/gemini-smoke-test.md)
- [Release Notes v4.4.0](./docs/guide/release-notes-v4.4.0.md)
- [What's New In Harina v4.4.0](./docs/guide/whats-new-v4.4.0.md)

## Development

```bash
uv sync
uv run pytest
uv run harina-v4 --help
npm --prefix docs install
npm --prefix docs run docs:build
```

## License

[MIT](./LICENSE)
