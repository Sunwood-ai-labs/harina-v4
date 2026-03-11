<div align="center">
  <img src="./docs/public/brand/harina-hero.svg" alt="Harina Receipt Bot hero" width="100%" />
  <h1>Harina Receipt Bot</h1>
  <p>Discord のレシート運用を Gemini、Google Drive、Google Sheets、そして移行用データセット作成までつなぐ Python ツールです。</p>
</div>

[English](./README.md)

![Python](https://img.shields.io/badge/Python-3.12-1E3A34?style=for-the-badge&logo=python&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-Receipt%20Extraction-E68B2C?style=for-the-badge)
![Docker Compose](https://img.shields.io/badge/Docker%20Compose-Self--Hosted-36544C?style=for-the-badge&logo=docker&logoColor=white)
![CI](https://img.shields.io/github/actions/workflow/status/Sunwood-ai-labs/harina-v4/ci.yml?branch=main&style=for-the-badge&label=CI)
![License](https://img.shields.io/github/license/Sunwood-ai-labs/harina-v4?style=for-the-badge)

## ✨ 概要

Harina Receipt Bot は、レシート運用向けのセルフホスト型 Python Discord bot です。役割は大きく 2 つあります。

- Discord に投稿されたレシート画像を常時処理し、Gemini、Google Drive、Google Sheets へ連携する
- V1、V2、V3 からの移行や、モデル更新後の再スキャン用に過去画像をデータセットとして取得する

## 🚀 特長

- Discord チャンネルに投稿されたレシート画像を監視
- Gemini で店舗名、日付、金額、税額、支払方法、OCR 風テキスト、明細行を構造化
- 元画像を Google Drive に保存
- 1 レシートごとに Google Sheets へ 1 行追加
- 過去の Discord 画像をローカルデータセットとして取得できる
- `uv` と Docker Compose でローカル運用しやすい

## 🔄 想定ワークフロー

1. 日常運用: ユーザーが Discord にレシート画像を投稿し、bot が自動処理する
2. データ移行: V1、V2、V3 のチャンネルから過去画像をまとめて取得する
3. 再スキャン: プロンプト、モデル、スキーマ、抽出ロジックの変更後に旧データを再評価する

## ⚡ クイックスタート

```bash
cp .env.example .env
uv sync
uv run pytest
uv run harina bot run
```

必須の環境変数:

- `DISCORD_TOKEN`
- `GEMINI_API_KEY`
- `GOOGLE_DRIVE_FOLDER_ID`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON` または `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`

## 🧰 HARINA CLI

このリポジトリは Python パッケージ CLI として `harina` コマンドを公開します。

```bash
uv run harina --help
```

主なコマンド:

```bash
uv run harina bot run
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 50
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
uv run harina bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

この形にする利点:

- V4 の運用コマンド面を CLI に集約できる
- Discord bot も同じ Python パッケージのロジックを再利用できる
- 移行、再スキャン、Discord 上の実機確認まで同じツールから実行できる

## 📦 データセットダウンローダー

移行や再スキャン用に、Discord の画像を一括取得するワンショット CLI としても使えます。

```bash
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>"
```

よく使う例:

```bash
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 5
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --output-dir ./dataset/v3-backfill
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --overwrite
```

主なオプション:

- `--output-dir ./dataset/discord-images`
- `--limit 500`
- `--include-bots`
- `--overwrite`

アップロードされていたファイル名はそのまま保持されます。保存先は `guild-<name-or-id>/channel-<name-or-id>/message-<id>/attachment-<id>/` で整理され、ルートには `metadata.jsonl` を出力します。サーバー名またはチャンネル名に日本語が含まれる場合は、その名前部分をスキップして数値 ID のみを使います。

主な用途:

- V1、V2、V3 からの過去データ移行
- 回帰検証や評価用の固定データセット作成
- Gemini モデルやプロンプト更新後の再スキャン

## 🧪 Gemini スモークテスト

データセットを取得したあと、2 枚程度の画像でレシート認識の動作確認をすぐ回せます。

```bash
uv run harina dataset smoke-test --limit 2
```

よく使う例:

```bash
uv run harina dataset smoke-test --limit 2
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2 --output ./artifacts/gemini-smoke-test.json
```

補足:

- `GEMINI_API_KEY` と `GEMINI_MODEL` を使って実行します
- このリポジトリの既定モデルは `gemini-3-flash-preview` です
- 同一画像は、`--allow-duplicates` を付けない限りハッシュで自動除外します
- 結果は JSON で標準出力され、必要ならファイルにも保存できます

## 🤖 Discord アップロードテスト

CLI から実際にレシート画像を Discord チャンネルへアップロードし、bot の返信まで待つ確認もできます。

```bash
uv run harina bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

補足:

- 対象チャンネルに実際のメッセージを投稿します
- 常時稼働の bot と同じパッケージロジックで処理します
- テストメッセージには `DISCORD_TEST_MESSAGE_PREFIX` が付き、既定値は `[HARINA-TEST]` です
- `DISCORD_TEST_CHANNEL_ID` を入れておくと `--channel-id` を省略できます
- 実運用確認向けなので、安全なテスト用チャンネルで使うのがおすすめです

bot 側の前提条件:

- 対象サーバーに bot が参加していること
- 対象チャンネルの閲覧権限と履歴参照権限があること
- Discord Developer Portal で `MESSAGE CONTENT INTENT` を有効化していること

## 🐳 Docker Compose

```bash
docker compose up -d --build
docker compose logs -f
```

Google サービスアカウント JSON ファイルを使う場合は `./secrets` に置き、`GOOGLE_SERVICE_ACCOUNT_KEY_FILE=/app/secrets/your-key.json` を設定してください。

## 📚 ドキュメント

- [Docs site](https://sunwood-ai-labs.github.io/harina-v4/)
- [概要](./docs/ja/guide/overview.md)
- [CLI](./docs/ja/guide/cli.md)
- [データセットダウンローダー](./docs/ja/guide/dataset-downloader.md)
- [Gemini スモークテスト](./docs/ja/guide/gemini-smoke-test.md)
- [Google 設定](./docs/ja/guide/google-setup.md)
- [デプロイ](./docs/ja/guide/deployment.md)

## 🗂 リポジトリ構成

```text
app/                  Python bot 実装
docs/                 VitePress ドキュメント
.github/workflows/    CI と GitHub Pages
Dockerfile            コンテナイメージ定義
docker-compose.yml    セルフホスト用構成
```

## 🛠 運用メモ

- `DISCORD_CHANNEL_IDS` を空にすると、アクセス可能な全チャンネルを対象にします
- `DISCORD_CHANNEL_IDS` にカンマ区切りの ID を入れると対象を制限できます
- bot 起動時に Google Sheets のヘッダー行を自動作成します
- 必須設定が不足している場合は起動時に失敗します
- `DISCORD_DATASET_OUTPUT_DIR` で downloader の既定保存先を変更できます
- `DISCORD_TEST_CHANNEL_ID` で `harina bot upload-test` の既定チャンネルを設定できます
- `DISCORD_TEST_MESSAGE_PREFIX` で CLI テスト投稿として扱う自己投稿メッセージの接頭辞を変えられます

## 💻 開発

```bash
uv sync
uv run pytest
uv run harina --help
npm --prefix docs install
npm --prefix docs run docs:build
```

## 📄 ライセンス

[MIT](./LICENSE)
