# リリースノート: v4.2.0

[![GitHub Release](https://img.shields.io/badge/GitHub-v4.2.0-1E3A34?style=for-the-badge&logo=github)](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.2.0)
[![English Notes](https://img.shields.io/badge/English-v4.2.0-E68B2C?style=for-the-badge)](/guide/release-notes-v4.2.0)

2026年3月15日 JST 公開。`v4.1.0` から `v4.2.0` までに出荷された変更をまとめたページです。

## 概要

- チーム別の Google Drive intake ルーティングと、Discord / Drive の一括セットアップを追加
- Gemini のレシート抽出と商品カテゴリ付与を分離し、Google Sheets とカテゴリ同期
- Discord の結果表示にカテゴリ要約、商品カテゴリ、Drive / Sheets 直リンクを追加
- Discord デバッグ機能と Gemini の再試行処理を強化
- `docs/public/test` を使う検証フローと、英日ドキュメントを更新

## 主な変更

### チーム別 intake ルーティング

`setup team-intake` により、HARINA 用 Discord カテゴリ、メンバーごとのチャンネル、対応する Drive の inbox / processed フォルダを 1 回で作れるようになりました。Drive watcher も `DRIVE_WATCH_ROUTES_JSON` を使って、各 Drive 受付ルートを対応する Discord チャンネルへ振り分けられます。

### 段階的カテゴリ付与と Sheets 同期

Gemini 処理は、まずレシート抽出、その後に商品ごとのカテゴリ付与という 2 段階になりました。HARINA は `Categories` シートを維持し、カテゴリ名の正規化、初期値投入、Gemini が提案した新カテゴリの追記まで行います。

### Discord 上の運用体験改善

レシート返信の埋め込みに、カテゴリ集計、商品カテゴリ一覧、明細プレビューが表示されるようになりました。Drive と Sheets の URL がある場合は、そこへ直接飛べるリンクボタンも付与されます。

### デバッグ性と耐障害性の向上

`bot collect-logs` は Discord チャンネル履歴、スレッド、埋め込み、添付、コンポーネント情報を `logs/discord` に保存できるため、障害調査がしやすくなりました。Gemini 呼び出しは一時障害を再試行し、quota やサービス問題が起きた場合は `GEMINI_API_KEY_ROTATION_LIST` のキーへ切り替えられます。

### 検証フローと docs の更新

`test docs-public` で `docs/public/test` のサンプルレシートを CLI 経路、Discord 経路、または両方で確認できます。Drive watcher と段階的カテゴリ付与を含めた最新フローが、英日両方の docs とアーキテクチャ図に反映されました。

## v4.2.0 に含まれるもの

### 新規または拡張されたコマンド

- `uv run harina-v4 setup team-intake --guild-id ... --member ...`
- `uv run harina-v4 google init-drive-watch --env-file .env`
- `uv run harina-v4 google oauth-start`
- `uv run harina-v4 google oauth-finish`
- `uv run harina-v4 bot collect-logs <discord-url>`
- `uv run harina-v4 test docs-public`

### ユーザーから見える振る舞い

- `Receipts` には商品ごとの 1 行を書き込むようになりました
- `itemCategory` が Sheets 出力に含まれるようになりました
- Drive watcher 通知は、受付投稿のあとに可能ならスレッドで処理結果を返します
- 成功した Discord 返信には Google Drive / Google Sheets への直リンクが付くことがあります
- カテゴリ名は `野菜`、`惣菜`、`飲料` のような短い名前へ正規化されます

## 検証

- `uv run pytest` (`67 passed`)
- `npm --prefix docs run docs:build`

## 関連ページ

- [概要](/ja/guide/overview)
- [CLI](/ja/guide/cli)
- [Google セットアップ](/ja/guide/google-setup)
- [English release notes](/guide/release-notes-v4.2.0)
