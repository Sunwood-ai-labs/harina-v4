---
layout: home

hero:
  name: Harina Receipt Bot
  text: Discord のレシート画像を Drive と Sheets に自動連携
  tagline: Python 製のセルフホスト Discord bot で、Gemini によるレシート抽出、Google Drive への元画像保存、Google Sheets への構造化データ追記をまとめて行います。
  image:
    src: /brand/harina-mark.svg
    alt: Harina Receipt Bot logo
  actions:
    - theme: brand
      text: 使い方
      link: /ja/guide/overview
    - theme: alt
      text: デプロイ
      link: /ja/guide/deployment
    - theme: alt
      text: GitHub
      link: https://github.com/Sunwood-ai-labs/harina-v4

features:
  - title: Discord そのまま運用
    details: 既存の Discord チャンネルを受付面にして、別アプリなしでレシート画像を投入できます。
  - title: Gemini で構造化抽出
    details: 店舗名、日付、合計、税額、支払方法、OCR風テキスト、明細を JSON として取り出します。
  - title: Google Workspace 連携
    details: 元画像は Drive、会計向けデータは Sheets に保存して、後工程へつなぎやすくします。
  - title: 自宅サーバー向け
    details: Python、uv、Docker Compose を前提にしているので、小さな常駐サーバーでも動かしやすい構成です。
---
