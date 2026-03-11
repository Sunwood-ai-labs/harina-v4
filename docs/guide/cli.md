# CLI

HARINA V4 is packaged around a Python CLI called `harina-v4`.
The shorter `harina` command remains available as a compatibility alias.

## Why use the CLI surface

- Keep bot operations, migrations, replays, and verification under one command namespace
- Reuse the same package logic for the always-on bot and operator workflows
- Make local runs, CI checks, and future automation easier to standardize

## Basic help

```bash
uv run harina-v4 --help
```

## Receipt commands

Process a local receipt image through the CLI-first pipeline:

```bash
uv run harina-v4 receipt process ./sample-receipt.jpg --skip-google-write
```

Notes:

- `receipt process` uses the same Gemini-centered receipt pipeline as the Discord bot
- `--skip-google-write` is the easiest way to debug extraction locally with only `GEMINI_API_KEY`
- Omit `--skip-google-write` when you want the CLI to also upload to Drive and append to Sheets

## Bot commands

Run the always-on Discord bot:

```bash
uv run harina-v4 bot run
```

## Google commands

Run the one-time OAuth login flow and save a refresh token:

```bash
uv run harina-v4 google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
```

Create or reuse the Drive folder and spreadsheet:

```bash
uv run harina-v4 google init-resources --env-file .env
```

## Dataset commands

Download Discord images into a dataset:

```bash
uv run harina-v4 dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 50
```

Run a Gemini smoke test on local dataset images:

```bash
uv run harina-v4 dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

## Discord upload test

Upload a real image into Discord and wait for the bot reply:

```bash
uv run harina-v4 bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

Notes:

- The command posts a real message into the specified Discord channel
- The bot processes that message using the same package logic as `harina-v4 bot run`
- Test messages are marked with `DISCORD_TEST_MESSAGE_PREFIX`, which defaults to `[HARINA-TEST]`
- `DISCORD_TEST_CHANNEL_ID` lets you keep a fixed test channel and omit `--channel-id`
- Use a safe test channel because this command touches live Discord, Gemini, Drive, and Sheets

## Recommended operator flow

1. Use `harina-v4 receipt process --skip-google-write` to debug extraction against a local image.
2. Use `harina-v4 dataset download` to export a small sample.
3. Use `harina-v4 dataset smoke-test` to validate Gemini on about 2 images.
4. Use `harina-v4 google oauth-login` if you are on personal Gmail.
5. Use `harina-v4 google init-resources` to create or confirm Drive and Sheets targets.
6. Use `harina-v4 bot upload-test` to confirm live Discord behavior.
7. Use `harina-v4 bot run` for the continuous production path.
