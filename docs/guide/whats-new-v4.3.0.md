# What's New In Harina v4.3.0

[![GitHub Release](https://img.shields.io/badge/GitHub-v4.3.0-1E3A34?style=for-the-badge&logo=github)](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.3.0)
[![Release Notes](https://img.shields.io/badge/Release%20Notes-v4.3.0-E68B2C?style=for-the-badge)](/guide/release-notes-v4.3.0)
[![Japanese Article](https://img.shields.io/badge/Japanese-Article-D8E7E0?style=for-the-badge&logoColor=1E3A34)](/ja/guide/whats-new-v4.3.0)

![Harina Receipt Bot v4.3.0 hero](/brand/harina-hero-v4.3.0.svg)

`v4.3.0` is a workflow-hardening release. Instead of introducing a brand-new surface area, it makes day-to-day receipt operations safer, quieter, and easier to audit across Discord, Google Drive, and Google Sheets.

## Why this release matters

- Duplicate receipts are now much less likely to create accidental double writes.
- Time-based folder and sheet routing makes historical bookkeeping easier to browse.
- Production receipt intake is separated from smoke and test model selection, so operators can validate without disturbing the live path.
- Long-running Drive watcher deployments get less idle noise while preserving actionable status updates.

## 1. Duplicate-safe intake with explicit rescans

HARINA now treats `attachmentName` as the duplicate key across receipt flows. In practice, that means the Discord bot can stop early with `Receipt Skipped`, while the Drive watcher can avoid duplicate Discord notifications and duplicate row writes before moving the file into the processed location.

When you do want to replay a receipt on purpose, `--rescan` remains the opt-in override. This makes the default path safer without removing deliberate backfill and retry workflows.

## 2. Year-based sheet routing and cleaner archives

This release pushes date-oriented organization further in two places:

- receipt rows can route into year-based sheet tabs
- archived images and processed Drive watcher files land in `YYYY/MM`

That combination makes month-by-month audits and year-based bookkeeping much easier to scan, especially once teams start accumulating a larger receipt history.

## 3. Safer Gemini operations

`v4.3.0` separates production and test Gemini model selection. The bot and watcher stay on the production path, while smoke-style flows can use a separate test model configuration.

The release also improves resiliency around Gemini key rotation and surfaces more operator-facing telemetry. Drive Receipt embeds now show the model used for the run plus estimated API cost metadata, so output quality and cost can be reviewed together instead of by guesswork.

## 4. Quieter watcher loops for long-running deployments

The Drive watcher no longer repeats `HARINA Scan Summary` messages for unchanged idle cycles. Operators still see updates when files are processed, skipped, failed, or when the backlog changes, but long idle periods stay much quieter.

This is a small change on paper, but it has a big effect on operational signal quality when the watcher runs continuously.

## What changes for operators

- Expect duplicate receipts to skip earlier unless you explicitly use `--rescan`.
- Expect Drive watcher processed folders and archived uploads to look more chronological.
- Expect test and smoke flows to be easier to isolate from production Gemini settings.
- Expect Discord embeds and watcher logs to be more useful for debugging and cost review.

## Validation

- `uv run pytest` (`100 passed`)
- `npm --prefix docs run docs:build`

## Links

- [Release Notes v4.3.0](/guide/release-notes-v4.3.0)
- [GitHub Release](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.3.0)
- [CLI Guide](/guide/cli)
