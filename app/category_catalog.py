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
    ("野菜", "生鮮野菜、カット野菜、きのこ類"),
    ("果物", "生果物、カットフルーツ"),
    ("肉", "精肉、ハム、ソーセージ、ベーコン"),
    ("魚介", "鮮魚、刺身、干物、練り物"),
    ("乳卵", "牛乳、ヨーグルト、チーズ、卵"),
    ("主食", "米、麺、パン、シリアル"),
    ("惣菜", "弁当、総菜、サラダ、できあい食品"),
    ("菓子", "お菓子、アイス、デザート"),
    ("飲料", "水、お茶、コーヒー、ジュース、清涼飲料"),
    ("酒", "ビール、ワイン、日本酒、チューハイ"),
    ("調味料", "調味料、缶詰、乾麺、レトルト、乾物"),
    ("冷凍", "冷凍弁当、冷凍野菜、冷凍おかず"),
    ("日用品", "洗剤、ティッシュ、ゴミ袋などの生活用品"),
    ("キッチン", "ラップ、スポンジ、保存容器、調理小物"),
    ("衛生", "マスク、歯ブラシ、生理用品、消毒用品"),
    ("美容", "化粧品、スキンケア、ヘアケア"),
    ("医薬品", "市販薬、湿布、サプリメント"),
    ("ベビー", "おむつ、離乳食、介護消耗品"),
    ("ペット", "ペットフード、トイレ用品、おやつ"),
    ("文具", "ノート、ペン、本、雑誌"),
    ("衣料", "服、靴、下着、服飾小物"),
    ("家電", "電池、充電器、小型家電、周辺機器"),
    ("娯楽", "玩具、ホビー用品、ゲーム関連"),
    ("外食", "店内飲食、テイクアウト、カフェ利用"),
    ("交通", "切符、駐車場、タクシー、ガソリン"),
    ("手数料", "配送料、各種手数料、サービス料"),
]

DEFAULT_CATEGORY_DESCRIPTION_MAP = {name: description for name, description in DEFAULT_RECEIPT_CATEGORIES}

CATEGORY_NAME_ALIASES = {
    "野菜/きのこ": "野菜",
    "肉/加工肉": "肉",
    "魚介/海産": "魚介",
    "乳製品/卵": "乳卵",
    "主食/パン": "主食",
    "惣菜/弁当": "惣菜",
    "菓子/スイーツ": "菓子",
    "酒類": "酒",
    "調味料/乾物": "調味料",
    "冷凍食品": "冷凍",
    "キッチン用品": "キッチン",
    "衛生用品": "衛生",
    "美容/コスメ": "美容",
    "ベビー/介護": "ベビー",
    "ペット用品": "ペット",
    "文房具/書籍": "文具",
    "衣料品": "衣料",
    "家電/ガジェット": "家電",
    "趣味/娯楽": "娯楽",
    "交通/移動": "交通",
    "送料/手数料": "手数料",
}


def build_default_category_rows(*, timestamp: str) -> list[list[str]]:
    return [
        [name, description, "TRUE", timestamp, timestamp, "seed"]
        for name, description in DEFAULT_RECEIPT_CATEGORIES
    ]


def normalize_category_name(value: str) -> str:
    normalized_value = " ".join(value.strip().split())
    normalized_value = normalized_value.replace("・", "/")
    return CATEGORY_NAME_ALIASES.get(normalized_value, normalized_value)


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
