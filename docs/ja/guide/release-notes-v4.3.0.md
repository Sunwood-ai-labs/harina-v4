# リリースノート: v4.3.0

[![GitHub Release](https://img.shields.io/badge/GitHub-v4.3.0-1E3A34?style=for-the-badge&logo=github)](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.3.0)
[![English Notes](https://img.shields.io/badge/English-v4.3.0-E68B2C?style=for-the-badge)](/guide/release-notes-v4.3.0)

![Harina Receipt Bot v4.3.0 hero](/brand/harina-hero-v4.3.0.svg)

2026年3月19日 JST 公開。`v4.2.0` から `v4.3.0` の変更をまとめたリリースノートです。

## 概要

- 受信レシートの重複排除と年別シート振り分けを明確化し、再処理と重複スキップの挙動を安定化
- 受信画像および Drive 処理済みファイルを年/月フォルダに整理
- 本番処理とテスト処理で Gemini モデルを分離し、運用と検証の切り分けを改善
- Gemini キー回転時の再試行を遅延付きで補完し、ボット側の耐障害性を向上
- Drive watcher の「変化なし」通知を抑制し、重要イベントのみ要約投稿
- Drive レシートの埋め込みにモデル名と推定コスト情報を追加
- Drive ルーティング、OAuth 復旧、Compose 再起動運用を docs 側で更新

## 主な変更

### 受信の安全性改善

`attachmentName` を重複判定キーとして扱い、Discord 受信と Drive watcher 両方で重複を抑制しやすくしました。必要な場合は明示的に再実行できるフローを維持しつつ、意図しない二重書き込みを避けられます。

### 年月ルーティングによる保管整理

受信画像の保存先と Drive watcher の処理済み配下は `YYYY/MM` で整理するように更新しました。運用時のフォルダ肥大化を抑え、日付ベースの棚卸しをしやすくします。

### モデル分離と耐障害性

本番フローとテスト/検証フローの Gemini 利用モデルを分離し、Drive/Discord の実運用を止めずに検証フローを回しやすくしました。加えて、キー回転枠の枯渇時は遅延付き再試行を行い、一時的な失敗時の回復性を上げています。

### 通知ノイズの抑制

Drive watcher サマリーは、進捗の変化がない idle サイクルを繰り返し投稿しないようになりました。処理が発生した場合や backlog 変化があった場合、失敗時は従来どおり投稿が残るため、監視しやすい粒度を保っています。

### 処理透明性の向上

Drive 受領後の埋め込みに、利用モデルと推定コスト情報を表示するようになり、運用時の原因調査やコスト観点の確認を行いやすくなります。

## v4.3.0 に含まれる内容

### 挙動面

- 重複判定は `attachmentName` ベースで一貫性が上がり、意図しない二重書き込みを抑止
- 受信画像と Drive 処理済みファイルの保存先が年/月ベースへ整理
- Drive watcher の要約は「変化がない要約」だけを静黙化（処理あり/失敗ありイベントは維持）
- Drive レシート埋め込みにモデル名・推定コスト情報を付与

### 運用と更新

- 既存コマンド運用の範囲で、重複排除・年月別ルーティング・静黙化サマリーが適用されます
- docs 側で次の内容を更新:
  - Drive watcher のルート先とフォルダ整理
  - OAuth リカバリと Compose 再作成運用
  - 長時間運用時の前提説明

## 検証

- `uv run pytest`（`100 passed`）
- `npm --prefix docs run docs:build`

## 参照

- [概要](/ja/guide/overview)
- [CLI](/ja/guide/cli)
- [Google 設定](/ja/guide/google-setup)
- [English release notes](/guide/release-notes-v4.3.0)
