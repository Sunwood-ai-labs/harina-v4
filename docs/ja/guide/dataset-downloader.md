# データセットダウンローダー

`app.dataset_downloader` は、Discord にある過去レシート画像をローカルに取り込みたいときのための CLI です。

## 向いている用途

- V1、V2、V3 のチャンネルから新環境へデータ移行したい
- Gemini モデル変更後に旧レシートを再スキャンしたい
- プロンプトや出力スキーマ変更後に再抽出したい
- 回帰テストや評価用の固定データセットを作りたい

## 基本コマンド

```bash
uv run python -m app.dataset_downloader "https://discord.com/channels/<guild_id>/<channel_id>"
```

## よく使う例

直近 5 メッセージだけ取得:

```bash
uv run python -m app.dataset_downloader "https://discord.com/channels/<guild_id>/<channel_id>" --limit 5
```

移行用にバージョン別フォルダへ保存:

```bash
uv run python -m app.dataset_downloader "https://discord.com/channels/<guild_id>/<channel_id>" --output-dir ./dataset/v3-backfill
```

既存ファイルを上書きして再取得:

```bash
uv run python -m app.dataset_downloader "https://discord.com/channels/<guild_id>/<channel_id>" --overwrite
```

## 出力構成

各添付ファイルは、元のアップロードファイル名を保持したまま保存されます。

```text
dataset/
  discord-images/
    guild-<name-or-id>/
      channel-<name-or-id>/
        message-<id>/
          attachment-<id>/
            original-file-name.jpg
    metadata.jsonl
```

補足:

- サーバー名またはチャンネル名に日本語が含まれる場合、フォルダ名は数値 ID にフォールバックします
- `metadata.jsonl` には message、author、attachment、source URL など再利用向けの情報が入ります
- `DISCORD_DATASET_OUTPUT_DIR` で既定の保存先ルートを変更できます

## 必要な権限

- bot が対象サーバーに参加していること
- 対象チャンネルを閲覧できること
- メッセージ履歴を参照できること
- Discord Developer Portal で `MESSAGE CONTENT INTENT` を有効化していること

## おすすめの移行手順

1. まず `--limit 5` や `--limit 50` で小さく確認する
2. フォルダ構成と `metadata.jsonl` を確認する
3. `dataset/v3-backfill` のようなバージョン付きフォルダへ本番取得する
4. 新しい抽出ロジックや正規化パイプラインに流し込む
5. V1、V2、V3 の既存結果と比較してから切り替える
