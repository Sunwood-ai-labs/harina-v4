from __future__ import annotations

from collections.abc import Iterable


CATEGORY_SHEET_HEADERS = [
    "categoryName",
    "description",
    "isActive",
    "createdAt",
    "updatedAt",
    "source",
]

DEFAULT_RECEIPT_CATEGORIES: list[tuple[str, str]] = [
    ("野菜・きのこ", "生鮮野菜、カット野菜、きのこ類"),
    ("果物", "生果物、カットフルーツ"),
    ("肉・加工肉", "精肉、ハム、ソーセージ、ベーコン"),
    ("魚介・海産", "鮮魚、刺身、干物、練り物"),
    ("乳製品・卵", "牛乳、ヨーグルト、チーズ、卵"),
    ("主食・パン", "米、麺、パン、シリアル"),
    ("惣菜・弁当", "弁当、総菜、サラダ、できあい食品"),
    ("菓子・スイーツ", "お菓子、アイス、デザート"),
    ("飲料", "水、お茶、コーヒー、ジュース、清涼飲料"),
    ("酒類", "ビール、ワイン、日本酒、チューハイ"),
    ("調味料・乾物", "調味料、缶詰、乾麺、レトルト、乾物"),
    ("冷凍食品", "冷凍弁当、冷凍野菜、冷凍おかず"),
    ("日用品", "洗剤、ティッシュ、ゴミ袋などの生活用品"),
    ("キッチン用品", "ラップ、スポンジ、保存容器、調理小物"),
    ("衛生用品", "マスク、歯ブラシ、生理用品、消毒用品"),
    ("美容・コスメ", "化粧品、スキンケア、ヘアケア"),
    ("医薬品", "市販薬、湿布、サプリメント"),
    ("ベビー・介護", "おむつ、離乳食、介護消耗品"),
    ("ペット用品", "ペットフード、トイレ用品、おやつ"),
    ("文房具・書籍", "ノート、ペン、本、雑誌"),
    ("衣料品", "服、靴、下着、服飾小物"),
    ("家電・ガジェット", "電池、充電器、小型家電、周辺機器"),
    ("趣味・娯楽", "玩具、ホビー用品、ゲーム関連"),
    ("外食", "店内飲食、テイクアウト、カフェ利用"),
    ("交通・移動", "切符、駐車場、タクシー、ガソリン"),
    ("送料・手数料", "配送料、各種手数料、サービス料"),
]


def build_default_category_rows(*, timestamp: str) -> list[list[str]]:
    return [
        [name, description, "TRUE", timestamp, timestamp, "seed"]
        for name, description in DEFAULT_RECEIPT_CATEGORIES
    ]


def normalize_category_name(value: str) -> str:
    return " ".join(value.strip().split())


def dedupe_category_names(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        normalized_value = normalize_category_name(raw_value)
        if not normalized_value:
            continue
        key = normalized_value.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized_value)
    return deduped
