# Google セットアップ

## 1. 認証方式を決める

同じ Google Cloud project で次の API を有効化します。

- Google Drive API
- Google Sheets API

認証方式は次のどれかを使います。

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`
- `GOOGLE_OAUTH_CLIENT_JSON` + `GOOGLE_OAUTH_REFRESH_TOKEN`
- `GOOGLE_OAUTH_CLIENT_SECRET_FILE` + `GOOGLE_OAUTH_REFRESH_TOKEN`

Docker Compose では、ファイルベース secret を `./secrets` に置いて `/app/secrets` へマウントする前提です。

## 2. 個人 Gmail は OAuth refresh token を推奨

個人 Google Drive に書き込むなら、service account より OAuth refresh token の方が安定します。

```bash
uv run harina-v4 google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
```

一度 refresh token を保存すれば、その後は自動でアクセストークン更新できます。

## 3. CLI で Drive と Sheets を作る

メインのレシート保存先 Drive フォルダと Spreadsheet を作成または再利用します。

```bash
uv run harina-v4 google init-resources --env-file .env
```

便利なオプション:

- `--folder-name "Harina V4 Receipts"`
- `--spreadsheet-title "Harina V4 Receipts"`
- `--sheet-name Receipts`
- `--share-with-email you@example.com`
- `--env-file .env`

このコマンドで:

- メインの Drive フォルダを作成または再利用
- Spreadsheet を作成または再利用
- 対象シートタブとヘッダー行を保証
- 必要に応じて ID と URL を `.env` へ保存

## 4. Drive watcher 用フォルダを作る

watcher 用の inbox フォルダと processed フォルダを作成または再利用します。

```bash
uv run harina-v4 google init-drive-watch --env-file .env
```

便利なオプション:

- `--source-folder-name "Harina V4 Drive Inbox"`
- `--processed-folder-name "Harina V4 Drive Processed"`
- `--parent-folder-id <folder_id>`
- `--poll-interval-seconds 60`
- `--share-with-email you@example.com`
- `--env-file .env`

`--env-file` を使うと次の値を書き込みます。

- `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_ID`
- `GOOGLE_DRIVE_WATCH_SOURCE_FOLDER_URL`
- `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID`
- `GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_URL`
- `DRIVE_POLL_INTERVAL_SECONDS`

すでに `GOOGLE_DRIVE_FOLDER_ID` がある場合は、それを watcher フォルダの親として自動利用します。

## 5. 注意点

- 個人 Google Drive では service account に Drive 容量がなく、アップロードが拒否されることがあります
- 個人 Gmail 環境では OAuth refresh token を優先してください
- 手動で作る場合も、メイン Drive フォルダと watcher 用フォルダの両方に対して選んだ認証主体が書き込みできる必要があります
