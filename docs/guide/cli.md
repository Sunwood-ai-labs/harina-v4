# CLI

HARINA V4 is packaged around a Python CLI called `harina`.

## Why use the CLI surface

- Keep bot operations, migrations, replays, and verification under one command namespace
- Reuse the same package logic for the always-on bot and operator workflows
- Make local runs, CI checks, and future automation easier to standardize

## Basic help

```bash
uv run harina --help
```

## Bot commands

Run the always-on Discord bot:

```bash
uv run harina bot run
```

## Dataset commands

Download Discord images into a dataset:

```bash
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 50
```

Run a Gemini smoke test on local dataset images:

```bash
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

## Discord upload test

Upload a real image into Discord and wait for the bot reply:

```bash
uv run harina bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

Notes:

- The command posts a real message into the specified Discord channel
- The bot processes that message using the same package logic as `harina bot run`
- Test messages are marked with `DISCORD_TEST_MESSAGE_PREFIX`, which defaults to `[HARINA-TEST]`
- `DISCORD_TEST_CHANNEL_ID` lets you keep a fixed test channel and omit `--channel-id`
- Use a safe test channel because this command touches live Discord, Gemini, Drive, and Sheets

## Recommended operator flow

1. Use `harina dataset download` to export a small sample.
2. Use `harina dataset smoke-test` to validate Gemini on about 2 images.
3. Use `harina bot upload-test` to confirm live Discord behavior.
4. Use `harina bot run` for the continuous production path.
