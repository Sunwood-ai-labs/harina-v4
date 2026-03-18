# 概要

Harina Receipt Bot は、レシート画像の取り込み、OCR、台帳化を自前で回すための自動化スタックです。
Discord 起点と Google Drive 起点の両方に対応します。

各レシートは Gemini の段階分離フローで扱います。

1. 正規化済みレシート情報と明細を抽出
2. Google Sheets のカテゴリ一覧を使って各商品へカテゴリを付与

## 2 つの動作モード

### 1. Discord レシート受付

- Discord チャンネルの画像添付を監視
- 各レシート画像に対して抽出とカテゴリ付与を実行
- 元画像を Google Drive の `YYYY/MM` に保存
- Google Sheets に商品ごとの 1 行を追記
- Discord にカテゴリ要約、商品ごとのカテゴリ、金額つき明細を返信

### 2. Google Drive watcher 受付

- Google Drive の inbox フォルダをポーリング
- 新着画像を Drive から直接ダウンロード
- Gemini で抽出し、各商品にカテゴリを付与して Google Sheets に追記
- 画像と要約を Discord 通知チャンネルへ投稿
- 成功後に Drive ファイルを processed `YYYY/MM` フォルダへ移動

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
3. Gemini が正規化済みレシート JSON を返す
4. Gemini が抽出結果と `Categories` シートを使って商品ごとのカテゴリを返す
5. 元画像を Google Drive の `YYYY/MM` に保存
6. `Receipts` に商品ごとの 1 行を書き込み、必要なら `Categories` に新カテゴリも追記する
7. Discord に `カテゴリ`、`商品カテゴリ`、`明細` を含む返信を返す

### Drive watcher フロー

1. ユーザーが Drive inbox フォルダにレシート画像をアップロード
2. watcher が Drive を見て新着画像を取得
3. Gemini が正規化済みのレシート情報と商品カテゴリを返す
4. HARINA が `Receipts` に商品ごとの 1 行を追記
5. HARINA が必要に応じて `Categories` に新カテゴリを追加
6. watcher が `DISCORD_NOTIFY_CHANNEL_ID` に画像つき通知を投稿
7. Drive ファイルを processed `YYYY/MM` フォルダへ移動
8. `DISCORD_SYSTEM_LOG_CHANNEL_ID` を設定している場合でも、無変化の idle scan cycle は新しい `HARINA Scan Summary` を送らず、活動や backlog 変化がある cycle だけ system log に出ます

### Downloader フロー

1. Discord チャンネル URL を `app.dataset_downloader` に渡す
2. downloader が bot token でメッセージ履歴を走査
3. 画像添付を dataset フォルダ構成で保存
4. 再処理や監査用に `metadata.jsonl` を生成

## Drive 保存先

- Discord と CLI の取り込み画像は、メインの Drive アーカイブに `YYYY/MM` で保存されます。
- Drive watcher の元ファイルは、処理成功時も重複スキップ時も `processed/YYYY/MM` へ移動します。
- `purchaseDate` があればその年月、なければ Drive 側の作成日時を使って保存先を決めます。

## 実行スタック

- Python 3.12
- `discord.py`
- `google-genai`
- Google Drive API と Google Sheets API
- ローカル依存管理用の `uv`
- 常時運用用の Docker Compose

## この構成の良さ

- 通知や運用の見える場所を Discord に寄せられる
- Gemini の抽出とカテゴリ付与を分けることで精度調整しやすい
- Drive に原本を残せる
- Sheets を `Receipts` と `Categories` に分けて監査しやすい
- dataset downloader が移行と回帰確認の逃げ道になる

## 次に読むもの

- [CLI](./cli.md)
- [Google セットアップ](./google-setup.md)
- [デプロイ](./deployment.md)
- [リリースノート v4.2.0](./release-notes-v4.2.0.md)
- [データセットダウンローダー](./dataset-downloader.md)
- [Gemini スモークテスト](./gemini-smoke-test.md)
