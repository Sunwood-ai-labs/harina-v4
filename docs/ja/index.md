---
layout: home

hero:
  name: Harina Receipt Bot
  text: 1つのコードベースで常時レシート処理と過去 Discord データの再取得を両立
  tagline: Gemini の 2 段階処理でレシートを抽出し、Google Sheets のカテゴリ一覧から商品ごとに分類し、Google Drive 保存や V1、V2、V3 からの移行用データセット再構築まで担える Python 製 Discord bot です。
  image:
    src: /brand/harina-hero.webp
    alt: Harina Receipt Bot hero image
  actions:
    - theme: brand
      text: 概要
      link: /ja/guide/overview
    - theme: alt
      text: リリースノート
      link: /ja/guide/release-notes-v4.2.0
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
  - title: 2 段階 Gemini パイプライン
    details: まずレシート情報を抽出し、その後に Sheets のカテゴリ一覧を使って商品ごとに分類します。
  - title: Google Workspace 連携
    details: 元画像を Drive に保存し、`Receipts` に商品行を追記しながら `Categories` も管理します。
  - title: 移行と再スキャンに対応
    details: V1、V2、V3 の履歴取得、回帰検証用データセット作成、モデルやプロンプト更新後の再評価に使えます。
  - title: Discord でカテゴリが見える
    details: 返信スレッドにカテゴリ要約、商品ごとのカテゴリ、金額つき明細をそのまま表示できます。
---
