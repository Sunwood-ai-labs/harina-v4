# CLI

HARINA V4 は `harina-v4` という Python CLI を中心に構成されています。
短い `harina` も互換用エイリアスとして使えます。

## CLI を使う理由

- bot 運用、移行、再スキャン、確認作業を 1 つのコマンド体系にまとめられます
- 常時稼働 bot と運用用コマンドで同じレシート処理パイプラインを共有できます
- ローカル実行、CI、将来の自動化をそろえやすくなります

## 基本ヘルプ

```bash
uv run harina-v4 --help
```

## receipt コマンド

ローカル画像を CLI-first の処理経路で確認できます。

```bash
uv run harina-v4 receipt process ./sample-receipt.jpg --skip-google-write
```

補足:

- `receipt process` は Discord bot と同じ Gemini 中心の処理パイプラインを使います
- `--skip-google-write` は `GEMINI_API_KEY` だけで抽出確認したいときに便利です
- 省略すると Drive へのアップロードと Sheets への追記まで行います

## bot コマンド

常時稼働の Discord bot を起動:

```bash
uv run harina-v4 bot run
```

## Google コマンド

初回 OAuth ログインを行い、refresh token を保存:

```bash
uv run harina-v4 google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
```

Drive フォルダと Spreadsheet を作成または再利用:

```bash
uv run harina-v4 google init-resources --env-file .env
```

## dataset コマンド

Discord 画像をデータセットへ保存:

```bash
uv run harina-v4 dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 50
```

ローカルデータセット画像で Gemini の簡易確認:

```bash
uv run harina-v4 dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

## Discord アップロードテスト

実際の画像を Discord に投稿して bot の返信まで確認:

```bash
uv run harina-v4 bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

補足:

- 指定チャンネルに実際のメッセージを投稿します
- `harina-v4 bot run` と同じパッケージロジックで処理します
- テストメッセージには `DISCORD_TEST_MESSAGE_PREFIX` が付き、既定値は `[HARINA-TEST]` です
- `DISCORD_TEST_CHANNEL_ID` を設定しておくと `--channel-id` を省略できます
- 実環境に触るので、安全なテストチャンネルで使うのがおすすめです

## おすすめ運用フロー

1. `harina-v4 receipt process --skip-google-write` でローカル抽出を確認する
2. `harina-v4 dataset download` で小さなサンプルを取得する
3. `harina-v4 dataset smoke-test` で 2 枚ほどの画像で抽出結果を確認する
4. 個人 Gmail 運用なら `harina-v4 google oauth-login` を先に通す
5. `harina-v4 google init-resources` で Drive / Sheets の保存先をそろえる
6. `harina-v4 bot upload-test` で Discord 上の動作確認をする
7. `harina-v4 bot run` で本番の常時稼働へ進む
