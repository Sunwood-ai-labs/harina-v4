# Google 設定

## 1. サービスアカウントを作成する

Google Cloud でサービスアカウントを作成し、同じプロジェクトで次を有効化します。

- Google Drive API
- Google Sheets API

JSON キーをダウンロードするか、JSON 本文をシークレットストアに保存します。

## 2. Drive を準備する

元のレシート画像を保存するフォルダを作成します。

- URL からフォルダ ID を控える
- そのフォルダをサービスアカウントのメールアドレスに共有する
- `GOOGLE_DRIVE_FOLDER_ID` にその ID を設定する

## 3. Sheets を準備する

抽出結果を書き込むスプレッドシートを作成します。

- URL からスプレッドシート ID を控える
- 同じサービスアカウントに共有する
- `GOOGLE_SHEETS_SPREADSHEET_ID` にその ID を設定する
- 既定の `Receipts` 以外を使いたい場合は `GOOGLE_SHEETS_SHEET_NAME` を設定する

## 4. 認証情報の渡し方を決める

次のどちらかを使います。

- `GOOGLE_SERVICE_ACCOUNT_JSON`
  JSON 本文を環境変数へ直接入れる
- `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`
  JSON ファイルをマウントし、そのパスを指定する

Docker Compose を使う場合は、ファイルベースの秘密情報を `./secrets` に置き、`/app/secrets` へマウントする構成を想定しています。
