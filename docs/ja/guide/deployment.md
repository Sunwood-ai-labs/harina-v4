# デプロイ

常時稼働の Discord bot には `harina bot run` を使います。
Google Drive watcher には `harina drive watch` を使います。
移行や確認だけなら `harina dataset download` や `harina dataset smoke-test` を使います。

## ローカル開発

```bash
uv sync
uv run pytest
uv run harina-v4 bot run
```

## 単発確認

Discord アップロード経路:

```bash
uv run harina-v4 bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

Drive watcher 経路:

```bash
uv run harina-v4 drive watch --once
```

Gemini スモークテスト:

```bash
uv run harina-v4 dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

## Docker Compose

1. `.env.example` を `.env` にコピー
2. Discord、Gemini、Drive、Sheets の設定を入れる
3. `harina-v4 google init-resources --env-file .env` を実行
4. `harina-v4 google init-drive-watch --env-file .env` を実行
5. JSON キーファイルを使うなら `./secrets` に配置
6. サービスを起動

```bash
docker compose up -d --build
docker compose logs -f receipt-bot
docker compose logs -f drive-watcher
```

## 必須環境変数

receipt bot 側:

- `DISCORD_TOKEN`
- `GEMINI_API_KEY`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- service account または OAuth refresh token の Google 認証

Drive watcher 側:

- `DISCORD_NOTIFY_CHANNEL_ID`
- `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID`
- `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID`
- `DRIVE_POLL_INTERVAL_SECONDS`

## 運用メモ

- `DISCORD_CHANNEL_IDS` を空にするとアクセス可能な Discord チャンネルをすべて監視
- `DISCORD_CHANNEL_IDS` をカンマ区切りで入れると Discord intake を制限
- bot は対象シートのヘッダー行を自動で作成
- watcher は `DISCORD_NOTIFY_CHANNEL_ID` に画像つき通知を投稿
- 成功した Drive ファイルは processed フォルダへ移動
- 必須設定が足りない場合は起動時に即失敗
- `DISCORD_DATASET_OUTPUT_DIR` は downloader の既定出力先
