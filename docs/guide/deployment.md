# Deployment

## Local development

```bash
uv sync
uv run pytest
uv run python -m app.main
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
