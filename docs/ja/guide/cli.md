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

同じファイル名が Google Sheets に既にあっても明示的に再実行したい場合:

```bash
uv run harina-v4 receipt process ./sample-receipt.jpg --rescan
```

`docs/public/test` の画像を使って CLI と Discord の両方をまとめて確認:

```bash
uv run harina-v4 test docs-public
```

補足:

- `receipt process` は Discord bot と同じ 2 段階 Gemini パイプラインを使います
- `--skip-google-write` は `GEMINI_API_KEY` だけでローカル確認したいときに便利です
- `--skip-google-write` 中は Sheets のカテゴリ一覧を読めないため、Gemini が短い自由カテゴリを付けます
- 外すと Drive 保存、Sheets 追記、`Categories` シートを使ったカテゴリ付与まで実行します

## bot コマンド

常時稼働の Discord bot を起動します。

```bash
uv run harina-v4 bot run
```

実画像を Discord に投稿して bot 応答まで確認します。

```bash
uv run harina-v4 bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

複数枚を 1 メッセージで送ることもできます:

```bash
uv run harina-v4 bot upload-test --channel-id <channel_id> --image ./docs/public/test/one/IMG_8923.jpg ./docs/public/test/two/IMG_9780.jpg
```

補足:

- `test docs-public` は `docs/public/test` 配下の対応画像をすべて走査します
- 既定の `--mode both` で CLI 経路と Discord 経路をまとめて確認できます
- 片側だけ確認したい場合は `--mode cli` または `--mode discord` を使います
- Discord 側は `--channel-id` を省略すると `DISCORD_TEST_CHANNEL_ID` を使います
- 成功した Discord 返信には `カテゴリ`、`商品カテゴリ`、`明細` が表示されます

## Drive watcher コマンド

1 回だけ watcher を回して終了:

```bash
uv run harina-v4 drive watch --once
```

重複ファイル名も明示的に再処理したい場合:

```bash
uv run harina-v4 drive watch --once --rescan
```

watcher を常駐実行:

```bash
uv run harina-v4 drive watch
```

補足:

- `drive watch` は `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID` から画像を読みます
- 通知先は `DISCORD_NOTIFY_CHANNEL_ID` です
- 成功したファイルは `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID/YYYY/MM` へ移動します
- 重複ファイル名をスキップした場合も、同じ `processed/YYYY/MM` へ移動します
- `DISCORD_SYSTEM_LOG_CHANNEL_ID` を設定している場合でも、無変化の idle poll では `HARINA Scan Summary` は連投しません
- ファイルの処理、重複スキップ、失敗、backlog 変化がある cycle は system log に出ます
- ポーリング間隔は `DRIVE_POLL_INTERVAL_SECONDS` で決まります

## Google コマンド

1 回だけ OAuth ログインして refresh token を保存:

```bash
uv run harina-v4 google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
```

ログイン済みブラウザを使いたいときは、先に認可 URL を発行:

```bash
uv run harina-v4 google oauth-start --oauth-client-secret-file ./secrets/harina-oauth-client.json --session-file .harina-google-oauth-session.json
```

最後に redirect URL を渡して token を保存:

```bash
uv run harina-v4 google oauth-finish --session-file .harina-google-oauth-session.json --redirect-url "http://127.0.0.1:8765/?state=...&code=..."
```

メインの Drive フォルダと Spreadsheet を作成または再利用:

```bash
uv run harina-v4 google init-resources --env-file .env
```

補足:

- `google init-resources` は `Receipts` と `Categories` の両方を保証します
- `GOOGLE_SHEETS_CATEGORY_SHEET_NAME` の既定値は `Categories` です
- `Categories` には `野菜`、`惣菜`、`飲料` などの一語カテゴリが初期投入されます

watcher 用の Drive フォルダを作成または再利用:

```bash
uv run harina-v4 google init-drive-watch --env-file .env
```

watcher セットアップで便利なオプション:

- `--source-folder-name "Harina V4 Drive Inbox"`
- `--processed-folder-name "Harina V4 Drive Processed"`
- `--parent-folder-id <folder_id>`
- `--poll-interval-seconds 60`

Google 認証まわりの補足:

- 既存のログイン済み Chrome を使いたいときは `google oauth-start` と `google oauth-finish` を組み合わせます
- Codex では [logged-in-google-chrome-skill](https://github.com/Sunwood-ai-labs/logged-in-google-chrome-skill) がこの復旧フローに向いています
- `.env` の `GOOGLE_OAUTH_REFRESH_TOKEN` を更新したあとは Docker Compose サービスを再作成してください

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

## カテゴリの挙動

- 書き込みありの実行では毎回 `Categories` シートを読みます
- カテゴリはレシート単位ではなく商品ごとに付きます
- 既存候補に合わない場合は Gemini が短い新カテゴリを提案できます
- 新カテゴリは次回以降に使えるよう `Categories` シートへ追記されます

## Drive watcher 保存先

- Drive watcher で正常処理または重複スキップされたファイルは `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID/YYYY/MM` に移動されます。
- `purchaseDate` があればその年月、なければ Drive 側の作成日時で processed サブフォルダを選びます。
