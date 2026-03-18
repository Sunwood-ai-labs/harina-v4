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

`.env` を更新したとき、特に `GOOGLE_OAUTH_REFRESH_TOKEN` を差し替えたときは `docker compose restart` ではなく再作成を使ってください。

```bash
docker compose up -d --force-recreate receipt-bot drive-watcher
```

コード変更も含めて反映したい場合は `--build` も付けます。

```bash
docker compose up -d --build --force-recreate receipt-bot drive-watcher
```

## 必須環境変数

receipt bot 側:

- `DISCORD_TOKEN`
- `GEMINI_API_KEY`
- 本番 bot 用の `GEMINI_MODEL`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- service account または OAuth refresh token の Google 認証

Drive watcher 側:

- `DISCORD_NOTIFY_CHANNEL_ID`
- `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID`
- `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID`
- `DRIVE_POLL_INTERVAL_SECONDS`

検証系で追加するとよい設定:

- `GEMINI_TEST_MODEL`: `receipt process`、`bot upload-test`、`dataset smoke-test`、`test docs-public` の検証レーン
- `GEMINI_API_KEY_ROTATION_LIST`: quota rotation に使うカンマまたは改行区切りの追加 key 群

## 運用メモ

- `DISCORD_CHANNEL_IDS` を空にするとアクセス可能な Discord チャンネルをすべて監視
- `DISCORD_CHANNEL_IDS` をカンマ区切りで入れると Discord intake を制限
- bot は対象シートのヘッダー行を自動で作成
- 商品行は `2025` のような年別シートタブへ追記されます
- watcher は `DISCORD_NOTIFY_CHANNEL_ID` に画像つき通知を投稿
- 成功した Drive ファイルは processed フォルダへ移動
- 毎 poll ごとに heartbeat 的な `HARINA Scan Summary` が出るわけではなく、無変化の idle poll は Discord ノイズ削減のため抑制されます
- Drive の結果 embed は、Gemini usage metadata がある場合に `Gemini Model` と `API Cost (est.)` を表示できます
- Gemini の一時失敗は key ごとに 60 秒間隔で最大 5 回まで再試行し、daily quota 枯渇は次の key へ即 rotate します
- すべての key が尽きた場合は delayed retry cycle に入り、`receipt-bot` は 1 時間、`drive-watcher` は 12 時間待機します。watcher は `HARINA Watch Status` も投稿します
- 稼働確認が必要なときは startup / progress の system log やコンテナログを確認してください
- watcher が動いているはずなのに system log がまったく出ない場合は、`DISCORD_SYSTEM_LOG_CHANNEL_ID` と Discord 接続をコンテナログで確認してください
- 必須設定が足りない場合は起動時に即失敗
- `DISCORD_DATASET_OUTPUT_DIR` は downloader の既定出力先
- 本番に近いスモークテストとして、`Bob` の source folder に重複しない画像を 1 枚入れ、`HARINA V4 Intake // Bob`、`HARINA Progress // Bob`、`Bob/_processed/YYYY/MM` への移動を確認すると安全です
