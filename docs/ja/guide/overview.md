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
3. 既存の `attachmentName` が全レシートタブ内で見つかった場合は `Receipt Skipped` で早期終了
4. Gemini が正規化済みレシート JSON を返す
5. Gemini が抽出結果と `Categories` シートを使って商品ごとのカテゴリを返す
6. 元画像を Google Drive の `YYYY/MM` に保存
7. `2025` のような年別レシートタブに商品ごとの 1 行を書き込み、必要なら `Categories` に新カテゴリも追記する
8. Discord に `カテゴリ`、`商品カテゴリ`、`明細` を含む返信を返す

### Drive watcher フロー

1. ユーザーが Drive inbox フォルダにレシート画像をアップロード
2. watcher が Drive を見て新着画像を取得
3. 既存の `attachmentName` が全レシートタブ内で見つかった場合は Discord 通知や row 追記をせず、重複として処理する
4. Gemini が正規化済みのレシート情報と商品カテゴリを返す
5. HARINA が `2025` のような年別レシートタブに商品ごとの 1 行を追記
6. HARINA が必要に応じて `Categories` に新カテゴリを追加
7. watcher が `DISCORD_NOTIFY_CHANNEL_ID` に画像つき通知を投稿し、Gemini usage metadata がある場合は `Gemini Model` と `API Cost (est.)` も表示
8. Drive ファイルを processed `YYYY/MM` フォルダへ移動
9. `DISCORD_SYSTEM_LOG_CHANNEL_ID` を設定している場合でも、無変化の idle scan cycle は新しい `HARINA Scan Summary` を送らず、活動や backlog 変化がある cycle だけ system log に出ます

### Downloader フロー

1. Discord チャンネル URL を `app.dataset_downloader` に渡す
2. downloader が bot token でメッセージ履歴を走査
3. 画像添付を dataset フォルダ構成で保存
4. 再処理や監査用に `metadata.jsonl` を生成

## Drive 保存先

- Discord と CLI の取り込み画像は、メインの Drive アーカイブに `YYYY/MM` で保存されます。
- Drive watcher の元ファイルは、処理成功時も重複スキップ時も `processed/YYYY/MM` へ移動します。
- Discord / CLI 側の Drive 保存は `purchaseDate` を優先し、無ければ現在の処理年月へ保存します。
- Drive watcher の正常処理後の移動先は `purchaseDate` を優先し、無ければ Drive 側の作成日時を使います。
- 重複スキップ時は抽出を走らせないため、Drive 側の作成日時ベースで移動先を決めます。

## Gemini モデルのレーン分け

- `bot run` と `drive watch` は `GEMINI_MODEL` を使います。
- `receipt process`、`bot upload-test`、`dataset smoke-test`、`test docs-public` の検証系は `GEMINI_TEST_MODEL` を使います。
- `GEMINI_API_KEY_ROTATION_LIST` を使うと、主 `GEMINI_API_KEY` の後ろに追加 key 群をつなげます。
- Gemini の一時的な失敗は key ごとに 60 秒間隔で最大 5 回まで再試行します。
- daily quota 枯渇は次の key へ即 rotate します。
- すべての key を使い切った場合は `receipt-bot` が 1 時間、`drive-watcher` が 12 時間待って 1 回だけ最初の key 群へ戻ります。watcher はこの待機を `HARINA Watch Status` で通知します。

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
- Sheets を年別レシートタブと `Categories` に分けて監査しやすい
- dataset downloader が移行と回帰確認の逃げ道になる

## 次に読むもの

- [CLI](./cli.md)
- [Google セットアップ](./google-setup.md)
- [デプロイ](./deployment.md)
- [リリースノート v4.4.0](./release-notes-v4.4.0.md)
- [Harina v4.4.0 解説](./whats-new-v4.4.0.md)
- [データセットダウンローダー](./dataset-downloader.md)
- [Gemini スモークテスト](./gemini-smoke-test.md)
