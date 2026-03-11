# Google 設定

## 1. サービスアカウントを作成する

Google Cloud でサービスアカウントを作成し、同じプロジェクトで次を有効化します。

- Google Drive API
- Google Sheets API

JSON キーをダウンロードするか、JSON 本文をシークレットストアに保存します。

## 2. 個人 Gmail では OAuth refresh token を優先する

個人の Google Drive に HARINA が書き込む場合は、service account より OAuth refresh token のほうが相性がよいです。

1. Google Cloud で OAuth client を作成する
2. OAuth client の JSON を `./secrets` に置く
3. 次を実行する

```bash
uv run harina google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
```

この認可は最初の 1 回だけで、その後は保存した refresh token で自動更新できます。

## 3. CLI で Drive と Sheets を初期化する

サービスアカウントの JSON キーがあれば、HARINA CLI から Drive フォルダと Spreadsheet を自動作成できます。

```bash
uv run harina google init-resources --service-account-key-file ./secrets/harina-v4-bot.json --env-file .env
```

OAuth を `.env` に設定済みなら、次だけで大丈夫です。

```bash
uv run harina google init-resources --env-file .env
```

よく使うオプション:

- `--folder-name "Harina V4 Receipts"`
- `--spreadsheet-title "Harina V4 Receipts"`
- `--sheet-name Receipts`
- `--share-with-email you@example.com`
- `--env-file .env`

このコマンドは次を行います。

- サービスアカウント所有の Drive フォルダを作成または再利用する
- サービスアカウント所有の Spreadsheet を作成または再利用する
- 目的のシートタブとヘッダー行を揃える
- 必要な `GOOGLE_*` 値を表示する
- 必要ならその値を `.env` に書き込む

`--env-file` を使うと、次のような成果物 URL も `.env` に残せます。

- `GOOGLE_DRIVE_FOLDER_URL`
- `GOOGLE_SHEETS_SPREADSHEET_URL`

運用メモとして、次の optional な Cloud Console 情報も `.env` に残しておくと見返しやすいです。

- `GOOGLE_CLOUD_PROJECT_ID`
- `GOOGLE_CLOUD_PROJECT_NUMBER`
- `GOOGLE_CLOUD_CONSOLE_URL`
- `GOOGLE_CLOUD_CREDENTIALS_URL`
- `GOOGLE_CLOUD_AUTH_OVERVIEW_URL`
- `GOOGLE_OAUTH_CLIENT_ID`

注意:

- 個人の Google Drive では、サービスアカウントに Drive 容量がないためアップロードが拒否されることがあります
- 個人 Gmail で運用する場合は、OAuth refresh token ベースの認証を優先するのが安全です

手動で用意したい場合は、これまでどおり次の手順でも構いません。

- レシート画像保存用フォルダを作成し、`GOOGLE_DRIVE_FOLDER_ID` にフォルダ ID を設定する
- 抽出結果保存用 Spreadsheet を作成し、`GOOGLE_SHEETS_SPREADSHEET_ID` にその ID を設定する
- service account を使う場合は、両方をサービスアカウントへ共有する
- 既定の `Receipts` 以外を使いたい場合は `GOOGLE_SHEETS_SHEET_NAME` を設定する

## 4. 認証情報の渡し方を決める

次のどちらかを使います。

- `GOOGLE_SERVICE_ACCOUNT_JSON`
  JSON 本文を環境変数へ直接入れる
- `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`
  JSON ファイルをマウントし、そのパスを指定する
- `GOOGLE_OAUTH_CLIENT_JSON` と `GOOGLE_OAUTH_REFRESH_TOKEN`
  OAuth client の JSON 本文と refresh token を環境変数へ入れる
- `GOOGLE_OAUTH_CLIENT_SECRET_FILE` と `GOOGLE_OAUTH_REFRESH_TOKEN`
  OAuth client の JSON ファイルを置き、refresh token を環境変数で渡す

Docker Compose を使う場合は、ファイルベースの秘密情報を `./secrets` に置き、`/app/secrets` へマウントする構成を想定しています。
