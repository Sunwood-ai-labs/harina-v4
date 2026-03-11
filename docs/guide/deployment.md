# Deployment

Use `harina bot run` for the always-on bot service. Use `harina dataset download` when you only need a one-shot migration or re-scan export.
Use `harina dataset smoke-test` when you want a quick Gemini verification pass against a few local dataset images.

## Local development

```bash
uv sync
uv run pytest
uv run harina bot run
```

## One-shot downloader runs

```bash
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 50
```

## Gemini smoke test runs

```bash
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

## Discord upload test runs

```bash
uv run harina bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

## Docker Compose

1. Copy `.env.example` to `.env`
2. Fill in the Discord, Gemini, Drive, and Sheets settings
3. If you use a JSON key file, place it under `./secrets`
4. Start the service

```bash
docker compose up -d --build
docker compose logs -f
```

## Required environment variables

- `DISCORD_TOKEN`
- `GEMINI_API_KEY`
- `GOOGLE_DRIVE_FOLDER_ID`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON` or `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`

## Operational notes

- Leave `DISCORD_CHANNEL_IDS` empty to watch all accessible channels
- Set `DISCORD_CHANNEL_IDS` to a comma-separated list to limit intake
- The bot creates the target sheet header row automatically
- Startup fails fast when required configuration is missing
- `DISCORD_DATASET_OUTPUT_DIR` sets the default output root for downloader runs
