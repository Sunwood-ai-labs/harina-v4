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

Force a replay even when the same filename is already recorded in Google Sheets:

```bash
uv run harina-v4 receipt process ./sample-receipt.jpg --rescan
```

Run both the CLI path and the Discord path against every sample under `docs/public/test`:

```bash
uv run harina-v4 test docs-public
```

Notes:

- `receipt process` uses the same two-stage Gemini pipeline as the Discord bot, but it resolves `GEMINI_TEST_MODEL`
- when Google writes are enabled, `receipt process` skips duplicate filenames already present in Sheets
- use `--rescan` when you intentionally want to replay a receipt with the same filename
- `--skip-google-write` is the easiest way to debug locally with only `GEMINI_API_KEY`
- when `--skip-google-write` is enabled, HARINA cannot read the Sheets-backed category catalog and Gemini will create short freeform category names
- omit `--skip-google-write` when you want the CLI to upload to Drive, append to Sheets, and categorize against the live `Categories` sheet

## Bot commands {#bot-commands}

Run the always-on Discord bot:

```bash
uv run harina-v4 bot run
```

Upload a real image into Discord and wait for the bot reply:

```bash
uv run harina-v4 bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

You can also upload multiple images in one message:

```bash
uv run harina-v4 bot upload-test --channel-id <channel_id> --image ./docs/public/test/one/IMG_8923.jpg ./docs/public/test/two/IMG_9780.jpg
```

Notes:

- `test docs-public` scans every supported image under `docs/public/test`
- When `docs/public/test` contains subdirectories such as `one/` and `two/`, each folder is treated as a separate test case
- The default `--mode both` runs the local CLI pipeline and the live Discord upload check in one pass
- Use `--mode cli` or `--mode discord` when you want to isolate one path
- `bot run` resolves `GEMINI_MODEL`, while `bot upload-test` resolves `GEMINI_TEST_MODEL`
- Discord-side checks default to `DISCORD_TEST_CHANNEL_ID` unless `--channel-id` is provided
- successful Discord replies now include `カテゴリ`, `商品カテゴリ`, and `明細`

- when the filename already exists in Sheets, the bot replies with `Receipt Skipped` and an `Open Sheet` link instead of processing the receipt again

## Drive watcher commands

Run one watcher scan and exit:

```bash
uv run harina-v4 drive watch --once
```

Force a replay scan even when duplicate filenames are already recorded in Google Sheets:

```bash
uv run harina-v4 drive watch --once --rescan
```

Run the watcher continuously:

```bash
uv run harina-v4 drive watch
```

Notes:

- `drive watch` reads images from `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID`
- Notifications go to `DISCORD_NOTIFY_CHANNEL_ID`
- Successfully handled files move into `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID/YYYY/MM`
- Duplicate filenames already present in Sheets are skipped before Discord notification and then moved into the matching processed `YYYY/MM` folder
- Successful watcher moves choose the processed subfolder from `purchaseDate` when available and otherwise fall back to the Drive file timestamp
- Duplicate-skip watcher moves use the Drive file timestamp because extraction is skipped
- Use `--rescan` when you intentionally want to reprocess duplicate filenames
- Files that fail before processing completes stay in the source folder for a later retry
- `DRIVE_POLL_INTERVAL_SECONDS` controls the polling interval
- When `DISCORD_SYSTEM_LOG_CHANNEL_ID` is set, repeated unchanged `HARINA Scan Summary` embeds are suppressed for idle polls
- The Drive result embed can include `Gemini Model` and `API Cost (est.)` when Gemini usage metadata is available
- If every rotation key is exhausted, the watcher posts `HARINA Watch Status` and waits 12 hours once before retrying from the first key again
- Active scan cycles and backlog changes still produce system-log updates

## Google commands

Run the one-time OAuth login flow and save a refresh token:

```bash
uv run harina-v4 google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
```

Generate an authorization URL first when you want to complete the consent flow in an already logged-in browser session:

```bash
uv run harina-v4 google oauth-start --oauth-client-secret-file ./secrets/harina-oauth-client.json --session-file .harina-google-oauth-session.json
```

Finish the split flow with the final redirect URL that contains the authorization code:

```bash
uv run harina-v4 google oauth-finish --session-file .harina-google-oauth-session.json --redirect-url "http://127.0.0.1:8765/?state=...&code=..."
```

Create or reuse the main Drive folder and spreadsheet:

```bash
uv run harina-v4 google init-resources --env-file .env
```

Notes:

- `google init-resources` ensures both fallback/bootstrap tabs `Receipts` and `Categories`
- Receipt appends auto-create year tabs such as `2025` and `2026`
- `GOOGLE_SHEETS_CATEGORY_SHEET_NAME` defaults to `Categories`
- `Categories` is seeded with short single-word labels such as `野菜`, `惣菜`, and `飲料`

Create or reuse the Drive watcher folders:

```bash
uv run harina-v4 google init-drive-watch --env-file .env
```

Useful flags for watcher setup:

- `--source-folder-name "Harina V4 Drive Inbox"`
- `--processed-folder-name "Harina V4 Drive Processed"`
- `--parent-folder-id <folder_id>`
- `--poll-interval-seconds 60`

Google auth notes:

- Use `google oauth-start` plus `google oauth-finish` when you want to pair HARINA with an existing logged-in Chrome session instead of opening a fresh browser
- The [logged-in-google-chrome-skill](https://github.com/Sunwood-ai-labs/logged-in-google-chrome-skill) helper is a good fit for that recovery flow in Codex
- After rotating `GOOGLE_OAUTH_REFRESH_TOKEN` in `.env`, recreate Docker Compose services so the new token reaches the running containers

## Dataset commands

Download Discord images into a dataset:

```bash
uv run harina-v4 dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 50
```

Run a Gemini smoke test on local dataset images:

```bash
uv run harina-v4 dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

Notes:

- `dataset smoke-test` resolves `GEMINI_TEST_MODEL`
- `test docs-public --mode both` uses the same verification lane for both the CLI replay path and the Discord upload-test path

## Recommended operator flow

1. Use `harina-v4 google oauth-login` if you are on personal Gmail.
2. Use `harina-v4 google init-resources` to create or confirm Drive and Sheets targets.
3. Use `harina-v4 google init-drive-watch` to provision the Drive watcher folders.
4. Put the receipt images you want to verify under `docs/public/test`.
5. Use `harina-v4 test docs-public` to exercise both the CLI path and the Discord path.
6. Use `harina-v4 drive watch --once` to confirm one-shot Drive watcher behavior.
7. Use `harina-v4 bot run` and `harina-v4 drive watch` for the continuous production path.

## Category behavior

- HARINA reads the `Categories` sheet on every write-enabled run
- Gemini assigns one category per line item, not one category per receipt
- New categories can be proposed when no approved option fits closely
- Newly accepted categories are appended back into `Categories` for future runs
