[English](./README.md)

# Harina Receipt Bot

Discord に投稿されたレシート画像を監視し、Gemini 3 で内容を抽出して、元画像を Google Drive に保存し、抽出データを Google スプレッドシートへ追記する bot です。

## できること

- Discord チャンネルにアップロードされたレシート画像を検知
- Gemini 3 で店舗名、日付、合計、税額、支払方法、明細を抽出
- 元画像を Google Drive の指定フォルダへ保存
- 抽出結果を Google スプレッドシートへ 1 レシート 1 行で追記
- 初回起動時にスプレッドシートのヘッダー行を自動作成

## 処理の流れ

1. Discord にレシート画像を投稿
2. bot が添付画像をダウンロード
3. Gemini 3 へ画像を送って構造化データを生成
4. 元画像を Google Drive にアップロード
5. 抽出結果を Google スプレッドシートに追記
6. Discord に処理結果の要約を返信

## セットアップ

### 1. Discord bot を作成

- [Discord Developer Portal](https://discord.com/developers/applications) でアプリを作成
- Bot ユーザーを作り、トークンを取得
- `MESSAGE CONTENT INTENT` を有効化
- メッセージ読取、添付ファイル参照、リアクション追加、メッセージ送信権限でサーバーに招待

### 2. Gemini API を用意

- [Google AI Studio](https://aistudio.google.com/) で API キーを発行
- `GEMINI_API_KEY` に設定
- 既定モデルは `gemini-3-flash-preview`

### 3. Google Drive / Sheets を用意

- Google Cloud でサービスアカウントを作成
- Drive API と Sheets API を有効化
- JSON キーを取得するか、JSON 文字列を環境変数に保存
- レシート画像保存用の Drive フォルダを作成
- データ保存用のスプレッドシートを作成
- フォルダとスプレッドシートをサービスアカウントのメールアドレスへ共有

### 4. 環境変数を設定

`.env.example` を `.env` にコピーして設定します。

```bash
DISCORD_TOKEN=...
DISCORD_CHANNEL_IDS=123456789012345678,234567890123456789
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3-flash-preview
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
GOOGLE_DRIVE_FOLDER_ID=...
GOOGLE_SHEETS_SPREADSHEET_ID=...
GOOGLE_SHEETS_SHEET_NAME=Receipts
```

`GOOGLE_SERVICE_ACCOUNT_JSON` の代わりに `GOOGLE_SERVICE_ACCOUNT_KEY_FILE` も使えます。

## 開発コマンド

```bash
npm install
npm run test
npm run build
npm run dev
```

## 補足

- `DISCORD_CHANNEL_IDS` を空にすると、bot が読める全チャンネルで画像を処理します。
- Gemini が自信を持って読めない項目は空欄のまま保存します。
- 本番運用ではサービスアカウント JSON を平文 `.env` ではなく Secret Manager などに置くのがおすすめです。

## ライセンス

[MIT](./LICENSE)
