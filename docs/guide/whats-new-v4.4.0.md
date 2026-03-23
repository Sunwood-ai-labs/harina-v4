# What's New In Harina v4.4.0

[![GitHub Release](https://img.shields.io/badge/GitHub-v4.4.0-1E3A34?style=for-the-badge&logo=github)](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.4.0)
[![Release Notes](https://img.shields.io/badge/Release%20Notes-v4.4.0-E68B2C?style=for-the-badge)](/guide/release-notes-v4.4.0)
[![Japanese Article](https://img.shields.io/badge/Japanese-Article-D8E7E0?style=for-the-badge&logoColor=1E3A34)](/ja/guide/whats-new-v4.4.0)

![Harina Receipt Bot v4.4.0 hero](/brand/harina-hero-v4.4.0.svg)

`v4.4.0` turns Google Sheets into a real operations dashboard for HARINA. Instead of only appending bookkeeping rows, the release gives operators live analysis tabs, duplicate-review controls, payer breakdowns, and a watcher resume command for the moments when the long-running system is waiting and you need it to move now.

## Why this release matters

- Spreadsheet operators can review trends, payer breakdowns, and category movement without touching the raw year tabs.
- Duplicate candidates can be reviewed from Sheets with a persistent checkbox flow instead of relying only on filename-level intake protection.
- The watcher can be resumed from Discord when it is sitting in a long retry or poll wait.
- Dashboard rebuilds now have a dedicated CLI command, so recovery and maintenance are easier when spreadsheet structure changes.

## 1. Live analysis dashboards instead of manual spreadsheet summaries

HARINA now rebuilds `Analysis YYYY` and `Analysis All Years` sheets as dashboard surfaces. These tabs are created from formulas and charts rather than from hand-maintained summary cells, which means existing year tabs can keep acting as the source of truth while the analysis layer stays disposable and reproducible.

The dashboards cover category totals, monthly category timelines, merchant trends, payer summaries, and stacked charts. They also recreate cleanly, so stale layout leftovers do not survive a refresh.

## 2. `google sync-analysis` for rebuilds and targeted refreshes

This release introduces a dedicated command:

```bash
uv run harina-v4 google sync-analysis
```

You can narrow the rebuild to one or more years with `--year` and omit the all-years sheet with `--skip-all-years`. That makes it much easier to repair a single dashboard after a spreadsheet-side change without rebuilding everything by hand.

## 3. Payer analytics and duplicate review in Sheets

The dashboard now tracks `authorTag`-based payer totals and payer-by-category breakdowns. That gives teams a better view of who is paying for what across a shared receipt archive.

On top of that, HARINA now creates `重複確認`, a persistent control sheet for duplicate candidates. Operators can leave the baseline receipt alone, check a duplicate for automatic dashboard exclusion, or uncheck it later if they want to keep that receipt in the analysis.

## 4. Resume the watcher without restarting containers

When the watcher is waiting for its next poll or sitting in the delayed Gemini retry window, `/resume_polling` lets an operator resume it from Discord immediately. That is faster than redeploying or waiting out the remaining delay and gives teams a cleaner operational recovery path.

The command is permission-gated and intended for the system-log channel workflow, so it stays operator-focused rather than becoming a noisy general-user control.

## What changes for operators

- Expect new `Analysis ...` tabs and a persistent `重複確認` sheet in the spreadsheet.
- Expect yearly dashboards to update automatically as HARINA appends new rows into existing year tabs.
- Expect to use `google sync-analysis` when a new year tab is introduced outside the normal HARINA append path or when you want to rebuild dashboards manually.
- Expect `/resume_polling` to be the quickest way to clear watcher waits from Discord.

## Validation

- `uv run pytest`
- `npm --prefix docs run docs:build`

## Links

- [Release Notes v4.4.0](/guide/release-notes-v4.4.0)
- [GitHub Release](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.4.0)
- [CLI Guide](/guide/cli)
