# Harina v4.3.0 解説

[![GitHub Release](https://img.shields.io/badge/GitHub-v4.3.0-1E3A34?style=for-the-badge&logo=github)](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.3.0)
[![Release Notes](https://img.shields.io/badge/Release%20Notes-v4.3.0-E68B2C?style=for-the-badge)](/ja/guide/release-notes-v4.3.0)
[![English Article](https://img.shields.io/badge/English-Article-D8E7E0?style=for-the-badge&logoColor=1E3A34)](/guide/whats-new-v4.3.0)

![Harina Receipt Bot v4.3.0 hero](/brand/harina-hero-v4.3.0.svg)

`v4.3.0` は新機能を大きく増やすよりも、日々のレシート運用を安全に、静かに、あとから追いやすくすることに重点を置いたリリースです。Discord、Google Drive、Google Sheets をまたぐ定常運用が、ひとつずつ素直になっています。

## このリリースが効く場面

- 重複レシートで二重書き込みが起きにくくなります。
- 年/月ベースの保存先整理で、あとから棚卸ししやすくなります。
- 本番運用と smoke/test の Gemini 設定を切り分けやすくなります。
- Drive watcher の長時間運用で、無変化サマリーの通知ノイズが減ります。

## 1. 重複に強い intake と明示的な再処理

HARINA は `attachmentName` を重複判定キーとして扱うようになり、Discord bot と Drive watcher の両方で意図しない再処理を抑えやすくなりました。Discord 側は `Receipt Skipped` を返し、Drive watcher 側は Discord 通知や Sheets 追記の前に重複を止めてから processed 側へ移動します。

一方で、意図的な再実行は `--rescan` で引き続き可能です。普段は安全に、必要なときだけ明示的にやり直せる形になりました。

## 2. 年ベースの台帳整理と `YYYY/MM` 保管

今回の更新では、日付ベースの整理が 2 か所で強化されています。

- レシート行は必要に応じて年別シートへ振り分け
- 元画像や watcher の processed ファイルは `YYYY/MM` へ整理

この組み合わせで、月ごとの見返しと年単位の台帳確認がかなりやりやすくなります。レシート件数が増えてきた運用ほど効く改善です。

## 3. Gemini 運用を本番と検証で分離

`v4.3.0` では Gemini の model selection を本番系と test 系で分離しました。bot や watcher は production 設定を使い、smoke 的な確認フローは別の test model 設定を使えます。

あわせて、常時稼働の bot / watcher フローではキー回転が尽きたときの待機付き再試行も入り、Gemini 呼び出しまわりの回復性が上がっています。さらに Drive watcher の receipt embed には使用モデル名と推定 API cost が出るため、品質とコストを同じ文脈で確認しやすくなりました。

## 4. watcher 常駐時の通知を静かに

Drive watcher は、変化のない idle cycle で `HARINA Scan Summary` を繰り返し投げなくなりました。処理成功、重複スキップ、失敗、backlog 変化がある cycle はこれまでどおり見えるので、必要な情報量は残しつつノイズだけを減らしています。

派手ではありませんが、長時間運用の体感をかなり良くする変更です。

## 運用者にとっての変化

- 重複レシートは `--rescan` を付けない限り早めに止まる前提になります。
- Drive watcher の保存先やアーカイブが時系列で追いやすくなります。
- smoke/test を本番 Gemini 設定から切り離しやすくなります。
- Drive watcher の receipt embed と watcher ログから、モデルやコストの確認がしやすくなります。

## 検証

- `uv run pytest`（`100 passed`）
- `npm --prefix docs run docs:build`

## 関連リンク

- [リリースノート v4.3.0](/ja/guide/release-notes-v4.3.0)
- [GitHub Release](https://github.com/Sunwood-ai-labs/harina-v4/releases/tag/v4.3.0)
- [CLI ガイド](/ja/guide/cli)
