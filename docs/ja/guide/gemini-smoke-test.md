# Gemini スモークテスト

`app.gemini_smoke_test` は、大きな移行や再スキャンの前に、ローカルのデータセット画像でレシート認識を数枚だけ確認したいときの CLI です。

## 向いている用途

- 設定した Gemini モデルが正しく応答するか確認したい
- プロンプトやスキーマ変更後に本番再実行の前に軽く確認したい
- V1、V2、V3 から取り出したデータセットを 2 枚程度で確認したい
- チーム共有用に軽量な検証結果を JSON として残したい

## 基本コマンド

```bash
uv run harina dataset smoke-test --limit 2
```

読み込む環境変数:

- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `DISCORD_DATASET_OUTPUT_DIR` を既定のデータセットルートとして使用

このリポジトリの既定モデルは `gemini-3-flash-preview` です。`GEMINI_MODEL` を変えれば別モデルの確認にも使えます。

## よく使う例

既定のデータセットから重複を除いて 2 枚確認:

```bash
uv run harina dataset smoke-test --limit 2
```

移行用フォルダを対象に確認:

```bash
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2
```

結果を JSON ファイルとして保存:

```bash
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2 --output ./artifacts/gemini-smoke-test.json
```

再投稿された同一画像もそのまま比較したい場合:

```bash
uv run harina dataset smoke-test --dataset-dir ./dataset/v3-backfill --limit 2 --allow-duplicates
```

## 出力の挙動

- データセット配下を再帰的に探索します
- 対応拡張子は `.jpg`、`.jpeg`、`.png`、`.webp`、`.gif`、`.heic`、`.heif` です
- `--allow-duplicates` を付けない場合、SHA-256 で同一画像を除外します
- 選ばれたファイル、ハッシュ、抽出結果を JSON で出力します
- `raw_text` は長すぎないように `raw_text_preview` に短縮して出します

## おすすめの確認フロー

1. まず `harina dataset download` で小さなサンプルを取得する
2. `harina dataset smoke-test --limit 2` を実行する
3. JSON 出力で店舗名、日付、合計金額、confidence を確認する
4. 問題なければ本番のバックフィルや再スキャンへ進む
