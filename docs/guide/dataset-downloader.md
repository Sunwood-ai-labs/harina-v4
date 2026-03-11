# Dataset Downloader

Use `app.dataset_downloader` when you need a local copy of historical Discord receipt images.

## Best fit scenarios

- Migrate data from V1, V2, or V3 channels into a stable local dataset
- Re-scan older receipts after changing Gemini models
- Re-run extraction after prompt or schema updates
- Build a regression dataset for tests and evaluation

## Basic command

```bash
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>"
```

## Common examples

Download only the most recent 5 messages:

```bash
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 5
```

Write into a versioned migration folder:

```bash
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --output-dir ./dataset/v3-backfill
```

Refresh files that already exist:

```bash
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --overwrite
```

## Output structure

Each attachment is stored with the original uploaded filename preserved:

```text
dataset/
  discord-images/
    guild-<name-or-id>/
      channel-<name-or-id>/
        message-<id>/
          attachment-<id>/
            original-file-name.jpg
    metadata.jsonl
```

Notes:

- If a server or channel name contains Japanese characters, the folder falls back to the numeric ID
- `metadata.jsonl` includes message, author, attachment, and source URL fields for replay pipelines
- `DISCORD_DATASET_OUTPUT_DIR` changes the default output root

## Required permissions

- The bot must be a member of the target server
- The bot must be able to view the target channel
- The bot must be able to read message history
- `MESSAGE CONTENT INTENT` should be enabled in the Discord Developer Portal

## Recommended migration flow

1. Download a bounded sample with `--limit 5` or `--limit 50`.
2. Validate folder layout and metadata output.
3. Run [Gemini Smoke Test](./gemini-smoke-test.md) on about 2 representative images.
4. Run the full channel export into a versioned folder such as `dataset/v3-backfill`.
5. Feed the dataset into your new extraction or normalization pipeline.
6. Compare the new results against prior V1, V2, or V3 outputs before cutover.
