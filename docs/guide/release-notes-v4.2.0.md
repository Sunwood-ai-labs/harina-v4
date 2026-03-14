# Release Notes: v4.2.0

[![GitHub Release](https://img.shields.io/badge/GitHub-v4.2.0-1E3A34?style=for-the-badge&logo=github)](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.2.0)
[![Japanese Notes](https://img.shields.io/badge/%E6%97%A5%E6%9C%AC%E8%AA%9E-v4.2.0-E68B2C?style=for-the-badge)](/ja/guide/release-notes-v4.2.0)

Published on March 15, 2026 (JST). This release covers the shipped changes between `v4.1.0` and `v4.2.0`.

## At a glance

- Added team-based Google Drive intake routing with one-shot Discord and Drive provisioning
- Split Gemini receipt extraction from line-item categorization and synchronized categories through Google Sheets
- Improved Discord result embeds with category previews, line-item categories, and direct Drive and Sheets links
- Added better Discord debugging and Gemini retry behavior for live operations
- Introduced `docs/public/test` verification flows plus updated English and Japanese documentation

## Highlights

### Team-based intake routing

`setup team-intake` can now create a HARINA Discord category, one channel per member, and matching Drive inbox and processed folders in one run. The Drive watcher also supports `DRIVE_WATCH_ROUTES_JSON`, so each Drive intake route can land in its matching Discord channel instead of one shared destination.

### Staged categorization with Sheets sync

Gemini processing is now split into two prompts: receipt extraction first, then category assignment for each line item. HARINA keeps a live `Categories` sheet, normalizes category names, seeds defaults, and appends newly proposed categories back into Sheets for future runs.

### Better Discord operator feedback

Receipt replies now surface category totals, per-item categories, and line-item previews in the embed. When Drive and Sheets URLs are available, HARINA also attaches link buttons so operators can jump straight to the archived image or spreadsheet rows.

### Stronger debugging and resilience

`bot collect-logs` saves Discord channel history, thread messages, embed payloads, attachments, and component metadata into `logs/discord` for post-incident analysis. Gemini calls now retry transient failures and can rotate across `GEMINI_API_KEY_ROTATION_LIST` entries when quota or service issues occur.

### Verification and docs refresh

`test docs-public` exercises sample receipt assets from `docs/public/test` through the CLI path, the Discord path, or both. The docs, overview pages, and architecture diagrams were updated in both English and Japanese so the Drive watcher and staged categorization flow are documented alongside the code.

## Included in v4.2.0

### New and expanded commands

- `uv run harina-v4 setup team-intake --guild-id ... --member ...`
- `uv run harina-v4 google init-drive-watch --env-file .env`
- `uv run harina-v4 google oauth-start`
- `uv run harina-v4 google oauth-finish`
- `uv run harina-v4 bot collect-logs <discord-url>`
- `uv run harina-v4 test docs-public`

### User-facing behavior changes

- The bot writes one row per line item into `Receipts`
- `itemCategory` is now part of the exported Sheets data
- Drive watcher notifications create an intake post and then reply with the processed result in a thread when possible
- Successful Discord replies can include direct links to Google Drive and Google Sheets
- Category labels are normalized to short family-friendly names such as `野菜`, `惣菜`, and `飲料`

## Validation

- `uv run pytest` (`67 passed`)
- `npm --prefix docs run docs:build`

## See also

- [Overview](/guide/overview)
- [CLI](/guide/cli)
- [Google Setup](/guide/google-setup)
- [Japanese release notes](/ja/guide/release-notes-v4.2.0)
