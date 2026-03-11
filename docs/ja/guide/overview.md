# 概要

Harina Receipt Bot は、レシート画像の取り込み、OCR、台帳化を自前で回すための自動化スタックです。
Discord 起点と Google Drive 起点の両方に対応します。

## 2 つの動作モード

### 1. Discord レシート受付

- Discord チャンネルの画像添付を監視
- 各レシート画像を Gemini へ送って構造化抽出
- 元画像を Google Drive に保存
- Google Sheets に 1 レシート 1 行で追記
- Discord に短い要約を返信

### 2. Google Drive watcher 受付

- Google Drive の inbox フォルダをポーリング
- 新着画像を Drive から直接ダウンロード
- Gemini で抽出して Google Sheets に追記
- 画像と要約を Discord 通知チャンネルへ投稿
- 成功後に Drive ファイルを processed フォルダへ移動

## CLI 中心の構成

HARINA V4 は Python パッケージ CLI を中心に整理されています。

- `harina bot run`: 常時稼働の Discord bot
- `harina drive watch`: Google Drive watcher
- `harina google init-resources`: メインの Drive フォルダと Spreadsheet を作成
- `harina google init-drive-watch`: watcher 用の inbox / processed フォルダを作成
- `harina dataset download`: Discord 画像を dataset として保存
- `harina dataset smoke-test`: ローカル画像を Gemini で軽く確認
- `harina bot upload-test`: 実画像を Discord に投稿して bot 応答まで確認

## アーキテクチャ図

![Harina V4 アーキテクチャ図](../../architecture/harina-v4-flow.ja.svg)

## 処理フロー

### Discord bot フロー

1. ユーザーが監視対象の Discord チャンネルにレシート画像を投稿
2. bot が Discord から画像 bytes を取得
3. Gemini が正規化済み JSON を返す
4. 元画像を Google Drive に保存
5. Google Sheets に対応する 1 行を書き込む
6. Discord に要約返信を返す

### Drive watcher フロー

1. ユーザーが Drive inbox フォルダにレシート画像をアップロード
2. watcher が Drive を見て新着画像を取得
3. Gemini が正規化済みのレシート情報を返す
4. HARINA が Google Sheets に 1 行追記
5. watcher が `DISCORD_NOTIFY_CHANNEL_ID` に画像つき通知を投稿
6. Drive ファイルを processed フォルダへ移動

### Downloader フロー

1. Discord チャンネル URL を `app.dataset_downloader` に渡す
2. downloader が bot token でメッセージ履歴を走査
3. 画像添付を dataset フォルダ構成で保存
4. 再処理や監査用に `metadata.jsonl` を生成

## 実行スタック

- Python 3.12
- `discord.py`
- `google-genai`
- Google Drive API と Google Sheets API
- ローカル依存管理用の `uv`
- 常時運用用の Docker Compose

## この構成の良さ

- 通知や運用の見える場所を Discord に寄せられる
- Gemini で OCR と構造化抽出をまとめて処理できる
- Drive に原本を残せる
- Sheets を台帳としてそのまま使いやすい
- dataset downloader が移行と回帰確認の逃げ道になる

## 次に読むもの

- [CLI](./cli.md)
- [Google セットアップ](./google-setup.md)
- [デプロイ](./deployment.md)
- [データセットダウンローダー](./dataset-downloader.md)
- [Gemini スモークテスト](./gemini-smoke-test.md)
