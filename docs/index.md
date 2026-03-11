---
layout: home

hero:
  name: Harina Receipt Bot
  text: Run real-time receipt intake and historical Discord backfills from one codebase
  tagline: A Python self-hosted Discord bot that processes live receipt uploads with Gemini, archives originals to Google Drive, writes structured rows to Google Sheets, and can also rebuild datasets for V1, V2, V3 migrations or model re-scan workflows.
  image:
    src: /brand/harina-mark.svg
    alt: Harina Receipt Bot logo
  actions:
    - theme: brand
      text: Overview
      link: /guide/overview
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
  - title: Structured Gemini extraction
    details: Extract merchant, date, totals, tax, payment method, OCR-like text, and line items into normalized JSON.
  - title: Google Workspace handoff
    details: Upload the source image to Drive and append a ledger-friendly row to Sheets in the same processing flow.
  - title: Migration and replay ready
    details: Download historical Discord images for V1, V2, V3 migrations, regression datasets, and re-scans after model or prompt changes.
---
