# 概要

Harina Receipt Bot は、Discord を入口にしたレシート収集 bot です。

## できること

- Discord メッセージ内の画像添付を監視
- Gemini でレシート内容を構造化抽出
- 元画像を Google Drive に保存
- 1 レシートごとに Google スプレッドシートへ追記
- Discord 上で処理結果を要約返信

## 処理の流れ

1. ユーザーが監視対象チャンネルにレシート画像を投稿します。
2. bot が Discord から画像をダウンロードします。
3. Gemini が正規化済み JSON を返します。
4. 元画像を Google Drive に保存します。
5. 対応するデータ行を Google スプレッドシートへ追加します。
6. Discord に簡単な結果サマリを返信します。

## 技術スタック

- Python 3.12
- `discord.py`
- `google-genai`
- Google Drive API / Google Sheets API
- ローカル依存管理に `uv`
- 常駐運用に Docker Compose

## この構成の良さ

- 入力は Discord のままで運用できる
- Gemini で OCR と項目抽出を一度に扱える
- 元画像を Drive に残せる
- Sheets 側で会計・整理・共有がしやすい
