# Deployment

Use `harina bot run` for the always-on Discord bot service.
Use `harina drive watch` for the Google Drive watcher service.
Use `harina dataset download` or `harina dataset smoke-test` for one-shot migration and verification jobs.

## Local development

```bash
uv sync
uv run pytest
uv run harina-v4 bot run
```

## One-shot checks

Discord upload path:

```bash
uv run harina-v4 bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

Drive watcher path:

```bash
uv run harina-v4 drive watch --once
```

Gemini smoke test:

```bash
uv run harina-v4 dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

## Docker Compose

1. Copy `.env.example` to `.env`
2. Fill in Discord, Gemini, Drive, and Sheets settings
3. Run `harina-v4 google init-resources --env-file .env`
4. Run `harina-v4 google init-drive-watch --env-file .env`
5. If you use JSON key files, place them under `./secrets`
6. Start the services

```bash
docker compose up -d --build
docker compose logs -f receipt-bot
docker compose logs -f drive-watcher
```

If you update `.env`, especially `GOOGLE_OAUTH_REFRESH_TOKEN`, recreate the services instead of using `docker compose restart`:

```bash
docker compose up -d --force-recreate receipt-bot drive-watcher
```

If code changed too, rebuild and recreate in one step:

```bash
docker compose up -d --build --force-recreate receipt-bot drive-watcher
```

## Required environment variables

For the receipt bot:

- `DISCORD_TOKEN`
- `GEMINI_API_KEY`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- Google credentials via service account or OAuth refresh token

For the Drive watcher:

- `DISCORD_NOTIFY_CHANNEL_ID`
- `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID`
- `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID`
- `DRIVE_POLL_INTERVAL_SECONDS`

## Operational notes

- Leave `DISCORD_CHANNEL_IDS` empty to watch all accessible Discord channels
- Set `DISCORD_CHANNEL_IDS` to a comma-separated list to limit Discord intake
- The bot creates the target sheet header row automatically
- The watcher posts image notifications into `DISCORD_NOTIFY_CHANNEL_ID`
- Successfully handled Drive files move into the processed folder
- Do not expect a heartbeat-style `HARINA Scan Summary` on every poll; unchanged idle polls are intentionally suppressed to reduce Discord noise
- Use startup/progress system-log messages or container logs when you need a liveness check between active scans
- If the watcher should be active but no system-log messages appear at all, verify `DISCORD_SYSTEM_LOG_CHANNEL_ID` and Discord connectivity in the container logs
- Startup fails fast when required configuration is missing
- `DISCORD_DATASET_OUTPUT_DIR` sets the default output root for downloader runs
- A production-like smoke test is to upload one unique image into the `Bob` source folder and confirm a new `HARINA V4 Intake // Bob` post, a matching `HARINA Progress // Bob` system-log entry, and a move into `Bob/_processed/YYYY/MM`
