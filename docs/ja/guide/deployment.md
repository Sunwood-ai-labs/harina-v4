# デプロイ

常時稼働させる bot は `harina bot run` を使います。移行や再スキャンのために一度だけ取得したい場合は `harina dataset download` を使います。
ローカルのデータセット画像で Gemini の応答を軽く確認したい場合は `harina dataset smoke-test` を使います。

## ローカル開発

```bash
uv sync
uv run pytest
uv run harina bot run
```

## ワンショット downloader 実行

```bash
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 50
```

## Gemini スモークテスト実行

```bash
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

## Discord アップロードテスト実行

```bash
uv run harina bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

## Docker Compose

1. `.env.example` を `.env` にコピーする
2. Discord、Gemini、Drive、Sheets の設定を入れる
3. JSON キーファイルを使う場合は `./secrets` に置く
4. サービスを起動する

```bash
docker compose up -d --build
docker compose logs -f
```

## 必須の環境変数

- `DISCORD_TOKEN`
- `GEMINI_API_KEY`
- `GOOGLE_DRIVE_FOLDER_ID`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON` または `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`

## 運用メモ

- `DISCORD_CHANNEL_IDS` を空にすると、アクセス可能な全チャンネルを監視します
- `DISCORD_CHANNEL_IDS` にカンマ区切りの ID を入れると対象を制限できます
- bot 起動時に対象シートのヘッダー行を自動作成します
- 必須設定が不足している場合は起動時に失敗します
- `DISCORD_DATASET_OUTPUT_DIR` で downloader の既定保存先を変更できます
