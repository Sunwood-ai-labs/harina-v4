# CLI

HARINA V4 is packaged around a Python CLI called `harina-v4`.
The shorter `harina` command remains available as a compatibility alias.

## Why use the CLI surface

- Keep bot operations, Drive watcher operations, migrations, and verification under one command namespace
- Reuse the same package logic for the always-on services and operator workflows
- Make local runs, CI checks, and Docker automation easier to standardize

## Basic help

```bash
uv run harina-v4 --help
```

## Receipt commands

Process a local receipt image through the CLI-first pipeline:

```bash
uv run harina-v4 receipt process ./sample-receipt.jpg --skip-google-write
```

Run both the CLI path and the Discord path against every sample under `docs/public/test`:

```bash
uv run harina-v4 test docs-public
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

Upload a real image into Discord and wait for the bot reply:

```bash
uv run harina-v4 bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

Notes:

- `test docs-public` scans every supported image under `docs/public/test`
- The default `--mode both` runs the local CLI pipeline and the live Discord upload check in one pass
- Use `--mode cli` or `--mode discord` when you want to isolate one path
- Discord-side checks default to `DISCORD_TEST_CHANNEL_ID` unless `--channel-id` is provided

## Drive watcher commands

Run one watcher scan and exit:

```bash
uv run harina-v4 drive watch --once
```

Run the watcher continuously:

```bash
uv run harina-v4 drive watch
```

Notes:

- `drive watch` reads images from `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID`
- Notifications go to `DISCORD_NOTIFY_CHANNEL_ID`
- Successfully handled files move into `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID`
- `DRIVE_POLL_INTERVAL_SECONDS` controls the polling interval

## Google commands

Run the one-time OAuth login flow and save a refresh token:

```bash
uv run harina-v4 google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
```

Create or reuse the main Drive folder and spreadsheet:

```bash
uv run harina-v4 google init-resources --env-file .env
```

Create or reuse the Drive watcher folders:

```bash
uv run harina-v4 google init-drive-watch --env-file .env
```

Useful flags for watcher setup:

- `--source-folder-name "Harina V4 Drive Inbox"`
- `--processed-folder-name "Harina V4 Drive Processed"`
- `--parent-folder-id <folder_id>`
- `--poll-interval-seconds 60`

## Dataset commands

Download Discord images into a dataset:

```bash
uv run harina-v4 dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 50
```

Run a Gemini smoke test on local dataset images:

```bash
uv run harina-v4 dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

## Recommended operator flow

1. Use `harina-v4 google oauth-login` if you are on personal Gmail.
2. Use `harina-v4 google init-resources` to create or confirm Drive and Sheets targets.
3. Use `harina-v4 google init-drive-watch` to provision the Drive watcher folders.
4. Put the receipt images you want to verify under `docs/public/test`.
5. Use `harina-v4 test docs-public` to exercise both the CLI path and the Discord path.
6. Use `harina-v4 drive watch --once` to confirm one-shot Drive watcher behavior.
7. Use `harina-v4 bot run` and `harina-v4 drive watch` for the continuous production path.
