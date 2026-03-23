# Harina v4.4.0 解説

[![GitHub Release](https://img.shields.io/badge/GitHub-v4.4.0-1E3A34?style=for-the-badge&logo=github)](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.4.0)
[![Release Notes](https://img.shields.io/badge/Release%20Notes-v4.4.0-E68B2C?style=for-the-badge)](/ja/guide/release-notes-v4.4.0)
[![English Article](https://img.shields.io/badge/English-Article-D8E7E0?style=for-the-badge&logoColor=1E3A34)](/guide/whats-new-v4.4.0)

![Harina Receipt Bot v4.4.0 リリースビジュアル](/brand/harina-hero-v4.4.0.svg)

`v4.4.0` は、HARINA の Google Sheets 運用を「ただの追記先」から「分析と重複確認までできるダッシュボード」に引き上げるリリースです。あわせて、Discord から Drive watcher の待機を解除できるようになり、運用中の復旧も速くなりました。

## このリリースが重要な理由

- raw の年度シートを触らずに、分析ダッシュボードで月次傾向やカテゴリ偏りを見られるようになった
- `重複確認` のチェックボックスで、重複候補を分析から自動除外できるようになった
- `/resume_polling` により、watcher の長い待機を Discord からすぐ解除できるようになった
- `google sync-analysis` により、分析シートの再生成と修復を CLI から明示実行できるようになった

## 1. Google Sheets が分析ダッシュボードになる

HARINA は `Analysis YYYY` と `Analysis All Years` を再生成し、カテゴリ分析、店舗分析、月次推移、支払者分析、カテゴリ別月次などを 1 枚のダッシュボードとして並べるようになりました。

しかも値の直打ちではなく数式ベースなので、既存年度シートにレシート行が追加されると、分析シート側も自動で追従します。raw データは raw のまま残し、分析だけを再構築できる構成です。

## 2. `google sync-analysis` で必要なときに再生成

分析シートは通常の append フローでも更新されますが、運用中には「この年だけ作り直したい」「全年度だけ更新したい」といった場面があります。

そのために `google sync-analysis` が追加されました。

```bash
uv run harina-v4 google sync-analysis
```

`--year 2025` のように年度を絞ることもできるので、スプレッドシートの修復や再計算のやり直しがかなり扱いやすくなっています。

## 3. 支払者分析と重複確認

今回のダッシュボードは、カテゴリ別・店舗別だけでなく、`authorTag` を使った支払者分析もできるようになりました。誰がどれだけ払っているか、どのカテゴリに使っているかを表とグラフの両方で確認できます。

さらに `重複確認` シートが追加され、重複候補を persistent に保持します。ここで `自動除外` をオンにしたレシートは分析から外れ、オフにすれば復帰します。年度シート本体を直接消したり編集したりしないので、安全に判断できます。

## 4. `/resume_polling` で watcher を止めっぱなしにしない

Gemini の長時間 retry wait や通常の poll interval 待機中に、Drive watcher を今すぐ動かしたい場面は珍しくありません。

`/resume_polling` はそのための運用コマンドです。Discord から待機を解除して次のスキャンを早められるので、コンテナを再起動するより軽く、運用としても扱いやすくなりました。

## オペレーター視点で何が変わるか

- スプレッドシートに `Analysis ...` と `重複確認` が追加される
- 既存年度シートへの行追加は、分析シートへ自動で反映される
- HARINA 外で新しい年タブを作った場合は `google sync-analysis` で再生成する
- watcher の長い待機は `/resume_polling` で解除するのが最短になる

## 検証

- `uv run pytest`
- `npm --prefix docs run docs:build`

## 関連リンク

- [リリースノート v4.4.0](/ja/guide/release-notes-v4.4.0)
- [GitHub Release](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.4.0)
- [CLI ガイド](/ja/guide/cli)
