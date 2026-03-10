---
layout: home

hero:
  name: Harina Receipt Bot
  text: Turn Discord receipt images into Drive files and spreadsheet rows
  tagline: A Python self-hosted Discord bot that reads receipts with Gemini, archives the original image to Google Drive, and writes structured bookkeeping data to Google Sheets.
  image:
    src: /brand/harina-mark.svg
    alt: Harina Receipt Bot logo
  actions:
    - theme: brand
      text: Quick Start
      link: /guide/overview
    - theme: alt
      text: Deployment Guide
      link: /guide/deployment
    - theme: alt
      text: GitHub
      link: https://github.com/Sunwood-ai-labs/harina-v4

features:
  - title: Discord-native intake
    details: Watch one or more Discord channels and process uploaded receipt images without forcing users into a separate UI.
  - title: Structured Gemini extraction
    details: Extract merchant, date, totals, tax, payment method, OCR-like text, and line items into normalized JSON.
  - title: Google Workspace handoff
    details: Upload the source image to Drive and append a ledger-friendly row to Sheets in the same processing flow.
  - title: Home-server friendly
    details: Ship the bot with Python, uv, Docker Compose, and environment-based secrets so it is easy to self-host.
---
