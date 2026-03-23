# リリースノート v4.4.0

[![GitHub Release](https://img.shields.io/badge/GitHub-v4.4.0-1E3A34?style=for-the-badge&logo=github)](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.4.0)
[![English Notes](https://img.shields.io/badge/English-v4.4.0-E68B2C?style=for-the-badge)](/guide/release-notes-v4.4.0)

![Harina Receipt Bot v4.4.0 リリースビジュアル](/brand/harina-hero-v4.4.0.svg)

このリリースは `v4.3.0` から `v4.4.0` までの変更をまとめたものです。

## 概要

- 年度別 `Analysis YYYY` と `Analysis All Years` を Google Sheets 上で再生成し、数式ベースで自動更新される分析ダッシュボードを追加
- 月次カテゴリ推移、支払者分析、支払者別カテゴリ内訳、各種グラフを追加して、家計簿レビューをスプレッドシート上で完結しやすく改善
- `重複確認` シートを追加し、チェックボックスで分析からの自動除外を制御できるように改善
- Drive watcher の待機中に `/resume_polling` で即時再開できる運用導線を追加
- `google sync-analysis` による明示的な分析再生成コマンドと、関連ドキュメントの truth-sync を実施

## ハイライト

### Google Sheets に分析ダッシュボードを追加

HARINA は raw の年度シートに直接集計を書き込むのではなく、`Analysis YYYY` と `Analysis All Years` を再生成してダッシュボードとして扱うようになりました。分析シートは数式とチャートで構成されるため、既存の年度シートに新しい行が追加されると、分析側も自動で再計算されます。

カテゴリ分析、店舗分析、月次推移、月次カテゴリ別支出、支払者分析などを同じシート上にまとめることで、月ごとの変化やカテゴリ偏りをすぐ確認できるようになりました。

### `google sync-analysis` で再生成を明示実行

新しい CLI コマンド `google sync-analysis` により、分析シートの再生成を必要なときに安全に実行できます。

```bash
uv run harina-v4 google sync-analysis
```

`--year` を繰り返して特定年度だけを対象にしたり、`--skip-all-years` で全年度シートを除外したりできるため、運用中のスプレッドシート修復や部分更新にも向いています。

### 支払者分析と重複確認を追加

`authorTag` ベースの支払者分析と、支払者ごとのカテゴリ内訳をダッシュボードに追加しました。これにより、誰がどのカテゴリにどれだけ使っているかを表とグラフの両方で確認できます。

さらに `重複確認` シートを追加し、重複候補を persistent に保持するようにしました。`自動除外` のチェックボックスをオンにすると、そのレシートは分析シートから除外され、オフに戻すと再び分析対象に復帰します。年度の raw シートそのものは変更しません。

### `/resume_polling` で watcher を即時再開

Drive watcher が通常の poll interval 待機中、または Gemini の長時間 retry wait 中でも、Discord の `/resume_polling` で即時再開できるようになりました。

待機が長いときでもコンテナ再起動なしで次のスキャンへ進めるため、運用の反応速度が上がります。

## ツールと運用

- `google sync-analysis` を CLI に追加
- 分析シート再生成後も状態が残る `重複確認` シートを追加
- ダッシュボード数式、チャート source、duplicate control、`/resume_polling` のテストを追加

## ドキュメントとアセット

- 既存の release hero を元に `v4.4.0` の header SVG を追加
- `v4.4.0` のリリースノートと解説記事を英日両方で追加
- docs のナビゲーション、docs home、README の最新 release リンクを更新
- CLI、Overview、Google Setup、Deployment の steady-state docs を release 内容に合わせて更新

## 検証

- `uv run pytest`
- `npm --prefix docs run docs:build`

## アップグレードメモ

- `重複確認` は新しい persistent シートです。チェック状態は分析結果にだけ影響し、年度別の raw データは変更しません。
- 取り込み時の `attachmentName` ベースの duplicate guard はそのまま残ります。今回の spreadsheet 側 duplicate control は ingestion を置き換えるものではありません。
- 既存年度シートへの行追加は自動反映されますが、HARINA 外で新しい年タブを作った場合は `uv run harina-v4 google sync-analysis` で全年度側の対象一覧を更新してください。

## 関連リンク

- [Harina v4.4.0 解説](/ja/guide/whats-new-v4.4.0)
- [Overview](/ja/guide/overview)
- [CLI](/ja/guide/cli)
- [Google Setup](/ja/guide/google-setup)
- [English release notes](/guide/release-notes-v4.4.0)
