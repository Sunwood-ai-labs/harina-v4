# 概要

Harina Receipt Bot は、レシート運用向けのセルフホスト Discord bot であり、移行や再実行に使えるワンショットのデータセットダウンローダーでもあります。

## 2つの運用モード

### 1. 常時レシート処理

- Discord の画像添付メッセージを監視
- Gemini でレシートを構造化抽出
- 元画像を Google Drive に保存
- レシートごとに Google Sheets へ 1 行追加
- Discord に処理結果の要約を返信

### 2. 履歴バックフィルと再スキャン

- Discord 上の過去レシート画像をローカルデータセットとして取得
- 元のアップロードファイル名を保持
- V1、V2、V3 のチャンネル履歴を新運用へ移行
- Gemini モデル、プロンプト、スキーマ、後段ロジック変更後に旧データを再処理

## 処理の流れ

### 常時 bot の流れ

1. 監視対象チャンネルにレシート画像が投稿されます。
2. bot が Discord から画像を直接取得します。
3. Gemini が正規化済み JSON を返します。
4. 元画像を Google Drive に保存します。
5. 対応する 1 行を Google Sheets に書き込みます。
6. Discord に要約メッセージを返信します。

### downloader の流れ

1. `app.dataset_downloader` に Discord チャンネル URL を渡します。
2. bot トークンでメッセージ履歴を走査します。
3. 画像添付をデータセット用フォルダへ保存します。
4. 再実行や監査に使える `metadata.jsonl` を出力します。

## 実行スタック

- Python 3.12
- `discord.py`
- `google-genai`
- Google Drive API と Google Sheets API
- ローカル依存管理用の `uv`
- 常時運用向けの Docker Compose

## この構成が向いている理由

- 入力面は普段使っている Discord のままでよい
- Gemini で OCR と項目抽出を低コストにまとめられる
- Drive に元証憑を残せる
- Sheets に会計向けの扱いやすい形で集約できる
- downloader があるので、システム更新時も安全に移行と回帰確認ができる

## 次に読むもの

- V1、V2、V3 から移行するなら [データセットダウンローダー](./dataset-downloader.md)
- 常時 bot を動かす前提を整えるなら [Google 設定](./google-setup.md)
- 継続運用するなら [デプロイ](./deployment.md)
