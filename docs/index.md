---
layout: home

hero:
  name: Harina Receipt Bot
  text: Run real-time receipt intake and historical Discord backfills from one codebase
  tagline: A Python self-hosted Discord bot that extracts receipts in two Gemini stages, categorizes each line item from a Sheets-backed catalog, archives originals to Google Drive, writes structured rows to Google Sheets, and can also rebuild datasets for V1, V2, V3 migrations or model re-scan workflows.
  image:
    src: /brand/harina-hero.webp
    alt: Harina Receipt Bot hero image
  actions:
    - theme: brand
      text: Overview
      link: /guide/overview
    - theme: alt
      text: Release Notes
      link: /guide/release-notes-v4.2.0
    - theme: alt
      text: CLI
      link: /guide/cli
    - theme: alt
      text: Dataset Downloader
      link: /guide/dataset-downloader
    - theme: alt
      text: Upload Test
      link: /guide/cli#discord-upload-test

features:
  - title: Discord-native intake
    details: Watch one or more Discord channels and process uploaded receipt images without forcing users into a separate UI.
  - title: Two-stage Gemini pipeline
    details: Extract receipt structure first, then assign one category per line item against the live Sheets catalog.
  - title: Google Workspace handoff
    details: Upload the source image to Drive, write one row per line item to `Receipts`, and maintain a reusable `Categories` sheet.
  - title: Migration and replay ready
    details: Download historical Discord images for V1, V2, V3 migrations, regression datasets, and re-scans after model or prompt changes.
  - title: Category-aware Discord replies
    details: Show category totals, per-item categories, and priced line items in the Discord response thread.
---
