# デプロイ

## ローカル開発

```bash
uv sync
uv run pytest
uv run python -m app.main
```

## Docker Compose

1. `.env.example` を `.env` にコピー
2. Discord、Gemini、Drive、Sheets の値を設定
3. JSON キーファイルを使う場合は `./secrets` に配置
4. サービスを起動

```bash
docker compose up -d --build
docker compose logs -f
```

## 必須の環境変数

- `DISCORD_TOKEN`
- `GEMINI_API_KEY`
- `GOOGLE_DRIVE_FOLDER_ID`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON` または `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`

## 運用メモ

- `DISCORD_CHANNEL_IDS` を空にすると、読める全チャンネルを対象にします
- `DISCORD_CHANNEL_IDS` にカンマ区切りで ID を入れると対象を限定できます
- 起動時に対象シートのヘッダー行を自動作成します
- 必須設定が不足している場合は起動直後に失敗して、設定漏れに気づきやすいです
