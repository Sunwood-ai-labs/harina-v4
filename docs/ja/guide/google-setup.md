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

Sheets 関連の主な設定:

- `GOOGLE_SHEETS_SHEET_NAME` の既定値は `Receipts` で、`.env` に残す bootstrap/fallback 用の受け皿シート名として使われます
- `GOOGLE_SHEETS_CATEGORY_SHEET_NAME` の既定値は `Categories`

Docker Compose では、ファイルベース secret を `./secrets` に置いて `/app/secrets` へマウントする前提です。

## 2. 個人 Gmail は OAuth refresh token を推奨

個人 Google Drive に書き込むなら、service account より OAuth refresh token の方が安定します。

```bash
uv run harina-v4 google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
```

一度 refresh token を保存すれば、その後は自動でアクセストークン更新できます。

### 専用エージェントアカウントを長期運用する場合

HARINA 専用の Google アカウントで常時運用するなら、OAuth consent screen は `In production` にしてください。`External + Testing` のままだと refresh token が短期間で失効し、HARINA では `invalid_grant: Token has been expired or revoked.` として見えることがあります。詳細は [Google OAuth 2.0 guide](https://developers.google.com/identity/protocols/oauth2) を参照してください。

### 既存ブラウザを使った token 再取得

`google oauth-login` が最短ですが、すでにログイン済みのブラウザを使いたいときは `oauth-start` と `oauth-finish` に分けられます。

```bash
uv run harina-v4 google oauth-start --oauth-client-secret-file ./secrets/harina-oauth-client.json --session-file .harina-google-oauth-session.json
uv run harina-v4 google oauth-finish --session-file .harina-google-oauth-session.json --redirect-url "http://127.0.0.1:8765/?state=...&code=..."
```

Codex で運用しているなら、[logged-in-google-chrome-skill](https://github.com/Sunwood-ai-labs/logged-in-google-chrome-skill) を組み合わせると、専用 Chrome プロファイルの起動と consent 操作を自動化しやすくなります。

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
- bootstrap 用の `Receipts` と `Categories` のシートタブとヘッダー行を保証
- 後続の row 追記時には `2025` のような年タブを自動作成
- `Categories` が空なら一語カテゴリを初期投入
- 必要に応じて ID と URL を `.env` へ保存

`Categories` は Gemini が毎回読むライブのカテゴリ一覧です。  
`惣菜・弁当` や `惣菜/弁当` のような旧表記が残っていても、現在の `惣菜` のような短い一語ラベルへ正規化されます。

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
watcher の実行時には、`GOOGLE_DRIVE_WATCH_PROCESSED_FOLDER_ID` 配下に `YYYY/MM` サブフォルダを必要に応じて自動作成します。

## 5. 注意点

- `Receipts` は bootstrap/fallback 名で、実際の商品行は `2025` のような年別レシートタブに入ります
- 各商品行には `itemCategory` も保存されます
- カテゴリ付与の前に Gemini は `Categories` を読み、合う候補がなければ短い新カテゴリを提案できます
- `attachmentName` の重複判定は `Categories` を除く全レシートタブを横断します
- 個人 Google Drive では service account に Drive 容量がなく、アップロードが拒否されることがあります
- 個人 Gmail 環境では OAuth refresh token を優先してください
- `.env` の `GOOGLE_OAUTH_REFRESH_TOKEN` を更新したあとは、Docker Compose サービスを再作成して新しい値を反映してください
- 手動で作る場合も、メイン Drive フォルダと watcher 用フォルダの両方に対して選んだ認証主体が書き込みできる必要があります
