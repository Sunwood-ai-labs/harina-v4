# Google 設定

## 1. サービスアカウントを作成

Google Cloud でサービスアカウントを作成し、次を有効化します。

- Google Drive API
- Google Sheets API

JSON キーをダウンロードするか、JSON 文字列を安全なシークレットに保存してください。

## 2. Drive を準備

元画像の保存先フォルダを作成します。

- URL からフォルダ ID を控える
- サービスアカウントのメールアドレスに共有する
- `GOOGLE_DRIVE_FOLDER_ID` にその ID を設定する

## 3. Sheets を準備

抽出データ保存用のスプレッドシートを作成します。

- URL からスプレッドシート ID を控える
- 同じサービスアカウントに共有する
- `GOOGLE_SHEETS_SPREADSHEET_ID` にその ID を設定する
- 必要なら `GOOGLE_SHEETS_SHEET_NAME` でシート名を変更する

## 4. 認証情報の渡し方

次のどちらかで設定します。

- `GOOGLE_SERVICE_ACCOUNT_JSON`
  JSON 本文を環境変数に直接入れる
- `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`
  JSON ファイルをマウントして、コンテナ内パスを渡す

Docker Compose では、ファイル型シークレットは `./secrets` から `/app/secrets` にマウントする想定です。
