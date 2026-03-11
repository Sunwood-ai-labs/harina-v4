# CLI

HARINA V4 は `harina-v4` という Python CLI を中心に構成されています。
短い互換エイリアスとして `harina` も使えます。

## CLI を使う理由

- bot 運用、Drive watcher、移行、検証を 1 つのコマンド体系にまとめられる
- 常時稼働サービスと単発オペレーションで同じロジックを再利用できる
- ローカル実行、CI、Docker 自動化をそろえやすい

## 基本ヘルプ

```bash
uv run harina-v4 --help
```

## receipt コマンド

ローカルのレシート画像を CLI-first パイプラインで処理します。

```bash
uv run harina-v4 receipt process ./sample-receipt.jpg --skip-google-write
```

補足:

- `receipt process` は Discord bot と同じ Gemini 中心の処理パイプラインを使います
- `--skip-google-write` は `GEMINI_API_KEY` だけで抽出確認したいときに便利です
- 外すと Drive への保存と Sheets 追記まで実行します

## bot コマンド

常時稼働の Discord bot を起動します。

```bash
uv run harina-v4 bot run
```

実画像を Discord に投稿して bot 応答まで確認します。

```bash
uv run harina-v4 bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

## Drive watcher コマンド

1 回だけ watcher を回して終了:

```bash
uv run harina-v4 drive watch --once
```

watcher を常駐実行:

```bash
uv run harina-v4 drive watch
```

補足:

- `drive watch` は `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID` から画像を読みます
- 通知先は `DISCORD_NOTIFY_CHANNEL_ID` です
- 成功したファイルは `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID` へ移動します
- ポーリング間隔は `DRIVE_POLL_INTERVAL_SECONDS` で決まります

## Google コマンド

1 回だけ OAuth ログインして refresh token を保存:

```bash
uv run harina-v4 google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
```

メインの Drive フォルダと Spreadsheet を作成または再利用:

```bash
uv run harina-v4 google init-resources --env-file .env
```

watcher 用の Drive フォルダを作成または再利用:

```bash
uv run harina-v4 google init-drive-watch --env-file .env
```

watcher セットアップで便利なオプション:

- `--source-folder-name "Harina V4 Drive Inbox"`
- `--processed-folder-name "Harina V4 Drive Processed"`
- `--parent-folder-id <folder_id>`
- `--poll-interval-seconds 60`

## dataset コマンド

Discord 画像を dataset として保存:

```bash
uv run harina-v4 dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 50
```

ローカル dataset に対して Gemini の軽い確認:

```bash
uv run harina-v4 dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

## おすすめ運用フロー

1. 個人 Gmail なら `harina-v4 google oauth-login` を先に実行
2. `harina-v4 google init-resources` で Drive / Sheets を作成
3. `harina-v4 google init-drive-watch` で watcher フォルダを作成
4. `harina-v4 receipt process --skip-google-write` で抽出確認
5. `harina-v4 bot upload-test` で Discord 側の動作確認
6. `harina-v4 drive watch --once` で Drive watcher の単発確認
7. `harina-v4 bot run` と `harina-v4 drive watch` を常時稼働
