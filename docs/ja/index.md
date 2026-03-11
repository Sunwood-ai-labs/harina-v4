---
layout: home

hero:
  name: Harina Receipt Bot
  text: 1つのコードベースで常時レシート処理と過去 Discord データの再取得を両立
  tagline: Gemini によるレシート抽出、Google Drive 保存、Google Sheets 連携を行う Python 製 Discord bot であり、同時に V1、V2、V3 からの移行やモデル更新後の再スキャン用データセット作成にも使えます。
  image:
    src: /brand/harina-hero.webp
    alt: Harina Receipt Bot hero image
  actions:
    - theme: brand
      text: 概要
      link: /ja/guide/overview
    - theme: alt
      text: CLI
      link: /ja/guide/cli
    - theme: alt
      text: データセットダウンローダー
      link: /ja/guide/dataset-downloader
    - theme: alt
      text: Upload Test
      link: /ja/guide/cli#discord-upload-test

features:
  - title: Discord ネイティブ運用
    details: 既存の Discord チャンネルをそのまま入力面として使い、別 UI を増やさずにレシート処理を進められます。
  - title: Gemini による構造化抽出
    details: 店舗名、日付、合計、税額、支払方法、OCR 風テキスト、明細行を JSON として整形します。
  - title: Google Workspace 連携
    details: 元画像を Drive に保存し、会計向けの行データを Sheets に追記します。
  - title: 移行と再スキャンに対応
    details: V1、V2、V3 の履歴取得、回帰検証用データセット作成、モデルやプロンプト更新後の再評価に使えます。
---
