<div align="center">
  <img src="./docs/public/brand/harina-hero.svg" alt="Harina Receipt Bot hero" width="100%" />
  <h1>Harina Receipt Bot</h1>
  <p>Discord に投稿されたレシート画像を、Gemini・Google Drive・Google Sheets へつなぐ自動化 bot。</p>
</div>

[English](./README.md)

![Python](https://img.shields.io/badge/Python-3.12-1E3A34?style=for-the-badge&logo=python&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-Receipt%20Extraction-E68B2C?style=for-the-badge)
![Docker Compose](https://img.shields.io/badge/Docker%20Compose-Self--Hosted-36544C?style=for-the-badge&logo=docker&logoColor=white)
![CI](https://img.shields.io/github/actions/workflow/status/Sunwood-ai-labs/harina-v4/ci.yml?branch=main&style=for-the-badge&label=CI)
![License](https://img.shields.io/github/license/Sunwood-ai-labs/harina-v4?style=for-the-badge)

## ✨ 概要

Harina Receipt Bot は、Discord を入口にしてレシート画像を自動処理する Python bot です。Discord に投稿された画像を Gemini で構造化抽出し、元画像は Google Drive へ、整形済みデータは Google スプレッドシートへ保存します。

## 🚀 特長

- Discord チャンネルに投稿されたレシート画像を監視
- Gemini で店舗名、日付、合計、税額、支払方法、OCR風テキスト、明細を抽出
- 元画像を Google Drive の指定フォルダへ保存
- 1 レシートごとに Google スプレッドシートへ追記
- `uv` と Docker Compose 前提で自宅サーバーに載せやすい

## 🧭 処理の流れ

1. ユーザーが Discord にレシート画像を投稿します。
2. bot が画像をダウンロードして Gemini に送ります。
3. Gemini が正規化済み JSON を返します。
4. 元画像を Google Drive に保存します。
5. 対応するデータ行を Google スプレッドシートへ追加します。
6. Discord に処理結果のサマリを返信します。

## ⚡ クイックスタート

```bash
cp .env.example .env
uv sync
uv run pytest
uv run python -m app.main
```

必須の環境変数:

- `DISCORD_TOKEN`
- `GEMINI_API_KEY`
- `GOOGLE_DRIVE_FOLDER_ID`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON` または `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`

## 🐳 Docker Compose

```bash
docker compose up -d --build
docker compose logs -f
```

Google サービスアカウントの JSON ファイルを使う場合は、`./secrets` に置いて `GOOGLE_SERVICE_ACCOUNT_KEY_FILE=/app/secrets/your-key.json` を指定してください。

## 📚 ドキュメント

- [Docs site](https://sunwood-ai-labs.github.io/harina-v4/)
- [概要](./docs/ja/guide/overview.md)
- [Google 設定](./docs/ja/guide/google-setup.md)
- [デプロイ](./docs/ja/guide/deployment.md)

## 🧱 リポジトリ構成

```text
app/                  Python bot 本体
docs/                 VitePress ドキュメント
.github/workflows/    CI と GitHub Pages 配備
Dockerfile            コンテナイメージ定義
docker-compose.yml    常駐運用設定
```

## 🔐 運用メモ

- `DISCORD_CHANNEL_IDS` を空にすると、bot が読める全チャンネルを対象にします
- `DISCORD_CHANNEL_IDS` にカンマ区切りで ID を入れると対象を限定できます
- 起動時に対象シートのヘッダー行を自動作成します
- 必須の Google 設定が不足している場合は起動直後に失敗します

## 🛠 開発

```bash
uv sync
uv run pytest
npm --prefix docs install
npm --prefix docs run docs:build
```

## 📄 ライセンス

[MIT](./LICENSE)
