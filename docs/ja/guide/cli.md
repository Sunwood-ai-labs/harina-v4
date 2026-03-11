# CLI

HARINA V4 は `harina` という Python CLI を中心に構成されています。

## CLI を使う理由

- bot 運用、移行、再スキャン、確認作業を 1 つのコマンド体系にまとめられる
- 常時稼働 bot と運用用コマンドで同じパッケージロジックを再利用できる
- ローカル実行、CI、将来の自動化を標準化しやすい

## 基本ヘルプ

```bash
uv run harina --help
```

## bot コマンド

常時稼働の Discord bot を起動:

```bash
uv run harina bot run
```

## Google コマンド

最初の 1 回だけ OAuth ログインを行い、refresh token を保存:

```bash
uv run harina google oauth-login --oauth-client-secret-file ./secrets/harina-oauth-client.json --env-file .env
```

Drive フォルダと Spreadsheet を作成または再利用:

```bash
uv run harina google init-resources --env-file .env
```

## dataset コマンド

Discord 画像をデータセットへ保存:

```bash
uv run harina dataset download "https://discord.com/channels/<guild_id>/<channel_id>" --limit 50
```

ローカルデータセット画像で Gemini を簡易確認:

```bash
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

## Discord アップロードテスト

実際の画像を Discord に投稿して bot の返信を待つ:

```bash
uv run harina bot upload-test --channel-id <channel_id> --image ./sample-receipt.jpg
```

補足:

- 指定チャンネルへ実際のメッセージを投稿します
- `harina bot run` と同じパッケージロジックで処理します
- テストメッセージには `DISCORD_TEST_MESSAGE_PREFIX` が付き、既定値は `[HARINA-TEST]` です
- `DISCORD_TEST_CHANNEL_ID` を設定しておけば `--channel-id` を省略できます
- Discord、Gemini、Drive、Sheets を触るので、安全なテスト用チャンネルで使うのがおすすめです

## おすすめ運用フロー

1. `harina dataset download` で小さなサンプルを取得する
2. `harina dataset smoke-test` で 2 枚程度の抽出結果を確認する
3. 個人 Gmail 環境なら `harina google oauth-login` を先に通す
4. `harina google init-resources` で Drive / Sheets の保存先を揃える
5. `harina bot upload-test` で Discord 上の実挙動を確認する
6. `harina bot run` で本番の常時稼働へ進む
