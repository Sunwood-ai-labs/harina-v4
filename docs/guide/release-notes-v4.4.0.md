# Release Notes: v4.4.0

[![GitHub Release](https://img.shields.io/badge/GitHub-v4.4.0-1E3A34?style=for-the-badge&logo=github)](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.4.0)
[![Japanese Notes](https://img.shields.io/badge/Japanese-v4.4.0-E68B2C?style=for-the-badge)](/ja/guide/release-notes-v4.4.0)

![Harina Receipt Bot v4.4.0 hero](/brand/harina-hero-v4.4.0.svg)

This release covers the shipped changes between `v4.3.0` and `v4.4.0`.

## At a glance

- Added formula-driven yearly and all-years Google Sheets dashboards that rebuild cleanly and refresh automatically as receipt rows are appended
- Added monthly category timelines, payer analytics, payer-by-category breakdowns, and charted dashboard sections for faster bookkeeping review
- Added spreadsheet-side duplicate candidate review plus a persistent `重複確認` control sheet with checkbox-driven analysis exclusion
- Added `/resume_polling` so operators can clear watcher poll waits or Gemini delayed-retry waits without restarting the service
- Reduced Sheets API readback pressure during analysis sync and refreshed the docs surface around dashboards, duplicate handling, and deployment operations

## Highlights

### Formula-driven analysis dashboards in Google Sheets

HARINA now creates `Analysis YYYY` tabs together with `Analysis All Years`, then rebuilds those analysis tabs as dashboard-style sheets instead of writing static summaries into the receipt tabs themselves. The dashboard cells are driven by Google Sheets formulas, so new rows appended into existing year tabs recalculate automatically without manual copy-paste.

The dashboard layout now includes KPI cards, category tables, merchant tables, monthly timelines, stacked monthly category charts, and a Japanese-first visual treatment for the live Sheets surface.

### Analysis sync as an explicit operator command

The new `google sync-analysis` command lets operators rebuild dashboard tabs on demand, target specific years with repeated `--year`, and skip the all-years tab when they only want to refresh one yearly dashboard.

This keeps the normal append path automatic while still giving you a safe recovery command when you need to rebuild analysis tabs after manual spreadsheet changes or after introducing a new year tab.

### Payer analysis and duplicate controls

The dashboard now includes `authorTag`-based payer summaries, payer-by-category tables, and companion charts so teams can inspect who paid how much and in which categories. On top of that, HARINA now creates a persistent `重複確認` sheet for spreadsheet-side duplicate review.

Duplicate candidates are grouped from receipt evidence and surfaced into the dashboard as a preview. The `重複確認` sheet adds a checkbox-based `自動除外` control so operators can keep the baseline receipt, exclude a duplicate from dashboard analysis, or manually opt back in without editing the raw yearly tabs.

### Drive watcher resume from Discord

The Drive watcher now registers a `/resume_polling` slash command. Operators with `Manage Server` permission can interrupt the current poll interval wait or a long Gemini retry wait, forcing the watcher to resume immediately instead of waiting out the remaining delay.

This is especially useful when the watcher is sitting in its delayed retry window after quota exhaustion or is between normal poll cycles and you want to trigger the next scan right away.

## Tooling and automation

- Added `google sync-analysis` to the CLI surface for dashboard rebuilds
- Added persistent duplicate-control state handling in Sheets so checkbox changes survive analysis sheet recreation
- Added test coverage for dashboard formulas, chart sources, duplicate-control behavior, and the new watcher resume command

## Docs and assets

- Added a new `v4.4.0` release hero asset derived from the existing release branding
- Added docs-backed release notes and walkthrough pages for `v4.4.0` in both English and Japanese
- Updated docs navigation, docs home links, and top-level README links to point at the new release collateral
- Synced steady-state docs for CLI, overview, Google setup, and deployment to cover dashboard rebuilds, duplicate-control sheets, and `/resume_polling`

## Validation

- `uv run pytest`
- `npm --prefix docs run docs:build`

## Upgrade notes

- `重複確認` is a new persistent spreadsheet tab. Its checkbox state affects dashboard analysis only; the original yearly receipt rows remain unchanged.
- HARINA still keeps the filename-based ingest duplicate guard around `attachmentName`. The new spreadsheet-side duplicate controls do not replace the ingestion-time duplicate skip.
- Existing year tabs recalculate automatically when new rows are appended. If you add a brand-new year tab outside the normal HARINA append flow, run `uv run harina-v4 google sync-analysis` to rebuild the all-years dashboard target list.

## See also

- [What's New In Harina v4.4.0](/guide/whats-new-v4.4.0)
- [Overview](/guide/overview)
- [CLI](/guide/cli)
- [Google Setup](/guide/google-setup)
- [Japanese release notes](/ja/guide/release-notes-v4.4.0)
