# Release Notes: v4.3.0

[![GitHub Release](https://img.shields.io/badge/GitHub-v4.3.0-1E3A34?style=for-the-badge&logo=github)](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.3.0)
[![Japanese Notes](https://img.shields.io/badge/Japanese-v4.3.0-E68B2C?style=for-the-badge)](/ja/guide/release-notes-v4.3.0)

![Harina Receipt Bot v4.3.0 hero](/brand/harina-hero-v4.3.0.svg)

Published on March 19, 2026 (JST). This release covers the shipped changes between `v4.2.0` and `v4.3.0`.

## At a glance

- Added explicit receipt dedup + year-based sheet tab routing to protect replay safety for both Discord and Drive paths
- Moved archived receipt images and processed Drive files into year/month-style folders
- Split Gemini model selection between production and test flows to reduce operational coupling between live intake and smoke/test paths
- Added a delayed retry flow for Gemini key rotation exhaustion, plus safer backoff behavior in the bot path
- Improved Drive watcher status reporting by suppressing unchanged idle summaries and keeping only actionable scan updates
- Added richer Drive Receipt embed metadata, including model and estimated cost details
- Updated operational docs for Drive routing, OAuth recovery, and deployment lifecycle guidance

## Highlights

### Safer intake replay behavior

HARINA now uses `attachmentName` as the authoritative duplicate key and writes Drive/Discord results with clearer duplicate handling: replays are skipped by default and explicit `--rescan`/re-run behavior is preserved for intentional reprocessing. Receipt rows continue to route by purchase year where relevant so historical data remains easier to review.

### Archive structure with year/month routing

Receipt image archives and processed Drive files now land in `YYYY/MM`-style folders. This keeps main folders cleaner and aligns with date-oriented operations for both direct uploads and watched Drive handoff paths.

### Model split and resiliency

Production receipt intake and lightweight test paths now resolve different Gemini model settings, so routine dry-runs and smoke scenarios can use dedicated test model flow without changing operators' core production settings. The bot retry flow now also includes a delayed retry pass for key rotation exhaustion and improved fallback behavior when Gemini transient failures appear.

### Less-noisy scan summaries

Drive watcher summaries now suppress idle cycles that report no meaningful progress changes. Operators still get messages for active processing, changed backlog state, and failed/processed cycles, so status noise is reduced without losing visibility where it matters.

### Better processing transparency

Drive path embeds now surface model identifiers and estimated cost metadata in the same run where receipt rows are produced, helping teams correlate output behavior with API usage cost and model choice.

## Included in v4.3.0

### User-facing behavior changes

- Duplicate safety now uses the `attachmentName` key path more consistently across Discord intake and Drive watch intake.
- Direct intake, watched Drive intake, and duplicate paths consistently route processed content into year/month archive structure.
- Changed scan summaries: idle/unchanged Drive watcher summaries are now quiet by default.
- Drive intake embeds include model/cost context for easier audit and debugging.

### Commands and operations notes

- Existing CLI/Discord flows now benefit from dedup, year/month routing, and quieter summary behavior without adding new top-level commands.
- Operational docs now describe:
  - Drive watcher route planning and folder routing
  - OAuth token recovery and production OAuth file wiring
  - Docker Compose lifecycle expectations after token/env rotation

## Validation

- `uv run pytest` (`100 passed`)
- `npm --prefix docs run docs:build`

## See also

- [What's New In Harina v4.3.0](/guide/whats-new-v4.3.0)
- [Overview](/guide/overview)
- [CLI](/guide/cli)
- [Google Setup](/guide/google-setup)
- [Japanese release notes](/ja/guide/release-notes-v4.3.0)
