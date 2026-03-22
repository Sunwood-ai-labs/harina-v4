from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from dataclasses import dataclass
import re
import time
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaInMemoryUpload

from app.category_catalog import (
    CATEGORY_SHEET_HEADERS,
    DEFAULT_CATEGORY_DESCRIPTION_MAP,
    build_default_category_rows,
    dedupe_category_names,
    normalize_category_name,
)
from app.formatters import RECEIPT_SHEET_HEADERS


def _column_letter(column_number: int) -> str:
    letters: list[str] = []
    current = column_number
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def _hex_color_style(hex_code: str) -> dict[str, dict[str, float]]:
    normalized = hex_code.removeprefix("#")
    if len(normalized) != 6:
        raise ValueError(f"Expected 6-digit hex color, got: {hex_code}")
    return {
        "rgbColor": {
            "red": int(normalized[0:2], 16) / 255,
            "green": int(normalized[2:4], 16) / 255,
            "blue": int(normalized[4:6], 16) / 255,
        }
    }


def _sheet_range(
    *,
    sheet_id: int,
    start_row_index: int,
    end_row_index: int,
    start_column_index: int,
    end_column_index: int,
) -> dict[str, int]:
    return {
        "sheetId": sheet_id,
        "startRowIndex": start_row_index,
        "endRowIndex": end_row_index,
        "startColumnIndex": start_column_index,
        "endColumnIndex": end_column_index,
    }


def _border_style(style: str, hex_code: str) -> dict[str, object]:
    return {
        "style": style,
        "colorStyle": _hex_color_style(hex_code),
    }


def _build_analysis_merge_request(
    *,
    sheet_id: int,
    start_row_index: int,
    end_row_index: int,
    start_column_index: int,
    end_column_index: int,
) -> dict[str, object]:
    return {
        "mergeCells": {
            "range": _sheet_range(
                sheet_id=sheet_id,
                start_row_index=start_row_index,
                end_row_index=end_row_index,
                start_column_index=start_column_index,
                end_column_index=end_column_index,
            ),
            "mergeType": "MERGE_ALL",
        }
    }


def _build_analysis_repeat_cell_request(
    *,
    sheet_id: int,
    start_row_index: int,
    end_row_index: int,
    start_column_index: int,
    end_column_index: int,
    user_entered_format: dict[str, object],
    fields: str,
) -> dict[str, object]:
    return {
        "repeatCell": {
            "range": _sheet_range(
                sheet_id=sheet_id,
                start_row_index=start_row_index,
                end_row_index=end_row_index,
                start_column_index=start_column_index,
                end_column_index=end_column_index,
            ),
            "cell": {"userEnteredFormat": user_entered_format},
            "fields": fields,
        }
    }


def _build_analysis_dimension_request(
    *,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
    pixel_size: int | None = None,
    hidden_by_user: bool | None = None,
) -> dict[str, object]:
    properties: dict[str, object] = {}
    fields: list[str] = []
    if pixel_size is not None:
        properties["pixelSize"] = pixel_size
        fields.append("pixelSize")
    if hidden_by_user is not None:
        properties["hiddenByUser"] = hidden_by_user
        fields.append("hiddenByUser")
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": dimension,
                "startIndex": start_index,
                "endIndex": end_index,
            },
            "properties": properties,
            "fields": ",".join(fields),
        }
    }


def _build_analysis_outlined_range_request(
    *,
    sheet_id: int,
    start_row_index: int,
    end_row_index: int,
    start_column_index: int,
    end_column_index: int,
    color: str | None = None,
    style: str = "SOLID_MEDIUM",
) -> dict[str, object]:
    border = _border_style(style, color or ANALYSIS_THEME_BORDER)
    return {
        "updateBorders": {
            "range": _sheet_range(
                sheet_id=sheet_id,
                start_row_index=start_row_index,
                end_row_index=end_row_index,
                start_column_index=start_column_index,
                end_column_index=end_column_index,
            ),
            "top": border,
            "bottom": border,
            "left": border,
            "right": border,
        }
    }


RECEIPT_PROCESSED_AT_INDEX = RECEIPT_SHEET_HEADERS.index("processedAt")
RECEIPT_PURCHASE_DATE_INDEX = RECEIPT_SHEET_HEADERS.index("purchaseDate")
RECEIPT_ATTACHMENT_NAME_COLUMN = chr(ord("A") + RECEIPT_SHEET_HEADERS.index("attachmentName"))
RECEIPT_TOTAL_INDEX = RECEIPT_SHEET_HEADERS.index("total")
YEAR_PATTERN = re.compile(r"(?<!\d)((?:19|20|21)\d{2})(?!\d)")
YEAR_MONTH_PATTERN = re.compile(r"(?<!\d)((?:19|20|21)\d{2})\D{0,3}(1[0-2]|0?[1-9])(?!\d)")
GOOGLE_DRIVE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
ANALYSIS_SHEET_PREFIX = "Analysis "
ANALYSIS_ALL_YEARS_SHEET_NAME = "Analysis All Years"
RECEIPT_LAST_COLUMN = _column_letter(len(RECEIPT_SHEET_HEADERS))
ANALYSIS_CATEGORY_MONTH_COLUMN_COUNT = 12
ANALYSIS_CATEGORY_TOTAL_COLUMN_INDEX = 15  # O
ANALYSIS_CATEGORY_LINE_ITEMS_COLUMN_INDEX = 16  # P
ANALYSIS_CATEGORY_RECEIPTS_COLUMN_INDEX = 17  # Q
ANALYSIS_CATEGORY_STATUS_COLUMN_INDEX = 18  # R
ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX = 20  # T
ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX = 26  # Z
ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX = 1  # A
ANALYSIS_MONTHLY_CATEGORY_TIMELINE_TITLE_ROW_NUMBER = 54
ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER = 55
ANALYSIS_VISIBLE_COLUMN_COUNT = 29  # AC base visible width before the timeline matrix
ANALYSIS_HELPER_SOURCE_COLUMN_INDEX = 100  # CV
ANALYSIS_HELPER_SOURCE_END_COLUMN_INDEX = ANALYSIS_HELPER_SOURCE_COLUMN_INDEX + len(RECEIPT_SHEET_HEADERS) - 1  # BI
ANALYSIS_HELPER_LATEST_RECEIPTS_COLUMN_INDEX = ANALYSIS_HELPER_SOURCE_END_COLUMN_INDEX + 2
ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_COLUMN_INDEX = ANALYSIS_HELPER_LATEST_RECEIPTS_COLUMN_INDEX + 7
ANALYSIS_HELPER_RECEIPT_TOTALS_COLUMN_INDEX = ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_COLUMN_INDEX + 5
ANALYSIS_HELPER_CATEGORY_REFERENCE_COLUMN_INDEX = ANALYSIS_HELPER_RECEIPT_TOTALS_COLUMN_INDEX + 5
ANALYSIS_HELPER_CATEGORY_ROLLUP_COLUMN_INDEX = ANALYSIS_HELPER_CATEGORY_REFERENCE_COLUMN_INDEX + 3
ANALYSIS_HELPER_MONTH_REFERENCE_COLUMN_INDEX = ANALYSIS_HELPER_CATEGORY_ROLLUP_COLUMN_INDEX + 5
ANALYSIS_HELPER_MONTH_ROLLUP_COLUMN_INDEX = ANALYSIS_HELPER_MONTH_REFERENCE_COLUMN_INDEX + 2
ANALYSIS_HELPER_RECEIPT_MONTH_LOOKUP_COLUMN_INDEX = 256  # IV
ANALYSIS_HELPER_ITEM_MONTHS_COLUMN_INDEX = 258  # IX
ANALYSIS_MAX_COLUMN_INDEX = 260  # IZ
ANALYSIS_HIDDEN_START_COLUMN_INDEX = ANALYSIS_HELPER_SOURCE_COLUMN_INDEX - 1  # hide helper columns from CV onward
ANALYSIS_HELPER_SOURCE_START_COLUMN = _column_letter(ANALYSIS_HELPER_SOURCE_COLUMN_INDEX)
ANALYSIS_HELPER_SOURCE_END_COLUMN = _column_letter(ANALYSIS_HELPER_SOURCE_END_COLUMN_INDEX)
ANALYSIS_HELPER_LATEST_RECEIPTS_START_COLUMN = _column_letter(ANALYSIS_HELPER_LATEST_RECEIPTS_COLUMN_INDEX)
ANALYSIS_HELPER_LATEST_RECEIPTS_END_COLUMN = _column_letter(ANALYSIS_HELPER_LATEST_RECEIPTS_COLUMN_INDEX + 5)
ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_START_COLUMN = _column_letter(ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_COLUMN_INDEX)
ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_END_COLUMN = _column_letter(ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_COLUMN_INDEX + 3)
ANALYSIS_HELPER_RECEIPT_TOTALS_START_COLUMN = _column_letter(ANALYSIS_HELPER_RECEIPT_TOTALS_COLUMN_INDEX)
ANALYSIS_HELPER_RECEIPT_TOTALS_END_COLUMN = _column_letter(ANALYSIS_HELPER_RECEIPT_TOTALS_COLUMN_INDEX + 3)
ANALYSIS_HELPER_CATEGORY_REFERENCE_START_COLUMN = _column_letter(ANALYSIS_HELPER_CATEGORY_REFERENCE_COLUMN_INDEX)
ANALYSIS_HELPER_CATEGORY_REFERENCE_END_COLUMN = _column_letter(ANALYSIS_HELPER_CATEGORY_REFERENCE_COLUMN_INDEX + 1)
ANALYSIS_HELPER_CATEGORY_ROLLUP_START_COLUMN = _column_letter(ANALYSIS_HELPER_CATEGORY_ROLLUP_COLUMN_INDEX)
ANALYSIS_HELPER_CATEGORY_ROLLUP_END_COLUMN = _column_letter(ANALYSIS_HELPER_CATEGORY_ROLLUP_COLUMN_INDEX + 3)
ANALYSIS_HELPER_MONTH_REFERENCE_START_COLUMN = _column_letter(ANALYSIS_HELPER_MONTH_REFERENCE_COLUMN_INDEX)
ANALYSIS_HELPER_MONTH_ROLLUP_START_COLUMN = _column_letter(ANALYSIS_HELPER_MONTH_ROLLUP_COLUMN_INDEX)
ANALYSIS_HELPER_MONTH_ROLLUP_END_COLUMN = _column_letter(ANALYSIS_HELPER_MONTH_ROLLUP_COLUMN_INDEX + 4)
ANALYSIS_HELPER_RECEIPT_MONTH_LOOKUP_START_COLUMN = _column_letter(ANALYSIS_HELPER_RECEIPT_MONTH_LOOKUP_COLUMN_INDEX)
ANALYSIS_HELPER_RECEIPT_MONTH_LOOKUP_END_COLUMN = _column_letter(ANALYSIS_HELPER_RECEIPT_MONTH_LOOKUP_COLUMN_INDEX + 1)
ANALYSIS_HELPER_ITEM_MONTHS_START_COLUMN = _column_letter(ANALYSIS_HELPER_ITEM_MONTHS_COLUMN_INDEX)
ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_COLUMN = _column_letter(ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX)
ANALYSIS_THEME_INK = "#1D2A24"
ANALYSIS_THEME_FOREST = "#234437"
ANALYSIS_THEME_MOSS = "#456A58"
ANALYSIS_THEME_PARCHMENT = "#F7F1E3"
ANALYSIS_THEME_SAND = "#E9DFC8"
ANALYSIS_THEME_SAGE = "#D8E4D8"
ANALYSIS_THEME_TEAL_MIST = "#D9E8E5"
ANALYSIS_THEME_SKY_MIST = "#DCE8F1"
ANALYSIS_THEME_NAVY = "#3C5A6B"
ANALYSIS_THEME_NAVY_MIST = "#D9E2EA"
ANALYSIS_THEME_TERRACOTTA = "#C86D4A"
ANALYSIS_THEME_TERRACOTTA_MIST = "#F2DED5"
ANALYSIS_THEME_AMBER = "#C9942F"
ANALYSIS_THEME_AMBER_MIST = "#F3E5C4"
ANALYSIS_THEME_IVORY = "#FFFDF8"
ANALYSIS_THEME_SLATE = "#6A756F"
ANALYSIS_THEME_BORDER = "#C9B89B"
ANALYSIS_DASHBOARD_TITLE = "HARINA 分析ダッシュボード"
ANALYSIS_DASHBOARD_SUBTITLE = "カテゴリ・店舗・月次のリズムを、一枚で眺めるレシートビュー"
ANALYSIS_SCOPE_LABEL = "対象範囲"
ANALYSIS_SCOPE_ALL_YEARS_LABEL = "全年度"
ANALYSIS_SOURCE_SHEETS_LABEL = "対象シート"
ANALYSIS_GENERATED_AT_LABEL = "更新日時"
ANALYSIS_UNIQUE_RECEIPTS_LABEL = "レシート数"
ANALYSIS_RECEIPT_TOTAL_LABEL = "レシート合計"
ANALYSIS_AVERAGE_RECEIPT_LABEL = "平均レシート額"
ANALYSIS_UNIQUE_MERCHANTS_LABEL = "店舗数"
ANALYSIS_LINE_ITEM_ROWS_LABEL = "明細行数"
ANALYSIS_DATE_RANGE_LABEL = "対象期間"
ANALYSIS_CATEGORY_SECTION_LABEL = "カテゴリ分析"
ANALYSIS_MERCHANT_SECTION_LABEL = "店舗分析"
ANALYSIS_MONTHLY_SECTION_LABEL = "月次推移"
ANALYSIS_TREND_SECTION_LABEL = "カテゴリ別月次"
ANALYSIS_CATEGORY_HEADER_LABEL = "カテゴリ"
ANALYSIS_DESCRIPTION_HEADER_LABEL = "説明"
ANALYSIS_TOTAL_AMOUNT_HEADER_LABEL = "合計金額"
ANALYSIS_LINE_ITEMS_HEADER_LABEL = "明細数"
ANALYSIS_RECEIPTS_HEADER_LABEL = "レシート数"
ANALYSIS_STATUS_HEADER_LABEL = "利用状況"
ANALYSIS_MERCHANT_HEADER_LABEL = "店舗"
ANALYSIS_RECEIPT_COUNT_HEADER_LABEL = "件数"
ANALYSIS_MONTH_HEADER_LABEL = "年月"
ANALYSIS_AVG_RECEIPT_HEADER_LABEL = "平均レシート額"
ANALYSIS_MERCHANTS_HEADER_LABEL = "店舗数"
ANALYSIS_MONTHLY_TOTAL_TREND_HEADER_LABEL = "月次合計推移"
ANALYSIS_USED_LABEL = "使用中"
ANALYSIS_UNUSED_LABEL = "未使用"
ANALYSIS_NO_CATEGORY_DATA_LABEL = "(カテゴリデータなし)"
ANALYSIS_NO_MERCHANT_DATA_LABEL = "(店舗データなし)"
ANALYSIS_NO_MONTH_DATA_LABEL = "(月次データなし)"
ANALYSIS_UNCATEGORIZED_LABEL = "(未分類)"
ANALYSIS_UNKNOWN_MERCHANT_LABEL = "(不明)"
ANALYSIS_NONE_LABEL = "(なし)"
ANALYSIS_CATEGORY_CHART_TITLE = "カテゴリ別支出"
ANALYSIS_MERCHANT_CHART_TITLE = "店舗別支出"
ANALYSIS_MONTHLY_CHART_TITLE = "月次支出推移"
ANALYSIS_CATEGORY_TIMELINE_CHART_TITLE = "月次カテゴリ別支出"
ANALYSIS_CHART_SERIES_PALETTE = [
    ANALYSIS_THEME_FOREST,
    ANALYSIS_THEME_TERRACOTTA,
    ANALYSIS_THEME_NAVY,
    ANALYSIS_THEME_AMBER,
    ANALYSIS_THEME_MOSS,
]


def _resolved_analysis_visible_column_count(*, category_timeline_column_count: int) -> int:
    return max(
        ANALYSIS_VISIBLE_COLUMN_COUNT,
        max(category_timeline_column_count, 2),
    )


def _resolved_analysis_hidden_start_column_index(*, category_timeline_column_count: int) -> int:
    del category_timeline_column_count
    return ANALYSIS_HIDDEN_START_COLUMN_INDEX


def _build_analysis_dashboard_layout_requests(
    *,
    sheet_id: int,
    category_timeline_column_count: int,
    category_timeline_row_count: int,
) -> list[dict[str, object]]:
    visible_column_count = _resolved_analysis_visible_column_count(
        category_timeline_column_count=category_timeline_column_count
    )
    hidden_start_column_index = _resolved_analysis_hidden_start_column_index(
        category_timeline_column_count=category_timeline_column_count
    )
    timeline_end_column_index = hidden_start_column_index
    requests: list[dict[str, object]] = [
        _build_analysis_merge_request(
            sheet_id=sheet_id,
            start_row_index=0,
            end_row_index=1,
            start_column_index=0,
            end_column_index=visible_column_count,
        ),
        _build_analysis_merge_request(
            sheet_id=sheet_id,
            start_row_index=1,
            end_row_index=2,
            start_column_index=1,
            end_column_index=3,
        ),
        _build_analysis_merge_request(
            sheet_id=sheet_id,
            start_row_index=1,
            end_row_index=2,
            start_column_index=5,
            end_column_index=12,
        ),
        _build_analysis_merge_request(
            sheet_id=sheet_id,
            start_row_index=1,
            end_row_index=2,
            start_column_index=14,
            end_column_index=17,
        ),
        _build_analysis_merge_request(
            sheet_id=sheet_id,
            start_row_index=2,
            end_row_index=3,
            start_column_index=0,
            end_column_index=visible_column_count,
        ),
        _build_analysis_merge_request(
            sheet_id=sheet_id,
            start_row_index=6,
            end_row_index=7,
            start_column_index=0,
            end_column_index=4,
        ),
        _build_analysis_merge_request(
            sheet_id=sheet_id,
            start_row_index=6,
            end_row_index=7,
            start_column_index=4,
            end_column_index=visible_column_count,
        ),
        _build_analysis_repeat_cell_request(
            sheet_id=sheet_id,
            start_row_index=0,
            end_row_index=200,
            start_column_index=0,
            end_column_index=visible_column_count,
            user_entered_format={
                "backgroundColorStyle": _hex_color_style(ANALYSIS_THEME_PARCHMENT),
                "textFormat": {"foregroundColorStyle": _hex_color_style(ANALYSIS_THEME_INK)},
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
            },
            fields="userEnteredFormat(backgroundColorStyle,textFormat,verticalAlignment,wrapStrategy)",
        ),
        _build_analysis_repeat_cell_request(
            sheet_id=sheet_id,
            start_row_index=0,
            end_row_index=1,
            start_column_index=0,
            end_column_index=visible_column_count,
            user_entered_format={
                "backgroundColorStyle": _hex_color_style(ANALYSIS_THEME_FOREST),
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "textFormat": {
                    "foregroundColorStyle": _hex_color_style(ANALYSIS_THEME_IVORY),
                    "fontSize": 20,
                    "bold": True,
                    "fontFamily": "Georgia",
                },
            },
            fields="userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment)",
        ),
        _build_analysis_repeat_cell_request(
            sheet_id=sheet_id,
            start_row_index=2,
            end_row_index=3,
            start_column_index=0,
            end_column_index=visible_column_count,
            user_entered_format={
                "backgroundColorStyle": _hex_color_style(ANALYSIS_THEME_PARCHMENT),
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "textFormat": {
                    "foregroundColorStyle": _hex_color_style(ANALYSIS_THEME_SLATE),
                    "fontSize": 11,
                    "italic": True,
                },
            },
            fields="userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment)",
        ),
        _build_analysis_repeat_cell_request(
            sheet_id=sheet_id,
            start_row_index=3,
            end_row_index=4,
            start_column_index=0,
            end_column_index=visible_column_count,
            user_entered_format={
                "backgroundColorStyle": _hex_color_style(ANALYSIS_THEME_PARCHMENT),
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "textFormat": {
                    "foregroundColorStyle": _hex_color_style(ANALYSIS_THEME_MOSS),
                    "fontSize": 9,
                    "bold": True,
                },
            },
            fields="userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment)",
        ),
    ]

    for start_column in (0, 4, 8, 12, 16):
        requests.append(
            _build_analysis_merge_request(
                sheet_id=sheet_id,
                start_row_index=4,
                end_row_index=6,
                start_column_index=start_column,
                end_column_index=start_column + 4,
            )
        )

    for start_column, end_column in (
        (0, ANALYSIS_CATEGORY_STATUS_COLUMN_INDEX),
        (ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX - 1, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 4),
        (ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX - 1, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 2),
    ):
        requests.append(
            _build_analysis_merge_request(
                sheet_id=sheet_id,
                start_row_index=7,
                end_row_index=8,
                start_column_index=start_column,
                end_column_index=end_column,
            )
        )

    for label_column in (0, 4, 13):
        requests.append(
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=1,
                end_row_index=2,
                start_column_index=label_column,
                end_column_index=label_column + 1,
                user_entered_format={
                    "backgroundColorStyle": _hex_color_style(ANALYSIS_THEME_FOREST),
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "textFormat": {
                        "foregroundColorStyle": _hex_color_style(ANALYSIS_THEME_IVORY),
                        "fontSize": 10,
                        "bold": True,
                    },
                },
                fields="userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment)",
            )
        )

    for start_column, end_column, alignment in ((1, 3, "CENTER"), (5, 12, "LEFT"), (14, 17, "CENTER")):
        requests.append(
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=1,
                end_row_index=2,
                start_column_index=start_column,
                end_column_index=end_column,
                user_entered_format={
                    "backgroundColorStyle": _hex_color_style(ANALYSIS_THEME_SAND),
                    "horizontalAlignment": alignment,
                    "verticalAlignment": "MIDDLE",
                    "textFormat": {
                        "foregroundColorStyle": _hex_color_style(ANALYSIS_THEME_INK),
                        "fontSize": 10,
                        "bold": True,
                    },
                    "wrapStrategy": "WRAP",
                },
                fields="userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
            )
        )

    for label_column in (0, 4, 8, 12, 16):
        requests.append(
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=3,
                end_row_index=4,
                start_column_index=label_column,
                end_column_index=label_column + 1,
                user_entered_format={
                    "backgroundColorStyle": _hex_color_style(ANALYSIS_THEME_PARCHMENT),
                    "horizontalAlignment": "LEFT",
                    "verticalAlignment": "BOTTOM",
                    "textFormat": {
                        "foregroundColorStyle": _hex_color_style(ANALYSIS_THEME_MOSS),
                        "fontSize": 9,
                        "bold": True,
                    },
                },
                fields="userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment)",
            )
        )

    for start_column, background_color, text_color in (
        (0, ANALYSIS_THEME_SAGE, ANALYSIS_THEME_FOREST),
        (4, ANALYSIS_THEME_AMBER_MIST, ANALYSIS_THEME_AMBER),
        (8, ANALYSIS_THEME_TERRACOTTA_MIST, ANALYSIS_THEME_TERRACOTTA),
        (12, ANALYSIS_THEME_NAVY_MIST, ANALYSIS_THEME_NAVY),
        (16, ANALYSIS_THEME_TEAL_MIST, ANALYSIS_THEME_MOSS),
    ):
        requests.append(
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=4,
                end_row_index=6,
                start_column_index=start_column,
                end_column_index=start_column + 4,
                user_entered_format={
                    "backgroundColorStyle": _hex_color_style(background_color),
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "textFormat": {
                        "foregroundColorStyle": _hex_color_style(text_color),
                        "fontSize": 18,
                        "bold": True,
                    },
                    "numberFormat": {"type": "NUMBER", "pattern": "#,##0"},
                },
                fields="userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment,numberFormat)",
            )
        )

    for start_column, end_column, background_color, text_color, start_row_index, end_row_index, alignment in (
        (0, 4, ANALYSIS_THEME_FOREST, ANALYSIS_THEME_IVORY, 6, 7, "CENTER"),
        (4, visible_column_count, ANALYSIS_THEME_SAND, ANALYSIS_THEME_INK, 6, 7, "LEFT"),
        (0, ANALYSIS_CATEGORY_STATUS_COLUMN_INDEX, ANALYSIS_THEME_FOREST, ANALYSIS_THEME_IVORY, 7, 8, "CENTER"),
        (
            ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX - 1,
            ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 4,
            ANALYSIS_THEME_NAVY,
            ANALYSIS_THEME_IVORY,
            7,
            8,
            "CENTER",
        ),
        (
            ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX - 1,
            ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 2,
            ANALYSIS_THEME_TERRACOTTA,
            ANALYSIS_THEME_IVORY,
            7,
            8,
            "CENTER",
        ),
    ):
        requests.append(
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=start_row_index,
                end_row_index=end_row_index,
                start_column_index=start_column,
                end_column_index=end_column,
                user_entered_format={
                    "backgroundColorStyle": _hex_color_style(background_color),
                    "horizontalAlignment": alignment,
                    "verticalAlignment": "MIDDLE",
                    "textFormat": {
                        "foregroundColorStyle": _hex_color_style(text_color),
                        "fontSize": 11 if start_row_index == 7 else 10,
                        "bold": True,
                    },
                    **({"wrapStrategy": "WRAP"} if start_row_index == 6 and start_column == 4 else {}),
                },
                fields="userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
            )
        )

    for start_column, end_column, background_color in (
        (0, ANALYSIS_CATEGORY_STATUS_COLUMN_INDEX, ANALYSIS_THEME_SAGE),
        (ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX - 1, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 4, ANALYSIS_THEME_NAVY_MIST),
        (ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX - 1, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 2, ANALYSIS_THEME_TERRACOTTA_MIST),
    ):
        requests.append(
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=8,
                end_row_index=9,
                start_column_index=start_column,
                end_column_index=end_column,
                user_entered_format={
                    "backgroundColorStyle": _hex_color_style(background_color),
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "textFormat": {
                        "foregroundColorStyle": _hex_color_style(ANALYSIS_THEME_INK),
                        "fontSize": 10,
                        "bold": True,
                    },
                },
                fields="userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment)",
            )
        )

    requests.extend(
        [
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=9,
                end_row_index=200,
                start_column_index=1,
                end_column_index=2,
                user_entered_format={
                    "backgroundColorStyle": _hex_color_style(ANALYSIS_THEME_IVORY),
                    "verticalAlignment": "TOP",
                    "wrapStrategy": "WRAP",
                },
                fields="userEnteredFormat(backgroundColorStyle,verticalAlignment,wrapStrategy)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=9,
                end_row_index=200,
                start_column_index=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX - 1,
                end_column_index=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX,
                user_entered_format={
                    "backgroundColorStyle": _hex_color_style(ANALYSIS_THEME_IVORY),
                    "verticalAlignment": "TOP",
                    "wrapStrategy": "WRAP",
                },
                fields="userEnteredFormat(backgroundColorStyle,verticalAlignment,wrapStrategy)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=9,
                end_row_index=200,
                start_column_index=2,
                end_column_index=ANALYSIS_CATEGORY_RECEIPTS_COLUMN_INDEX,
                user_entered_format={"horizontalAlignment": "RIGHT", "verticalAlignment": "TOP"},
                fields="userEnteredFormat(horizontalAlignment,verticalAlignment)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=9,
                end_row_index=200,
                start_column_index=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX,
                end_column_index=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 4,
                user_entered_format={"horizontalAlignment": "RIGHT", "verticalAlignment": "TOP"},
                fields="userEnteredFormat(horizontalAlignment,verticalAlignment)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=9,
                end_row_index=200,
                start_column_index=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX,
                end_column_index=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 2,
                user_entered_format={"horizontalAlignment": "RIGHT", "verticalAlignment": "TOP"},
                fields="userEnteredFormat(horizontalAlignment,verticalAlignment)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=9,
                end_row_index=200,
                start_column_index=ANALYSIS_CATEGORY_STATUS_COLUMN_INDEX - 1,
                end_column_index=ANALYSIS_CATEGORY_STATUS_COLUMN_INDEX,
                user_entered_format={
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "TOP",
                    "textFormat": {"bold": True},
                },
                fields="userEnteredFormat(horizontalAlignment,verticalAlignment,textFormat)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=9,
                end_row_index=200,
                start_column_index=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX - 1,
                end_column_index=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX,
                user_entered_format={"horizontalAlignment": "CENTER", "verticalAlignment": "TOP"},
                fields="userEnteredFormat(horizontalAlignment,verticalAlignment)",
            ),
        ]
    )

    requests.extend(
        [
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=1,
                end_row_index=2,
                start_column_index=14,
                end_column_index=17,
                user_entered_format={
                    "numberFormat": {"type": "DATE_TIME", "pattern": "yyyy-mm-dd hh:mm"},
                    "horizontalAlignment": "CENTER",
                },
                fields="userEnteredFormat(numberFormat,horizontalAlignment)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=9,
                end_row_index=200,
                start_column_index=2,
                end_column_index=ANALYSIS_CATEGORY_TOTAL_COLUMN_INDEX,
                user_entered_format={"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}},
                fields="userEnteredFormat(numberFormat)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=9,
                end_row_index=200,
                start_column_index=ANALYSIS_CATEGORY_LINE_ITEMS_COLUMN_INDEX - 1,
                end_column_index=ANALYSIS_CATEGORY_RECEIPTS_COLUMN_INDEX,
                user_entered_format={"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}},
                fields="userEnteredFormat(numberFormat)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=9,
                end_row_index=200,
                start_column_index=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX,
                end_column_index=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 4,
                user_entered_format={"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}},
                fields="userEnteredFormat(numberFormat)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=9,
                end_row_index=200,
                start_column_index=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX,
                end_column_index=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 2,
                user_entered_format={"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}},
                fields="userEnteredFormat(numberFormat)",
            ),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="ROWS", start_index=0, end_index=1, pixel_size=54),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="ROWS", start_index=1, end_index=2, pixel_size=34),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="ROWS", start_index=2, end_index=3, pixel_size=28),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="ROWS", start_index=3, end_index=4, pixel_size=22),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="ROWS", start_index=4, end_index=6, pixel_size=36),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="ROWS", start_index=6, end_index=7, pixel_size=34),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="ROWS", start_index=7, end_index=8, pixel_size=28),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="ROWS", start_index=8, end_index=9, pixel_size=26),
            _build_analysis_dimension_request(
                sheet_id=sheet_id,
                dimension="COLUMNS",
                start_index=0,
                end_index=visible_column_count,
                pixel_size=104,
            ),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="COLUMNS", start_index=1, end_index=2, pixel_size=220),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="COLUMNS", start_index=2, end_index=14, pixel_size=88),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="COLUMNS", start_index=14, end_index=15, pixel_size=118),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="COLUMNS", start_index=15, end_index=17, pixel_size=92),
            _build_analysis_dimension_request(sheet_id=sheet_id, dimension="COLUMNS", start_index=17, end_index=18, pixel_size=96),
            _build_analysis_dimension_request(
                sheet_id=sheet_id,
                dimension="COLUMNS",
                start_index=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX - 2,
                end_index=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX - 1,
                pixel_size=28,
            ),
            _build_analysis_dimension_request(
                sheet_id=sheet_id,
                dimension="COLUMNS",
                start_index=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX - 1,
                end_index=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX,
                pixel_size=118,
            ),
            _build_analysis_dimension_request(
                sheet_id=sheet_id,
                dimension="COLUMNS",
                start_index=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX,
                end_index=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 4,
                pixel_size=100,
            ),
            _build_analysis_dimension_request(
                sheet_id=sheet_id,
                dimension="COLUMNS",
                start_index=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX - 2,
                end_index=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX - 1,
                pixel_size=28,
            ),
            _build_analysis_dimension_request(
                sheet_id=sheet_id,
                dimension="COLUMNS",
                start_index=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX - 1,
                end_index=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX,
                pixel_size=200,
            ),
            _build_analysis_dimension_request(
                sheet_id=sheet_id,
                dimension="COLUMNS",
                start_index=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX,
                end_index=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 2,
                pixel_size=110,
            ),
            _build_analysis_dimension_request(
                sheet_id=sheet_id,
                dimension="COLUMNS",
                start_index=hidden_start_column_index,
                end_index=ANALYSIS_MAX_COLUMN_INDEX,
                hidden_by_user=True,
            ),
        ]
    )

    for start_row_index, end_row_index, start_column_index, end_column_index, style in (
        (1, 2, 0, 3, "SOLID_MEDIUM"),
        (1, 2, 4, 12, "SOLID_MEDIUM"),
        (1, 2, 13, 17, "SOLID_MEDIUM"),
        (2, 3, 0, visible_column_count, "SOLID"),
        (4, 6, 0, 4, "SOLID_MEDIUM"),
        (4, 6, 4, 8, "SOLID_MEDIUM"),
        (4, 6, 8, 12, "SOLID_MEDIUM"),
        (4, 6, 12, 16, "SOLID_MEDIUM"),
        (4, 6, 16, 20, "SOLID_MEDIUM"),
        (6, 7, 0, 4, "SOLID_MEDIUM"),
        (6, 7, 4, visible_column_count, "SOLID_MEDIUM"),
        (7, 12, 0, ANALYSIS_CATEGORY_STATUS_COLUMN_INDEX, "SOLID_MEDIUM"),
        (7, 12, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX - 1, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 4, "SOLID_MEDIUM"),
        (7, 12, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX - 1, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 2, "SOLID_MEDIUM"),
    ):
        requests.append(
            _build_analysis_outlined_range_request(
                sheet_id=sheet_id,
                start_row_index=start_row_index,
                end_row_index=end_row_index,
                start_column_index=start_column_index,
                end_column_index=end_column_index,
                style=style,
            )
        )

    timeline_table_start_row_index = ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER - 1
    timeline_title_row_index = ANALYSIS_MONTHLY_CATEGORY_TIMELINE_TITLE_ROW_NUMBER - 1
    requests.extend(
        [
            _build_analysis_merge_request(
                sheet_id=sheet_id,
                start_row_index=timeline_title_row_index,
                end_row_index=timeline_title_row_index + 1,
                start_column_index=0,
                end_column_index=visible_column_count,
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=timeline_title_row_index,
                end_row_index=timeline_title_row_index + 1,
                start_column_index=0,
                end_column_index=visible_column_count,
                user_entered_format={
                    "backgroundColorStyle": _hex_color_style(ANALYSIS_THEME_TEAL_MIST),
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "textFormat": {
                        "foregroundColorStyle": _hex_color_style(ANALYSIS_THEME_MOSS),
                        "fontSize": 11,
                        "bold": True,
                    },
                },
                fields="userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=timeline_table_start_row_index,
                end_row_index=timeline_table_start_row_index + 1,
                start_column_index=0,
                end_column_index=visible_column_count,
                user_entered_format={
                    "backgroundColorStyle": _hex_color_style(ANALYSIS_THEME_TEAL_MIST),
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "textFormat": {
                        "foregroundColorStyle": _hex_color_style(ANALYSIS_THEME_INK),
                        "fontSize": 10,
                        "bold": True,
                    },
                },
                fields="userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=timeline_table_start_row_index + 1,
                end_row_index=200,
                start_column_index=0,
                end_column_index=1,
                user_entered_format={"horizontalAlignment": "CENTER", "verticalAlignment": "TOP"},
                fields="userEnteredFormat(horizontalAlignment,verticalAlignment)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=timeline_table_start_row_index + 1,
                end_row_index=200,
                start_column_index=1,
                end_column_index=visible_column_count,
                user_entered_format={"horizontalAlignment": "RIGHT", "verticalAlignment": "TOP"},
                fields="userEnteredFormat(horizontalAlignment,verticalAlignment)",
            ),
            _build_analysis_repeat_cell_request(
                sheet_id=sheet_id,
                start_row_index=timeline_table_start_row_index + 1,
                end_row_index=200,
                start_column_index=1,
                end_column_index=visible_column_count,
                user_entered_format={"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}},
                fields="userEnteredFormat(numberFormat)",
            ),
            _build_analysis_dimension_request(
                sheet_id=sheet_id,
                dimension="ROWS",
                start_index=timeline_title_row_index,
                end_index=timeline_title_row_index + 1,
                pixel_size=28,
            ),
            _build_analysis_dimension_request(
                sheet_id=sheet_id,
                dimension="COLUMNS",
                start_index=0,
                end_index=1,
                pixel_size=118,
            ),
            _build_analysis_dimension_request(
                sheet_id=sheet_id,
                dimension="COLUMNS",
                start_index=1,
                end_index=visible_column_count,
                pixel_size=92,
            ),
            _build_analysis_outlined_range_request(
                sheet_id=sheet_id,
                start_row_index=timeline_title_row_index,
                end_row_index=timeline_title_row_index + max(category_timeline_row_count + 2, 3),
                start_column_index=0,
                end_column_index=visible_column_count,
                style="SOLID_MEDIUM",
            ),
        ]
    )

    return requests


@dataclass(slots=True)
class UploadedDriveFile:
    file_id: str
    web_view_link: str | None


@dataclass(slots=True)
class DriveImageFile:
    file_id: str
    name: str
    mime_type: str
    created_time: str
    parents: list[str]
    web_view_link: str | None


class GoogleWorkspaceClient:
    def __init__(
        self,
        *,
        credentials,
        drive_folder_id: str,
        spreadsheet_id: str,
        sheet_name: str,
        category_sheet_name: str = "Categories",
    ) -> None:
        self._drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self._sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self._drive_folder_id = drive_folder_id
        self._drive_folder_cache: dict[tuple[str, str], str] = {}
        self._spreadsheet_id = spreadsheet_id
        self._sheet_name = sheet_name
        self._category_sheet_name = category_sheet_name

    async def ensure_receipt_sheet(self) -> None:
        await asyncio.to_thread(self._ensure_receipt_sheet_sync)

    async def list_receipt_categories(self) -> list[str]:
        return await asyncio.to_thread(self._list_receipt_categories_sync)

    async def append_receipt_categories(self, categories: list[str], *, source: str = "gemini") -> list[str]:
        return await asyncio.to_thread(self._append_receipt_categories_sync, categories, source)

    async def upload_receipt_image(
        self,
        *,
        file_name: str,
        mime_type: str,
        image_bytes: bytes,
        purchase_date: str | None = None,
    ) -> UploadedDriveFile:
        return await asyncio.to_thread(self._upload_receipt_image_sync, file_name, mime_type, image_bytes, purchase_date)

    async def ensure_receipt_storage_folder(
        self,
        *,
        root_folder_id: str | None = None,
        date_hint: str | None = None,
    ) -> str:
        resolved_root_folder_id = root_folder_id or self._drive_folder_id
        return await asyncio.to_thread(
            self._ensure_receipt_storage_folder_sync,
            resolved_root_folder_id,
            date_hint,
        )

    async def append_receipt_row(self, row: list[str]) -> None:
        await asyncio.to_thread(self._append_receipt_row_sync, row)

    async def append_receipt_rows(self, rows: list[list[str]]) -> None:
        await asyncio.to_thread(self._append_receipt_rows_sync, rows)

    async def sync_analysis_sheets(
        self,
        *,
        years: list[str] | None = None,
        include_all_years: bool = True,
    ) -> dict[str, object]:
        return await asyncio.to_thread(self._sync_analysis_sheets_sync, years, include_all_years)

    async def list_receipt_attachment_names(self) -> set[str]:
        return await asyncio.to_thread(self._list_receipt_attachment_names_sync)

    async def receipt_attachment_exists(self, *, attachment_name: str) -> bool:
        return await asyncio.to_thread(self._receipt_attachment_exists_sync, attachment_name)

    async def list_image_files(self, *, folder_id: str) -> list[DriveImageFile]:
        return await asyncio.to_thread(self._list_image_files_sync, folder_id)

    async def download_file(self, *, file_id: str) -> bytes:
        return await asyncio.to_thread(self._download_file_sync, file_id)

    async def move_file(self, *, file_id: str, destination_folder_id: str) -> None:
        await asyncio.to_thread(self._move_file_sync, file_id, destination_folder_id)

    @property
    def spreadsheet_url(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self._spreadsheet_id}/edit"

    def _ensure_receipt_sheet_sync(self) -> None:
        self._ensure_sheet_with_header_sync(sheet_name=self._sheet_name, headers=RECEIPT_SHEET_HEADERS)
        self._ensure_category_sheet_sync()

    def _ensure_category_sheet_sync(self) -> None:
        self._ensure_sheet_with_header_sync(sheet_name=self._category_sheet_name, headers=CATEGORY_SHEET_HEADERS)

        existing_rows = (
            self._sheets.spreadsheets()
            .values()
            .get(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{self._category_sheet_name}'!A2:F",
            )
            .execute()
        ).get("values", [])
        if existing_rows:
            self._migrate_category_sheet_rows_sync(existing_rows)
            return

        seeded_rows = build_default_category_rows(timestamp=_timestamp_now())
        (
            self._sheets.spreadsheets()
            .values()
            .append(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{self._category_sheet_name}'!A2",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": seeded_rows},
            )
            .execute()
        )

    def _migrate_category_sheet_rows_sync(self, rows: list[list[str]]) -> None:
        updates: list[dict[str, object]] = []
        timestamp = _timestamp_now()

        for row_index, row in enumerate(rows, start=2):
            raw_name = row[0] if row else ""
            normalized_name = normalize_category_name(raw_name)
            if not normalized_name:
                continue

            description = DEFAULT_CATEGORY_DESCRIPTION_MAP.get(normalized_name)
            if normalized_name != raw_name:
                updates.append(
                    {
                        "range": f"'{self._category_sheet_name}'!A{row_index}:B{row_index}",
                        "values": [[normalized_name, description if description is not None else (row[1] if len(row) > 1 else "")]],
                    }
                )
                updates.append(
                    {
                        "range": f"'{self._category_sheet_name}'!E{row_index}",
                        "values": [[timestamp]],
                    }
                )

        if not updates:
            return

        (
            self._sheets.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"valueInputOption": "RAW", "data": updates},
            )
            .execute()
        )

    def _ensure_sheet_with_header_sync(self, *, sheet_name: str, headers: list[str]) -> None:
        self._ensure_sheet_exists_sync(sheet_name)

        current_header = (
            self._sheets.spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, range=f"'{sheet_name}'!1:1")
            .execute()
        )
        header_values = (current_header.get("values") or [[]])[0]

        if header_values == headers:
            return

        (
            self._sheets.spreadsheets()
            .values()
            .update(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption="RAW",
                body={"values": [headers]},
            )
            .execute()
        )

    def _list_receipt_categories_sync(self) -> list[str]:
        self._ensure_category_sheet_sync()

        response = (
            self._sheets.spreadsheets()
            .values()
            .get(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{self._category_sheet_name}'!A2:C",
            )
            .execute()
        )

        categories: list[str] = []
        for row in response.get("values", []):
            category_name = normalize_category_name(row[0]) if row else ""
            if not category_name:
                continue

            is_active = row[2].strip().lower() if len(row) >= 3 and row[2] is not None else "true"
            if is_active in {"false", "0", "no", "inactive"}:
                continue
            categories.append(category_name)

        return dedupe_category_names(categories)

    def _append_receipt_categories_sync(self, categories: list[str], source: str) -> list[str]:
        candidate_categories = dedupe_category_names(categories)
        if not candidate_categories:
            return []

        existing_categories = self._list_receipt_categories_sync()
        existing_keys = {value.casefold() for value in existing_categories}
        categories_to_add = [value for value in candidate_categories if value.casefold() not in existing_keys]
        if not categories_to_add:
            return []

        timestamp = _timestamp_now()
        (
            self._sheets.spreadsheets()
            .values()
            .append(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{self._category_sheet_name}'!A2",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={
                    "values": [
                        [category_name, "", "TRUE", timestamp, timestamp, source]
                        for category_name in categories_to_add
                    ]
                },
            )
            .execute()
        )
        return categories_to_add

    def _upload_receipt_image_sync(
        self,
        file_name: str,
        mime_type: str,
        image_bytes: bytes,
        purchase_date: str | None,
    ) -> UploadedDriveFile:
        media = MediaInMemoryUpload(image_bytes, mimetype=mime_type, resumable=False)
        parent_folder_id = self._ensure_receipt_storage_folder_sync(self._drive_folder_id, purchase_date)
        try:
            response = (
                self._drive.files()
                .create(
                    body={"name": file_name, "parents": [parent_folder_id]},
                    media_body=media,
                    fields="id,webViewLink",
                )
                .execute()
            )
        except HttpError as exc:
            if _is_service_account_quota_error(exc):
                raise RuntimeError(
                    "Google Drive rejected the upload because service accounts do not have storage quota on personal "
                    "My Drive. Use a Google Workspace shared drive or add OAuth refresh-token support for a user-owned "
                    "Drive account."
                ) from exc
            raise

        return UploadedDriveFile(file_id=response["id"], web_view_link=response.get("webViewLink"))

    def _ensure_receipt_storage_folder_sync(self, root_folder_id: str, date_hint: str | None) -> str:
        year, month = _resolve_drive_folder_parts(date_hint)
        year_folder_id = self._get_or_create_drive_folder_sync(parent_folder_id=root_folder_id, folder_name=year)
        return self._get_or_create_drive_folder_sync(parent_folder_id=year_folder_id, folder_name=month)

    def _get_or_create_drive_folder_sync(self, *, parent_folder_id: str, folder_name: str) -> str:
        cache_key = (parent_folder_id, folder_name)
        cached_folder_id = self._drive_folder_cache.get(cache_key)
        if cached_folder_id is not None:
            return cached_folder_id

        response = (
            self._drive.files()
            .list(
                q=(
                    f"'{_escape_drive_query_value(parent_folder_id)}' in parents and "
                    f"name = '{_escape_drive_query_value(folder_name)}' and "
                    f"mimeType = '{GOOGLE_DRIVE_FOLDER_MIME_TYPE}' and trashed = false"
                ),
                fields="files(id,name)",
                pageSize=1,
            )
            .execute()
        )
        existing_files = response.get("files", [])
        if existing_files:
            folder_id = existing_files[0]["id"]
            self._drive_folder_cache[cache_key] = folder_id
            return folder_id

        response = (
            self._drive.files()
            .create(
                body={
                    "name": folder_name,
                    "parents": [parent_folder_id],
                    "mimeType": GOOGLE_DRIVE_FOLDER_MIME_TYPE,
                },
                fields="id",
            )
            .execute()
        )
        folder_id = response["id"]
        self._drive_folder_cache[cache_key] = folder_id
        return folder_id

    def _append_receipt_row_sync(self, row: list[str]) -> None:
        self._append_receipt_rows_sync([row])

    def _append_receipt_rows_sync(self, rows: list[list[str]]) -> None:
        if not rows:
            return
        grouped_rows_by_sheet = self._group_receipt_rows_by_sheet_name(rows)
        for sheet_name, grouped_rows in grouped_rows_by_sheet.items():
            self._ensure_sheet_with_header_sync(sheet_name=sheet_name, headers=RECEIPT_SHEET_HEADERS)
            (
                self._sheets.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self._spreadsheet_id,
                    range=f"'{sheet_name}'!A1",
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body={"values": grouped_rows},
                )
                .execute()
            )
        self._sync_analysis_sheets_sync(list(grouped_rows_by_sheet), include_all_years=True)

    def _group_receipt_rows_by_sheet_name(self, rows: list[list[str]]) -> dict[str, list[list[str]]]:
        grouped_rows: dict[str, list[list[str]]] = {}
        for row in rows:
            sheet_name = self._resolve_receipt_sheet_name(row)
            grouped_rows.setdefault(sheet_name, []).append(row)
        return grouped_rows

    def _list_receipt_attachment_names_sync(self) -> set[str]:
        attachment_names: set[str] = set()
        for sheet_name in self._list_receipt_sheet_names_sync():
            response = (
                self._sheets.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self._spreadsheet_id,
                    range=f"'{sheet_name}'!{RECEIPT_ATTACHMENT_NAME_COLUMN}2:{RECEIPT_ATTACHMENT_NAME_COLUMN}",
                )
                .execute()
            )
            for row in response.get("values", []):
                normalized_attachment_name = _normalize_attachment_name(row[0] if row else "")
                if normalized_attachment_name:
                    attachment_names.add(normalized_attachment_name)
        return attachment_names

    def _receipt_attachment_exists_sync(self, attachment_name: str) -> bool:
        normalized_attachment_name = _normalize_attachment_name(attachment_name)
        if not normalized_attachment_name:
            return False
        return normalized_attachment_name in self._list_receipt_attachment_names_sync()

    def _list_receipt_sheet_names_sync(self) -> list[str]:
        spreadsheet = (
            self._sheets.spreadsheets()
            .get(spreadsheetId=self._spreadsheet_id, fields="sheets.properties.title")
            .execute()
        )
        return [
            title
            for title in (
                sheet.get("properties", {}).get("title", "")
                for sheet in spreadsheet.get("sheets", [])
            )
            if title and title != self._category_sheet_name and not _is_analysis_sheet_name(title)
        ]

    def _ensure_sheet_exists_sync(self, sheet_name: str) -> None:
        has_sheet = self._get_sheet_properties_by_title_sync(sheet_name) is not None
        if has_sheet:
            return

        (
            self._sheets.spreadsheets()
            .batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
            )
            .execute()
        )

    def _get_sheet_properties_by_title_sync(self, sheet_name: str) -> dict[str, Any] | None:
        spreadsheet = (
            self._sheets.spreadsheets()
            .get(spreadsheetId=self._spreadsheet_id, fields="sheets.properties")
            .execute()
        )
        for sheet in spreadsheet.get("sheets", []):
            properties = sheet.get("properties", {})
            if properties.get("title") == sheet_name:
                return dict(properties)
        return None

    def _recreate_analysis_sheet_sync(self, *, sheet_name: str, row_count: int, column_count: int) -> int:
        existing_properties = self._get_sheet_properties_by_title_sync(sheet_name)
        requests: list[dict[str, object]] = []
        if existing_properties is not None and "sheetId" in existing_properties:
            requests.append({"deleteSheet": {"sheetId": int(existing_properties["sheetId"])}})
        requests.append(
            {
                "addSheet": {
                    "properties": {
                        "title": sheet_name,
                        "gridProperties": {
                            "rowCount": max(row_count, 200),
                            "columnCount": column_count,
                            "frozenRowCount": 3,
                        },
                    }
                }
            }
        )
        (
            self._sheets.spreadsheets()
            .batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": requests},
            )
            .execute()
        )
        created_properties = self._get_sheet_properties_by_title_sync(sheet_name)
        if created_properties is None or "sheetId" not in created_properties:
            raise RuntimeError(f"Failed to recreate analysis sheet: {sheet_name}")
        return int(created_properties["sheetId"])

    def _apply_analysis_dashboard_layout_sync(
        self,
        *,
        sheet_id: int,
        category_timeline_column_count: int,
        category_timeline_row_count: int,
    ) -> None:
        requests = _build_analysis_dashboard_layout_requests(
            sheet_id=sheet_id,
            category_timeline_column_count=category_timeline_column_count,
            category_timeline_row_count=category_timeline_row_count,
        )
        (
            self._sheets.spreadsheets()
            .batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": requests},
            )
            .execute()
        )
        return

        requests: list[dict[str, object]] = [
            {
                "mergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": ANALYSIS_VISIBLE_COLUMN_COUNT,
                    },
                    "mergeType": "MERGE_ALL",
                }
            },
            {
                "mergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": 2,
                        "startColumnIndex": 1,
                        "endColumnIndex": 3,
                    },
                    "mergeType": "MERGE_ALL",
                }
            },
            {
                "mergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": 2,
                        "startColumnIndex": 5,
                        "endColumnIndex": 12,
                    },
                    "mergeType": "MERGE_ALL",
                }
            },
            {
                "mergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": 2,
                        "startColumnIndex": 14,
                        "endColumnIndex": 17,
                    },
                    "mergeType": "MERGE_ALL",
                }
            },
            {
                "mergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 2,
                        "endRowIndex": 3,
                        "startColumnIndex": 0,
                        "endColumnIndex": ANALYSIS_VISIBLE_COLUMN_COUNT,
                    },
                    "mergeType": "MERGE_ALL",
                }
            },
            {
                "mergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 6,
                        "endRowIndex": 7,
                        "startColumnIndex": 0,
                        "endColumnIndex": 4,
                    },
                    "mergeType": "MERGE_ALL",
                }
            },
            {
                "mergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 6,
                        "endRowIndex": 7,
                        "startColumnIndex": 4,
                        "endColumnIndex": ANALYSIS_VISIBLE_COLUMN_COUNT,
                    },
                    "mergeType": "MERGE_ALL",
                }
            },
        ]

        for start_column in (0, 4, 8, 12, 16):
            requests.append(
                {
                    "mergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 4,
                            "endRowIndex": 6,
                            "startColumnIndex": start_column,
                            "endColumnIndex": start_column + 4,
                        },
                        "mergeType": "MERGE_ALL",
                    }
                }
            )

        for start_column, end_column in ((0, 6), (7, 10), (11, 16), (17, 20)):
            requests.append(
                {
                    "mergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 7,
                            "endRowIndex": 8,
                            "startColumnIndex": start_column,
                            "endColumnIndex": end_column,
                        },
                        "mergeType": "MERGE_ALL",
                    }
                }
            )

        requests.append(
            {
                "mergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 9,
                        "endRowIndex": 12,
                        "startColumnIndex": 17,
                        "endColumnIndex": 20,
                    },
                    "mergeType": "MERGE_ALL",
                }
            }
        )

        requests.extend(
            [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": ANALYSIS_VISIBLE_COLUMN_COUNT,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColorStyle": {"rgbColor": {"red": 0.11, "green": 0.29, "blue": 0.25}},
                                "horizontalAlignment": "CENTER",
                                "verticalAlignment": "MIDDLE",
                                "textFormat": {
                                    "foregroundColorStyle": {"rgbColor": {"red": 1, "green": 1, "blue": 1}},
                                    "fontSize": 18,
                                    "bold": True,
                                },
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": 2,
                            "startColumnIndex": 0,
                            "endColumnIndex": ANALYSIS_VISIBLE_COLUMN_COUNT,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColorStyle": {"rgbColor": {"red": 0.92, "green": 0.96, "blue": 0.94}},
                                "textFormat": {"bold": True},
                                "verticalAlignment": "MIDDLE",
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColorStyle,textFormat,verticalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 3,
                            "endRowIndex": 4,
                            "startColumnIndex": 0,
                            "endColumnIndex": ANALYSIS_VISIBLE_COLUMN_COUNT,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColorStyle": {"rgbColor": {"red": 0.86, "green": 0.91, "blue": 0.99}},
                                "horizontalAlignment": "CENTER",
                                "textFormat": {"bold": True, "fontSize": 10},
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 4,
                            "endRowIndex": 6,
                            "startColumnIndex": 0,
                            "endColumnIndex": ANALYSIS_VISIBLE_COLUMN_COUNT,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColorStyle": {"rgbColor": {"red": 0.97, "green": 0.98, "blue": 1.0}},
                                "horizontalAlignment": "CENTER",
                                "verticalAlignment": "MIDDLE",
                                "textFormat": {"bold": True, "fontSize": 14},
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment,verticalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 6,
                            "endRowIndex": 7,
                            "startColumnIndex": 0,
                            "endColumnIndex": ANALYSIS_VISIBLE_COLUMN_COUNT,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColorStyle": {"rgbColor": {"red": 0.96, "green": 0.97, "blue": 0.92}},
                                "verticalAlignment": "MIDDLE",
                                "textFormat": {"bold": True},
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColorStyle,textFormat,verticalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 7,
                            "endRowIndex": 8,
                            "startColumnIndex": 0,
                            "endColumnIndex": ANALYSIS_VISIBLE_COLUMN_COUNT,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColorStyle": {"rgbColor": {"red": 0.16, "green": 0.43, "blue": 0.64}},
                                "horizontalAlignment": "CENTER",
                                "textFormat": {
                                    "foregroundColorStyle": {"rgbColor": {"red": 1, "green": 1, "blue": 1}},
                                    "bold": True,
                                },
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColorStyle,textFormat,horizontalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 8,
                            "endRowIndex": 9,
                            "startColumnIndex": 0,
                            "endColumnIndex": 16,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColorStyle": {"rgbColor": {"red": 0.91, "green": 0.94, "blue": 0.98}},
                                "textFormat": {"bold": True},
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColorStyle,textFormat)",
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                            "endIndex": ANALYSIS_VISIBLE_COLUMN_COUNT,
                        },
                        "properties": {"pixelSize": 110},
                        "fields": "pixelSize",
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 1,
                            "endIndex": 3,
                        },
                        "properties": {"pixelSize": 150},
                        "fields": "pixelSize",
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 5,
                            "endIndex": 12,
                        },
                        "properties": {"pixelSize": 135},
                        "fields": "pixelSize",
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 10,
                            "endIndex": 12,
                        },
                        "properties": {"pixelSize": 190},
                        "fields": "pixelSize",
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": ANALYSIS_HELPER_SOURCE_COLUMN_INDEX - 1,
                            "endIndex": ANALYSIS_MAX_COLUMN_INDEX,
                        },
                        "properties": {"hiddenByUser": True},
                        "fields": "hiddenByUser",
                    }
                },
            ]
        )

        (
            self._sheets.spreadsheets()
            .batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": requests},
            )
            .execute()
        )

    def _sync_analysis_sheets_sync(
        self,
        target_years: list[str] | None = None,
        include_all_years: bool = True,
    ) -> dict[str, object]:
        available_receipt_sheet_names = self._list_receipt_sheet_names_sync()
        available_year_sheet_names = sorted(
            sheet_name for sheet_name in available_receipt_sheet_names if _is_year_sheet_name(sheet_name)
        )
        if target_years is None:
            year_sheet_names = available_year_sheet_names
        else:
            year_sheet_names = sorted(
                sheet_name for sheet_name in {sheet_name for sheet_name in target_years if _is_year_sheet_name(sheet_name)}
                if sheet_name in available_year_sheet_names
            )
        updated_analysis_sheets: list[str] = []
        missing_years = (
            sorted(
                sheet_name
                for sheet_name in {sheet_name for sheet_name in target_years if _is_year_sheet_name(sheet_name)}
                if sheet_name not in year_sheet_names
            )
            if target_years is not None
            else []
        )

        for year_sheet_name in year_sheet_names:
            analysis_rows = self._build_analysis_sheet_rows_sync([year_sheet_name], scope_label=year_sheet_name)
            analysis_sheet_name = f"{ANALYSIS_SHEET_PREFIX}{year_sheet_name}"
            self._replace_sheet_values_sync(sheet_name=analysis_sheet_name, rows=analysis_rows)
            updated_analysis_sheets.append(analysis_sheet_name)

        if include_all_years:
            analysis_rows = self._build_analysis_sheet_rows_sync(
                available_year_sheet_names,
                scope_label="All Years",
            )
            self._replace_sheet_values_sync(sheet_name=ANALYSIS_ALL_YEARS_SHEET_NAME, rows=analysis_rows)
            updated_analysis_sheets.append(ANALYSIS_ALL_YEARS_SHEET_NAME)

        return {
            "updated_analysis_sheets": updated_analysis_sheets,
            "years": year_sheet_names,
            "missing_years": missing_years,
            "source_sheet_names": available_year_sheet_names,
            "include_all_years": include_all_years,
        }

    def _build_analysis_sheet_rows_sync(self, source_sheet_names: list[str], *, scope_label: str) -> list[list[object]]:
        return build_analysis_sheet_rows(
            scope_label=scope_label,
            source_sheet_names=source_sheet_names,
            category_sheet_name=self._category_sheet_name,
        )

    def _read_receipt_sheet_rows_sync(self, sheet_name: str) -> list[list[str]]:
        response = (
            self._sheets.spreadsheets()
            .values()
            .get(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{sheet_name}'!A2:ZZ",
            )
            .execute()
        )
        return [list(row) for row in response.get("values", [])]

    def _replace_sheet_values_sync(self, *, sheet_name: str, rows: list[list[object]]) -> None:
        sheet_id = self._recreate_analysis_sheet_sync(
            sheet_name=sheet_name,
            row_count=len(rows),
            column_count=ANALYSIS_MAX_COLUMN_INDEX,
        )
        (
            self._sheets.spreadsheets()
            .values()
            .update(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption="USER_ENTERED",
                body={"values": rows},
            )
            .execute()
        )
        category_timeline_column_count, category_timeline_row_count = self._resolve_category_timeline_shape_sync(
            sheet_name=sheet_name
        )
        self._apply_analysis_dashboard_layout_sync(
            sheet_id=sheet_id,
            category_timeline_column_count=category_timeline_column_count,
            category_timeline_row_count=category_timeline_row_count,
        )
        self._apply_analysis_dashboard_charts_sync(
            sheet_id=sheet_id,
            sheet_name=sheet_name,
            category_timeline_column_count=category_timeline_column_count,
            category_timeline_row_count=category_timeline_row_count,
        )

    def _apply_analysis_dashboard_charts_sync(
        self,
        *,
        sheet_id: int,
        sheet_name: str,
        category_timeline_column_count: int | None = None,
        category_timeline_row_count: int | None = None,
    ) -> None:
        if category_timeline_column_count is None or category_timeline_row_count is None:
            category_timeline_column_count, category_timeline_row_count = self._resolve_category_timeline_shape_sync(
                sheet_name=sheet_name
            )
        requests = _build_analysis_dashboard_chart_requests(
            sheet_id=sheet_id,
            category_timeline_series_count=max(category_timeline_column_count - 1, 1),
            category_timeline_row_count=max(category_timeline_row_count, 2),
        )
        if not requests:
            return
        (
            self._sheets.spreadsheets()
            .batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": requests},
            )
            .execute()
        )

    def _resolve_category_timeline_shape_sync(self, *, sheet_name: str) -> tuple[int, int]:
        fallback_column_count = max(len(self._list_receipt_categories_sync()) + 1, 2)
        timeline_end_column = _column_letter(ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX + fallback_column_count - 1)
        timeline_range = (
            f"'{sheet_name}'!{ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_COLUMN}"
            f"{ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER}:{timeline_end_column}200"
        )
        for _ in range(10):
            response = (
                self._sheets.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self._spreadsheet_id,
                    range=timeline_range,
                    valueRenderOption="UNFORMATTED_VALUE",
                )
                .execute()
            )
            values = response.get("values", [])
            if len(values) > 1 and len(values[0]) > 1 and len(values[1]) > 1:
                return len(values[0]), len(values)
            time.sleep(0.5)
        return fallback_column_count, 2

    def _resolve_receipt_sheet_name(self, row: list[str]) -> str:
        for column_index in (RECEIPT_PURCHASE_DATE_INDEX, RECEIPT_PROCESSED_AT_INDEX):
            year = _extract_year_from_cell(_get_row_value(row, column_index))
            if year is not None:
                return year

        configured_year = _extract_year_from_cell(self._sheet_name)
        if configured_year is not None:
            return configured_year
        return str(datetime.now(UTC).year)

    def _list_image_files_sync(self, folder_id: str) -> list[DriveImageFile]:
        page_token = None
        files: list[DriveImageFile] = []

        while True:
            response = (
                self._drive.files()
                .list(
                    q=(
                        f"'{folder_id}' in parents and trashed = false "
                        "and mimeType != 'application/vnd.google-apps.folder'"
                    ),
                    fields="nextPageToken,files(id,name,mimeType,createdTime,parents,webViewLink)",
                    orderBy="createdTime asc",
                    pageSize=100,
                    pageToken=page_token,
                )
                .execute()
            )

            image_items = [item for item in response.get("files", []) if str(item.get("mimeType", "")).startswith("image/")]
            files.extend(_parse_drive_image_files(image_items))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return files

    def _download_file_sync(self, file_id: str) -> bytes:
        return self._drive.files().get_media(fileId=file_id).execute()

    def _move_file_sync(self, file_id: str, destination_folder_id: str) -> None:
        response = self._drive.files().get(fileId=file_id, fields="parents").execute()
        parents = response.get("parents", [])
        remove_parents = ",".join(parent for parent in parents if parent != destination_folder_id)
        (
            self._drive.files()
            .update(
                fileId=file_id,
                addParents=destination_folder_id,
                removeParents=remove_parents or None,
                fields="id,parents",
            )
            .execute()
        )


def _is_service_account_quota_error(exc: HttpError) -> bool:
    if getattr(exc, "resp", None) is not None and getattr(exc.resp, "status", None) != 403:
        return False

    text = str(exc)
    return "storageQuotaExceeded" in text or "Service Accounts do not have storage quota" in text


def _parse_drive_image_files(items: list[dict[str, Any]]) -> list[DriveImageFile]:
    return [
        DriveImageFile(
            file_id=item["id"],
            name=item["name"],
            mime_type=item["mimeType"],
            created_time=item.get("createdTime", ""),
            parents=list(item.get("parents", [])),
            web_view_link=item.get("webViewLink"),
        )
        for item in items
    ]


def build_analysis_sheet_rows(
    *,
    scope_label: str,
    source_sheet_names: list[str],
    category_sheet_name: str = "Categories",
    receipt_rows: list[list[str]] | None = None,
) -> list[list[object]]:
    del receipt_rows
    rows = _new_analysis_grid(row_count=ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER + 1)
    source_sheet_text = ", ".join(source_sheet_names) if source_sheet_names else ANALYSIS_NONE_LABEL
    display_scope_label = ANALYSIS_SCOPE_ALL_YEARS_LABEL if scope_label == "All Years" else scope_label

    _set_grid_cell(rows, 1, 1, ANALYSIS_DASHBOARD_TITLE)
    _set_grid_cell(rows, 2, 1, ANALYSIS_SCOPE_LABEL)
    _set_grid_cell(rows, 2, 2, display_scope_label)
    _set_grid_cell(rows, 2, 5, ANALYSIS_SOURCE_SHEETS_LABEL)
    _set_grid_cell(rows, 2, 6, source_sheet_text)
    _set_grid_cell(rows, 2, 14, ANALYSIS_GENERATED_AT_LABEL)
    _set_grid_cell(rows, 2, 15, "=NOW()")
    _set_grid_cell(rows, 3, 1, ANALYSIS_DASHBOARD_SUBTITLE)

    _set_grid_cell(rows, 4, 1, ANALYSIS_UNIQUE_RECEIPTS_LABEL)
    _set_grid_cell(rows, 4, 5, ANALYSIS_RECEIPT_TOTAL_LABEL)
    _set_grid_cell(rows, 4, 9, ANALYSIS_AVERAGE_RECEIPT_LABEL)
    _set_grid_cell(rows, 4, 13, ANALYSIS_UNIQUE_MERCHANTS_LABEL)
    _set_grid_cell(rows, 4, 17, ANALYSIS_LINE_ITEM_ROWS_LABEL)
    _set_grid_cell(rows, 7, 1, ANALYSIS_DATE_RANGE_LABEL)

    _set_grid_cell(rows, 8, 1, ANALYSIS_CATEGORY_SECTION_LABEL)
    _set_grid_cell(rows, 8, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX, ANALYSIS_MONTHLY_SECTION_LABEL)
    _set_grid_cell(rows, 8, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX, ANALYSIS_MERCHANT_SECTION_LABEL)
    _set_grid_cell(rows, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_TITLE_ROW_NUMBER, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX, ANALYSIS_TREND_SECTION_LABEL)

    _set_grid_cell(rows, 9, 1, ANALYSIS_CATEGORY_HEADER_LABEL)
    _set_grid_cell(rows, 9, 2, ANALYSIS_DESCRIPTION_HEADER_LABEL)
    for month_offset in range(ANALYSIS_CATEGORY_MONTH_COLUMN_COUNT):
        _set_grid_cell(rows, 9, 3 + month_offset, f"{month_offset + 1}月")
    _set_grid_cell(rows, 9, ANALYSIS_CATEGORY_TOTAL_COLUMN_INDEX, ANALYSIS_TOTAL_AMOUNT_HEADER_LABEL)
    _set_grid_cell(rows, 9, ANALYSIS_CATEGORY_LINE_ITEMS_COLUMN_INDEX, ANALYSIS_LINE_ITEMS_HEADER_LABEL)
    _set_grid_cell(rows, 9, ANALYSIS_CATEGORY_RECEIPTS_COLUMN_INDEX, ANALYSIS_RECEIPTS_HEADER_LABEL)
    _set_grid_cell(rows, 9, ANALYSIS_CATEGORY_STATUS_COLUMN_INDEX, ANALYSIS_STATUS_HEADER_LABEL)
    _set_grid_cell(rows, 9, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX, ANALYSIS_MONTH_HEADER_LABEL)
    _set_grid_cell(rows, 9, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 1, ANALYSIS_RECEIPT_TOTAL_LABEL)
    _set_grid_cell(rows, 9, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 2, ANALYSIS_RECEIPT_COUNT_HEADER_LABEL)
    _set_grid_cell(rows, 9, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 3, ANALYSIS_AVG_RECEIPT_HEADER_LABEL)
    _set_grid_cell(rows, 9, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 4, ANALYSIS_MERCHANTS_HEADER_LABEL)
    _set_grid_cell(rows, 9, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX, ANALYSIS_MERCHANT_HEADER_LABEL)
    _set_grid_cell(rows, 9, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 1, ANALYSIS_RECEIPT_TOTAL_LABEL)
    _set_grid_cell(rows, 9, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 2, ANALYSIS_RECEIPT_COUNT_HEADER_LABEL)

    if not source_sheet_names:
        _set_grid_cell(rows, 5, 1, 0)
        _set_grid_cell(rows, 5, 5, 0)
        _set_grid_cell(rows, 5, 9, 0)
        _set_grid_cell(rows, 5, 13, 0)
        _set_grid_cell(rows, 5, 17, 0)
        _set_grid_cell(rows, 7, 5, ANALYSIS_NONE_LABEL)
        _set_grid_cell(rows, 10, 1, ANALYSIS_NO_CATEGORY_DATA_LABEL)
        _set_grid_cell(rows, 10, 2, "")
        for month_offset in range(ANALYSIS_CATEGORY_MONTH_COLUMN_COUNT):
            _set_grid_cell(rows, 10, 3 + month_offset, 0)
        _set_grid_cell(rows, 10, ANALYSIS_CATEGORY_TOTAL_COLUMN_INDEX, 0)
        _set_grid_cell(rows, 10, ANALYSIS_CATEGORY_LINE_ITEMS_COLUMN_INDEX, 0)
        _set_grid_cell(rows, 10, ANALYSIS_CATEGORY_RECEIPTS_COLUMN_INDEX, 0)
        _set_grid_cell(rows, 10, ANALYSIS_CATEGORY_STATUS_COLUMN_INDEX, ANALYSIS_UNUSED_LABEL)
        _set_grid_cell(rows, 10, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX, ANALYSIS_NO_MONTH_DATA_LABEL)
        _set_grid_cell(rows, 10, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 1, 0)
        _set_grid_cell(rows, 10, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 2, 0)
        _set_grid_cell(rows, 10, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 3, 0)
        _set_grid_cell(rows, 10, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 4, 0)
        _set_grid_cell(rows, 10, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX, ANALYSIS_NO_MERCHANT_DATA_LABEL)
        _set_grid_cell(rows, 10, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 1, 0)
        _set_grid_cell(rows, 10, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 2, 0)
        _set_grid_cell(rows, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX, ANALYSIS_NO_MONTH_DATA_LABEL)
        return [_trim_trailing_blank_cells(row) for row in rows]

    source_formula = _build_analysis_source_formula(source_sheet_names)
    _set_grid_cell(rows, 2, ANALYSIS_HELPER_SOURCE_COLUMN_INDEX, source_formula)
    _set_grid_cell(rows, 2, ANALYSIS_HELPER_LATEST_RECEIPTS_COLUMN_INDEX, _build_latest_receipts_formula())
    _set_grid_cell(rows, 2, ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_COLUMN_INDEX, _build_active_line_items_formula())
    _set_grid_cell(rows, 2, ANALYSIS_HELPER_RECEIPT_TOTALS_COLUMN_INDEX, _build_receipt_totals_formula())
    _set_grid_cell(rows, 2, ANALYSIS_HELPER_CATEGORY_REFERENCE_COLUMN_INDEX, _build_active_categories_formula(category_sheet_name))
    _set_grid_cell(rows, 2, ANALYSIS_HELPER_CATEGORY_ROLLUP_COLUMN_INDEX, _build_category_rollup_formula())
    _set_grid_cell(rows, 2, ANALYSIS_HELPER_MONTH_REFERENCE_COLUMN_INDEX, _build_month_reference_formula(source_sheet_names))
    _set_grid_cell(rows, 2, ANALYSIS_HELPER_MONTH_ROLLUP_COLUMN_INDEX, _build_month_rollup_formula())
    _set_grid_cell(rows, 2, ANALYSIS_HELPER_RECEIPT_MONTH_LOOKUP_COLUMN_INDEX, _build_receipt_month_lookup_formula())
    _set_grid_cell(rows, 2, ANALYSIS_HELPER_ITEM_MONTHS_COLUMN_INDEX, _build_item_months_formula())

    _set_grid_cell(rows, 5, 1, f'=IFERROR(COUNTA(FILTER(INDEX(${ANALYSIS_HELPER_RECEIPT_TOTALS_START_COLUMN}$2:${ANALYSIS_HELPER_RECEIPT_TOTALS_END_COLUMN},,1), LEN(INDEX(${ANALYSIS_HELPER_RECEIPT_TOTALS_START_COLUMN}$2:${ANALYSIS_HELPER_RECEIPT_TOTALS_END_COLUMN},,1)))), 0)')
    _set_grid_cell(rows, 5, 5, f'=IFERROR(SUM(FILTER(INDEX(${ANALYSIS_HELPER_RECEIPT_TOTALS_START_COLUMN}$2:${ANALYSIS_HELPER_RECEIPT_TOTALS_END_COLUMN},,4), LEN(INDEX(${ANALYSIS_HELPER_RECEIPT_TOTALS_START_COLUMN}$2:${ANALYSIS_HELPER_RECEIPT_TOTALS_END_COLUMN},,1)))), 0)')
    _set_grid_cell(rows, 5, 9, f'=IFERROR(AVERAGE(FILTER(INDEX(${ANALYSIS_HELPER_RECEIPT_TOTALS_START_COLUMN}$2:${ANALYSIS_HELPER_RECEIPT_TOTALS_END_COLUMN},,4), LEN(INDEX(${ANALYSIS_HELPER_RECEIPT_TOTALS_START_COLUMN}$2:${ANALYSIS_HELPER_RECEIPT_TOTALS_END_COLUMN},,1)))), 0)')
    _set_grid_cell(rows, 5, 13, f'=IFERROR(COUNTUNIQUE(FILTER(INDEX(${ANALYSIS_HELPER_RECEIPT_TOTALS_START_COLUMN}$2:${ANALYSIS_HELPER_RECEIPT_TOTALS_END_COLUMN},,2), LEN(INDEX(${ANALYSIS_HELPER_RECEIPT_TOTALS_START_COLUMN}$2:${ANALYSIS_HELPER_RECEIPT_TOTALS_END_COLUMN},,2)))), 0)')
    _set_grid_cell(rows, 5, 17, f'=IFERROR(COUNTA(FILTER(INDEX(${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_START_COLUMN}$2:${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_END_COLUMN},,3), LEN(INDEX(${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_START_COLUMN}$2:${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_END_COLUMN},,3)))), 0)')
    receipt_totals_range = f"${ANALYSIS_HELPER_RECEIPT_TOTALS_START_COLUMN}$2:${ANALYSIS_HELPER_RECEIPT_TOTALS_END_COLUMN}"
    receipt_date_value_formula = _build_sheet_date_value_formula(receipt_totals_range, 3)
    _set_grid_cell(
        rows,
        7,
        5,
        f'=IFERROR(TEXT(MIN(FILTER({receipt_date_value_formula}, LEN(INDEX({receipt_totals_range},,3)))), "yyyy-mm-dd")'
        ' & " .. " & '
        f'TEXT(MAX(FILTER({receipt_date_value_formula}, LEN(INDEX({receipt_totals_range},,3)))), "yyyy-mm-dd"), "{ANALYSIS_NONE_LABEL}")',
    )

    _set_grid_cell(
        rows,
        10,
        1,
        _build_category_analysis_formula(),
    )
    _set_grid_cell(
        rows,
        10,
        ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX,
        _build_month_timeline_formula(),
    )
    _set_grid_cell(
        rows,
        10,
        ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX,
        _build_merchant_analysis_formula(),
    )
    _set_grid_cell(
        rows,
        ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER,
        ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX,
        _build_category_month_matrix_formula(),
    )

    return [_trim_trailing_blank_cells(row) for row in rows]


def _new_analysis_grid(*, row_count: int) -> list[list[object]]:
    return [["" for _ in range(ANALYSIS_MAX_COLUMN_INDEX)] for _ in range(row_count)]


def _set_grid_cell(rows: list[list[object]], row_number: int, column_number: int, value: object) -> None:
    rows[row_number - 1][column_number - 1] = value


def _trim_trailing_blank_cells(row: list[object]) -> list[object]:
    trimmed_row = list(row)
    while trimmed_row and trimmed_row[-1] == "":
        trimmed_row.pop()
    return trimmed_row


def _quote_sheet_name(sheet_name: str) -> str:
    return "'" + sheet_name.replace("'", "''") + "'"


def _build_sheet_date_value_formula(range_reference: str, column_index: int) -> str:
    indexed_value = f"INDEX({range_reference},,{column_index})"
    return f"IF(ISNUMBER({indexed_value}), {indexed_value}, DATEVALUE(LEFT(TO_TEXT({indexed_value}), 10)))"


def _build_analysis_source_formula(source_sheet_names: list[str]) -> str:
    source_ranges = [f"{_quote_sheet_name(sheet_name)}!A2:{RECEIPT_LAST_COLUMN}" for sheet_name in source_sheet_names]
    source_stack = source_ranges[0] if len(source_ranges) == 1 else "{" + ";".join(source_ranges) + "}"
    return f'=QUERY({source_stack}, "select * where Col11 is not null", 0)'


def _build_latest_receipts_formula() -> str:
    source_range = f"${ANALYSIS_HELPER_SOURCE_START_COLUMN}$2:${ANALYSIS_HELPER_SOURCE_END_COLUMN}"
    return (
        '=IFERROR('
        'SORTN('
        'SORT('
        'FILTER({'
        f'INDEX({source_range},,11),'
        f'INDEX({source_range},,1),'
        f'INDEX({source_range},,15),'
        f'IF(LEN(INDEX({source_range},,17)), INDEX({source_range},,17), INDEX({source_range},,1)),'
        f'INDEX({source_range},,22),'
        f'INDEX({source_range},,11)&"|"&INDEX({source_range},,1)'
        f'}}, LEN(INDEX({source_range},,11))),'
        '1, TRUE, 2, FALSE'
        '),'
        '9^9, 2, 1, TRUE'
        '),'
        '{"","","","","",""}'
        ')'
    )


def _build_active_line_items_formula() -> str:
    source_range = f"${ANALYSIS_HELPER_SOURCE_START_COLUMN}$2:${ANALYSIS_HELPER_SOURCE_END_COLUMN}"
    latest_receipts_range = f"${ANALYSIS_HELPER_LATEST_RECEIPTS_START_COLUMN}$2:${ANALYSIS_HELPER_LATEST_RECEIPTS_END_COLUMN}"
    return (
        '=IFERROR('
        'FILTER({'
        f'IF(LEN(INDEX({source_range},,33)), INDEX({source_range},,33), "{ANALYSIS_UNCATEGORIZED_LABEL}"),'
        f'N(INDEX({source_range},,36)),'
        f'INDEX({source_range},,11)&"|"&INDEX({source_range},,1),'
        f'INDEX({source_range},,11)'
        '},'
        f'INDEX({source_range},,30)="line_item",'
        f'ISNUMBER(MATCH(INDEX({source_range},,11)&"|"&INDEX({source_range},,1), INDEX({latest_receipts_range},,6), 0))'
        '),'
        '{"",0,"",""}'
        ')'
    )


def _build_receipt_totals_formula() -> str:
    latest_receipts_range = f"${ANALYSIS_HELPER_LATEST_RECEIPTS_START_COLUMN}$2:${ANALYSIS_HELPER_LATEST_RECEIPTS_END_COLUMN}"
    active_line_items_range = f"${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_START_COLUMN}$2:${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_END_COLUMN}"
    return (
        "=IFERROR("
        "FILTER({"
        f"INDEX({latest_receipts_range},,1),"
        f'IF(LEN(INDEX({latest_receipts_range},,3)), INDEX({latest_receipts_range},,3), "{ANALYSIS_UNKNOWN_MERCHANT_LABEL}"),'
        f"INDEX({latest_receipts_range},,4),"
        "IF("
        f"LEN(INDEX({latest_receipts_range},,5)),"
        f"N(INDEX({latest_receipts_range},,5)),"
        "IFNA("
        "VLOOKUP("
        f"INDEX({latest_receipts_range},,6),"
        f"QUERY({active_line_items_range}, \"select Col3, sum(Col2) where Col3 is not null group by Col3 label sum(Col2) ''\", 0),"
        "2,"
        "FALSE"
        "),"
        "0"
        ")"
        ")"
        f"}}, LEN(INDEX({latest_receipts_range},,1))),"
        f'{{"","{ANALYSIS_UNKNOWN_MERCHANT_LABEL}","",0}}'
        ")"
    )


def _build_active_categories_formula(category_sheet_name: str) -> str:
    quoted_sheet_name = _quote_sheet_name(category_sheet_name)
    return (
        "=IFERROR(FILTER({"
        f"{quoted_sheet_name}!A2:A,"
        f"{quoted_sheet_name}!B2:B"
        "},"
        f"LEN({quoted_sheet_name}!A2:A),"
        f"IF(LEN({quoted_sheet_name}!C2:C), NOT(REGEXMATCH(LOWER(TO_TEXT({quoted_sheet_name}!C2:C)), \"false|0|no|inactive\")), TRUE)"
        "),"
        "{\"\",\"\"})"
    )


def _build_category_rollup_formula() -> str:
    active_line_items_range = f"${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_START_COLUMN}$2:${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_END_COLUMN}"
    return (
        "=IFERROR(LET("
        f"categories, SORT(UNIQUE(FILTER(INDEX({active_line_items_range},,1), LEN(INDEX({active_line_items_range},,1))))),"
        "{"
        "categories,"
        f"MAP(categories, LAMBDA(category_name, SUMIF(INDEX({active_line_items_range},,1), category_name, INDEX({active_line_items_range},,2)))),"
        f"MAP(categories, LAMBDA(category_name, COUNTIF(INDEX({active_line_items_range},,1), category_name))),"
        f"MAP(categories, LAMBDA(category_name, IF(COUNTIF(INDEX({active_line_items_range},,1), category_name), COUNTUNIQUE(FILTER(INDEX({active_line_items_range},,4), INDEX({active_line_items_range},,1)=category_name)), 0)))"
        "}"
        "), "
        "{\"\",0,0,0})"
    )


def _build_month_reference_formula(source_sheet_names: list[str]) -> str:
    month_keys: list[str] = []
    for sheet_name in source_sheet_names:
        if not _is_year_sheet_name(sheet_name):
            continue
        month_keys.extend(f"{sheet_name}-{month:02d}" for month in range(1, 13))
    if not month_keys:
        return '={""}'
    return "={" + ";".join(f'"{month_key}"' for month_key in month_keys) + "}"


def _build_month_rollup_formula() -> str:
    receipt_totals_range = f"${ANALYSIS_HELPER_RECEIPT_TOTALS_START_COLUMN}$2:${ANALYSIS_HELPER_RECEIPT_TOTALS_END_COLUMN}"
    month_key_range = f'TEXT({_build_sheet_date_value_formula(receipt_totals_range, 3)}, "yyyy-mm")'
    return (
        "=IFERROR(LET("
        f"months, FILTER(${ANALYSIS_HELPER_MONTH_REFERENCE_START_COLUMN}$2:${ANALYSIS_HELPER_MONTH_REFERENCE_START_COLUMN}, LEN(${ANALYSIS_HELPER_MONTH_REFERENCE_START_COLUMN}$2:${ANALYSIS_HELPER_MONTH_REFERENCE_START_COLUMN})),"
        f"amounts, INDEX({receipt_totals_range},,4),"
        f"merchants, INDEX({receipt_totals_range},,2),"
        "{"
        "months,"
        f"MAP(months, LAMBDA(month_key, IFERROR(SUM(FILTER(amounts, {month_key_range}=month_key)), 0))),"
        f"MAP(months, LAMBDA(month_key, IFERROR(COUNTA(FILTER(amounts, {month_key_range}=month_key)), 0))),"
        f"MAP(months, LAMBDA(month_key, IFERROR(AVERAGE(FILTER(amounts, {month_key_range}=month_key)), 0))),"
        f"MAP(months, LAMBDA(month_key, IFERROR(COUNTUNIQUE(FILTER(merchants, {month_key_range}=month_key)), 0)))"
        "}"
        "), "
        "{\"\",0,0,0,0})"
    )


def _build_category_analysis_formula() -> str:
    category_reference_range = f"${ANALYSIS_HELPER_CATEGORY_REFERENCE_START_COLUMN}$2:${ANALYSIS_HELPER_CATEGORY_REFERENCE_END_COLUMN}"
    category_rollup_range = f"${ANALYSIS_HELPER_CATEGORY_ROLLUP_START_COLUMN}$2:${ANALYSIS_HELPER_CATEGORY_ROLLUP_END_COLUMN}"
    active_line_item_category_range = f"${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_START_COLUMN}$2:${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_START_COLUMN}"
    active_line_item_amount_column = _column_letter(ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_COLUMN_INDEX + 1)
    active_line_item_amount_range = f"${active_line_item_amount_column}$2:${active_line_item_amount_column}"
    item_months_range = f"${ANALYSIS_HELPER_ITEM_MONTHS_START_COLUMN}$2:${ANALYSIS_HELPER_ITEM_MONTHS_START_COLUMN}"
    fallback_row = ",".join(
        [
            f'"{ANALYSIS_NO_CATEGORY_DATA_LABEL}"',
            '""',
            *["0" for _ in range(ANALYSIS_CATEGORY_MONTH_COLUMN_COUNT)],
            "0",
            "0",
            "0",
            f'"{ANALYSIS_UNUSED_LABEL}"',
        ]
    )
    return (
        "=IFERROR(LET("
        f"categories, FILTER(INDEX({category_reference_range},,1), LEN(INDEX({category_reference_range},,1))),"
        f"descriptions, FILTER(INDEX({category_reference_range},,2), LEN(INDEX({category_reference_range},,1))),"
        f"amounts, {active_line_item_amount_range},"
        f"itemCategories, {active_line_item_category_range},"
        f"itemMonths, {item_months_range},"
        "monthlyBreakdown, MAKEARRAY("
        "ROWS(categories),"
        f"{ANALYSIS_CATEGORY_MONTH_COLUMN_COUNT},"
        "LAMBDA(rowIndex, monthIndex, "
        "IFERROR("
        'SUMIFS(amounts, itemCategories, INDEX(categories, rowIndex), itemMonths, "*-"&TEXT(monthIndex, "00")),'
        "0"
        ")"
        ")),"
        "totals, MAP(categories, LAMBDA(category_name, IFNA(VLOOKUP(category_name, "
        f"{category_rollup_range}, 2, FALSE), 0))),"
        "lineItems, MAP(categories, LAMBDA(category_name, IFNA(VLOOKUP(category_name, "
        f"{category_rollup_range}, 3, FALSE), 0))),"
        "receipts, MAP(categories, LAMBDA(category_name, IFNA(VLOOKUP(category_name, "
        f"{category_rollup_range}, 4, FALSE), 0))),"
        "statuses, MAP(receipts, LAMBDA(receiptCount, "
        f'IF(receiptCount>0, "{ANALYSIS_USED_LABEL}", "{ANALYSIS_UNUSED_LABEL}"))),'
        "data, HSTACK(categories, descriptions, monthlyBreakdown, totals, lineItems, receipts, statuses),"
        f"SORT(data, {ANALYSIS_CATEGORY_TOTAL_COLUMN_INDEX}, FALSE, 1, TRUE)"
        "), "
        "{"
        f"{fallback_row}"
        "})"
    )


def _build_merchant_analysis_formula() -> str:
    receipt_totals_range = f"${ANALYSIS_HELPER_RECEIPT_TOTALS_START_COLUMN}$2:${ANALYSIS_HELPER_RECEIPT_TOTALS_END_COLUMN}"
    return (
        "=IFERROR(QUERY(FILTER({"
        f"INDEX({receipt_totals_range},,2),"
        f"INDEX({receipt_totals_range},,4)"
        "},"
        f"LEN(INDEX({receipt_totals_range},,1))), "
        "\"select Col1, sum(Col2), count(Col2) where Col1 is not null "
        "group by Col1 order by sum(Col2) desc label Col1 '', sum(Col2) '', count(Col2) ''\", 0), "
        f'{{"{ANALYSIS_NO_MERCHANT_DATA_LABEL}",0,0}})'
    )


def _build_month_timeline_formula() -> str:
    month_reference_range = f"${ANALYSIS_HELPER_MONTH_REFERENCE_START_COLUMN}$2:${ANALYSIS_HELPER_MONTH_REFERENCE_START_COLUMN}"
    month_rollup_range = f"${ANALYSIS_HELPER_MONTH_ROLLUP_START_COLUMN}$2:${ANALYSIS_HELPER_MONTH_ROLLUP_END_COLUMN}"
    return (
        "=IFERROR(FILTER({"
        f"{month_reference_range},"
        f"IFNA(VLOOKUP({month_reference_range}, {month_rollup_range}, 2, FALSE), 0),"
        f"IFNA(VLOOKUP({month_reference_range}, {month_rollup_range}, 3, FALSE), 0),"
        f"IFNA(VLOOKUP({month_reference_range}, {month_rollup_range}, 4, FALSE), 0),"
        f"IFNA(VLOOKUP({month_reference_range}, {month_rollup_range}, 5, FALSE), 0)"
        "}, LEN("
        f"{month_reference_range})), "
        f'{{"{ANALYSIS_NO_MONTH_DATA_LABEL}",0,0,0,0}})'
    )


def _build_month_trend_sparkline_formula() -> str:
    month_rollup_range = f"${ANALYSIS_HELPER_MONTH_ROLLUP_START_COLUMN}$2:${ANALYSIS_HELPER_MONTH_ROLLUP_END_COLUMN}"
    return (
        "=IFERROR(SPARKLINE("
        f"FILTER(INDEX({month_rollup_range},,2), LEN(INDEX({month_rollup_range},,1))), "
        "{\"charttype\",\"column\";\"color\",\"#1D6F57\";\"empty\",\"zero\"}), \"\")"
    )


def _build_receipt_month_lookup_formula() -> str:
    latest_receipts_range = f"${ANALYSIS_HELPER_LATEST_RECEIPTS_START_COLUMN}$2:${ANALYSIS_HELPER_LATEST_RECEIPTS_END_COLUMN}"
    return (
        "=IFERROR(HSTACK("
        f"INDEX({latest_receipts_range},,1), "
        f'MAP(INDEX({latest_receipts_range},,4), LAMBDA(receiptDate, TEXT(IF(ISNUMBER(receiptDate), receiptDate, DATEVALUE(LEFT(TO_TEXT(receiptDate), 10))), "yyyy-mm")))'
        '), {"",""})'
    )


def _build_item_months_formula() -> str:
    active_line_items_range = f"${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_START_COLUMN}$2:${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_END_COLUMN}"
    receipt_month_lookup_range = (
        f"${ANALYSIS_HELPER_RECEIPT_MONTH_LOOKUP_START_COLUMN}$2:${ANALYSIS_HELPER_RECEIPT_MONTH_LOOKUP_END_COLUMN}"
    )
    return (
        "=IFERROR(MAP("
        f"INDEX({active_line_items_range},,4), "
        "LAMBDA(attachmentName, "
        f'IFNA(XLOOKUP(attachmentName, INDEX({receipt_month_lookup_range},,1), INDEX({receipt_month_lookup_range},,2)), "")))'
        ', {""})'
    )


def _build_category_month_matrix_formula() -> str:
    active_line_item_category_range = f"${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_START_COLUMN}$2:${ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_START_COLUMN}"
    active_line_item_amount_column = _column_letter(ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_COLUMN_INDEX + 1)
    active_line_item_amount_range = f"${active_line_item_amount_column}$2:${active_line_item_amount_column}"
    item_months_range = f"${ANALYSIS_HELPER_ITEM_MONTHS_START_COLUMN}$2:${ANALYSIS_HELPER_ITEM_MONTHS_START_COLUMN}"
    visible_category_range = f"$A$10:$A${ANALYSIS_MONTHLY_CATEGORY_TIMELINE_TITLE_ROW_NUMBER - 1}"
    visible_month_range = f"${ANALYSIS_HELPER_MONTH_REFERENCE_START_COLUMN}$2:${ANALYSIS_HELPER_MONTH_REFERENCE_START_COLUMN}"
    return (
        "=IFERROR(LET("
        f'categories, FILTER({visible_category_range}, LEN({visible_category_range}), {visible_category_range}<>"{ANALYSIS_NO_CATEGORY_DATA_LABEL}"), '
        f'months, FILTER({visible_month_range}, LEN({visible_month_range}), {visible_month_range}<>"{ANALYSIS_NO_MONTH_DATA_LABEL}"), '
        f"amounts, {active_line_item_amount_range}, "
        f"itemCategories, {active_line_item_category_range}, "
        f"itemMonths, {item_months_range}, "
        f'headerRow, HSTACK("{ANALYSIS_MONTH_HEADER_LABEL}", TRANSPOSE(categories)), '
        "body, MAKEARRAY(ROWS(months), ROWS(categories)+1, "
        "LAMBDA(rowIndex, columnIndex, "
        "IF(columnIndex=1, "
        "INDEX(months, rowIndex), "
        "IFERROR(SUMIFS(amounts, itemMonths, INDEX(months, rowIndex), itemCategories, INDEX(categories, columnIndex-1)), 0)"
        "))), "
        "VSTACK(headerRow, body)"
        "), "
        f'{{"{ANALYSIS_MONTH_HEADER_LABEL}",0}})'
    )


def _build_analysis_dashboard_chart_requests(
    *,
    sheet_id: int,
    category_timeline_series_count: int,
    category_timeline_row_count: int,
) -> list[dict[str, object]]:
    return [
        _build_basic_chart_request(
            sheet_id=sheet_id,
            title=ANALYSIS_CATEGORY_CHART_TITLE,
            chart_type="BAR",
            domain_start_column=0,
            domain_end_column=1,
            series_start_column=ANALYSIS_CATEGORY_TOTAL_COLUMN_INDEX - 1,
            series_end_column=ANALYSIS_CATEGORY_TOTAL_COLUMN_INDEX,
            start_row_index=9,
            end_row_index=21,
            anchor_row_index=12,
            anchor_column_index=0,
            width_pixels=520,
            height_pixels=280,
            bottom_axis_title=ANALYSIS_TOTAL_AMOUNT_HEADER_LABEL,
            left_axis_title=ANALYSIS_CATEGORY_HEADER_LABEL,
            series_palette=[ANALYSIS_THEME_FOREST],
        ),
        _build_basic_chart_request(
            sheet_id=sheet_id,
            title=ANALYSIS_MERCHANT_CHART_TITLE,
            chart_type="BAR",
            domain_start_column=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX - 1,
            domain_end_column=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX,
            series_start_column=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX,
            series_end_column=ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 1,
            start_row_index=9,
            end_row_index=21,
            anchor_row_index=12,
            anchor_column_index=20,
            width_pixels=520,
            height_pixels=280,
            bottom_axis_title=ANALYSIS_RECEIPT_TOTAL_LABEL,
            left_axis_title=ANALYSIS_MERCHANT_HEADER_LABEL,
            series_palette=[ANALYSIS_THEME_TERRACOTTA],
        ),
        _build_basic_chart_request(
            sheet_id=sheet_id,
            title=ANALYSIS_MONTHLY_CHART_TITLE,
            chart_type="COLUMN",
            domain_start_column=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX - 1,
            domain_end_column=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX,
            series_start_column=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX,
            series_end_column=ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 1,
            start_row_index=9,
            end_row_index=200,
            anchor_row_index=32,
            anchor_column_index=0,
            width_pixels=1040,
            height_pixels=320,
            bottom_axis_title=ANALYSIS_MONTH_HEADER_LABEL,
            left_axis_title=ANALYSIS_RECEIPT_TOTAL_LABEL,
            series_palette=[ANALYSIS_THEME_AMBER],
        ),
        _build_basic_chart_request(
            sheet_id=sheet_id,
            title=ANALYSIS_CATEGORY_TIMELINE_CHART_TITLE,
            chart_type="COLUMN",
            domain_start_column=ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX - 1,
            domain_end_column=ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX,
            series_start_column=ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX,
            series_end_column=ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX + 1,
            series_column_ranges=[
                (
                    ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX + offset,
                    ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX + offset + 1,
                )
                for offset in range(category_timeline_series_count)
            ],
            start_row_index=ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER - 1,
            end_row_index=ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER - 1 + category_timeline_row_count,
            anchor_row_index=ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER + category_timeline_row_count + 2,
            anchor_column_index=0,
            width_pixels=1040,
            height_pixels=360,
            bottom_axis_title=ANALYSIS_MONTH_HEADER_LABEL,
            left_axis_title=ANALYSIS_TOTAL_AMOUNT_HEADER_LABEL,
            header_count=1,
            legend_position="RIGHT_LEGEND",
            stacked_type="STACKED",
            series_palette=ANALYSIS_CHART_SERIES_PALETTE,
        ),
    ]


def _build_basic_chart_request(
    *,
    sheet_id: int,
    title: str,
    chart_type: str,
    domain_start_column: int,
    domain_end_column: int,
    series_start_column: int,
    series_end_column: int,
    start_row_index: int,
    end_row_index: int,
    anchor_row_index: int,
    anchor_column_index: int,
    width_pixels: int,
    height_pixels: int,
    bottom_axis_title: str,
    left_axis_title: str,
    header_count: int = 0,
    legend_position: str = "NO_LEGEND",
    stacked_type: str | None = None,
    series_column_ranges: list[tuple[int, int]] | None = None,
    series_palette: list[str] | None = None,
) -> dict[str, object]:
    resolved_series_column_ranges = series_column_ranges or [(series_start_column, series_end_column)]
    resolved_palette = series_palette or ANALYSIS_CHART_SERIES_PALETTE
    basic_chart: dict[str, object] = {
        "chartType": chart_type,
        "legendPosition": legend_position,
        "headerCount": header_count,
        "axis": [
            {"position": "BOTTOM_AXIS", "title": bottom_axis_title},
            {"position": "LEFT_AXIS", "title": left_axis_title},
        ],
        "domains": [
            {
                "domain": {
                    "sourceRange": {
                        "sources": [
                            {
                                "sheetId": sheet_id,
                                "startRowIndex": start_row_index,
                                "endRowIndex": end_row_index,
                                "startColumnIndex": domain_start_column,
                                "endColumnIndex": domain_end_column,
                            }
                        ]
                    }
                }
            }
        ],
        "series": [
            {
                "series": {
                    "sourceRange": {
                        "sources": [
                            {
                                "sheetId": sheet_id,
                                "startRowIndex": start_row_index,
                                "endRowIndex": end_row_index,
                                "startColumnIndex": column_start,
                                "endColumnIndex": column_end,
                            }
                        ]
                    }
                },
                "targetAxis": "BOTTOM_AXIS" if chart_type == "BAR" else "LEFT_AXIS",
                "colorStyle": _hex_color_style(resolved_palette[series_index % len(resolved_palette)]),
            }
            for series_index, (column_start, column_end) in enumerate(resolved_series_column_ranges)
        ],
    }
    if stacked_type is not None:
        basic_chart["stackedType"] = stacked_type

    return {
        "addChart": {
            "chart": {
                "spec": {
                    "title": title,
                    "altText": title,
                    "fontName": "Noto Sans JP",
                    "backgroundColorStyle": _hex_color_style(ANALYSIS_THEME_IVORY),
                    "titleTextFormat": {
                        "foregroundColorStyle": _hex_color_style(ANALYSIS_THEME_FOREST),
                        "fontSize": 16,
                        "bold": True,
                    },
                    "basicChart": basic_chart,
                },
                "position": {
                    "overlayPosition": {
                        "anchorCell": {
                            "sheetId": sheet_id,
                            "rowIndex": anchor_row_index,
                            "columnIndex": anchor_column_index,
                        },
                        "offsetXPixels": 0,
                        "offsetYPixels": 0,
                        "widthPixels": width_pixels,
                        "heightPixels": height_pixels,
                    }
                },
            }
        }
    }


def _timestamp_now() -> str:
    return datetime.now(UTC).isoformat()


def _get_row_value(row: list[str], index: int) -> str:
    if index >= len(row):
        return ""
    return row[index] or ""


def _extract_year_from_cell(value: str) -> str | None:
    match = YEAR_PATTERN.search(value)
    if match is None:
        return None
    return match.group(1)


def _resolve_drive_folder_parts(purchase_date: str | None) -> tuple[str, str]:
    if purchase_date:
        match = YEAR_MONTH_PATTERN.search(purchase_date)
        if match is not None:
            return match.group(1), f"{int(match.group(2)):02d}"

    now = datetime.now(UTC)
    return str(now.year), f"{now.month:02d}"


def _escape_drive_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _normalize_attachment_name(value: str) -> str:
    return value.strip().casefold()


def _build_analysis_summary_metrics(receipt_rows: list[list[str]]) -> list[list[object]]:
    receipt_records = _collect_receipt_records(receipt_rows)
    total_amount = sum(record["total_amount"] for record in receipt_records.values())
    date_values = sorted(record["date_value"] for record in receipt_records.values() if record["date_value"])
    date_range = f"{date_values[0]} .. {date_values[-1]}" if date_values else "(none)"
    average_receipt_total = total_amount / len(receipt_records) if receipt_records else 0.0
    line_item_row_count = sum(
        1
        for record in receipt_records.values()
        for row in record["rows"]
        if _get_row_value(row, RECEIPT_ROW_TYPE_INDEX) == "line_item"
    )

    return [
        ["Line Item Rows", line_item_row_count],
        ["Unique Receipts", len(receipt_records)],
        ["Unique Merchants", len({record['merchant_name'] for record in receipt_records.values() if record['merchant_name']})],
        ["Date Range", date_range],
        ["Receipt Total", round(total_amount, 2)],
        ["Average Receipt Total", round(average_receipt_total, 2)],
    ]


def _build_category_analysis_rows(receipt_rows: list[list[str]]) -> list[list[object]]:
    category_totals: dict[str, dict[str, object]] = {}
    for receipt_key, record in _collect_receipt_records(receipt_rows).items():
        for row in record["rows"]:
            if _get_row_value(row, RECEIPT_ROW_TYPE_INDEX) != "line_item":
                continue
            category_name = _get_row_value(row, RECEIPT_ITEM_CATEGORY_INDEX).strip() or "(uncategorized)"
            bucket = category_totals.setdefault(
                category_name,
                {"amount": 0.0, "row_count": 0, "receipt_keys": set()},
            )
            bucket["amount"] = float(bucket["amount"]) + _parse_number(_get_row_value(row, RECEIPT_ITEM_TOTAL_PRICE_INDEX))
            bucket["row_count"] = int(bucket["row_count"]) + 1
            receipt_keys = bucket["receipt_keys"]
            if isinstance(receipt_keys, set):
                receipt_keys.add(receipt_key)

    return [
        [
            category_name,
            round(float(bucket["amount"]), 2),
            int(bucket["row_count"]),
            len(bucket["receipt_keys"]) if isinstance(bucket["receipt_keys"], set) else 0,
        ]
        for category_name, bucket in sorted(
            category_totals.items(),
            key=lambda item: (-float(item[1]["amount"]), item[0]),
        )
    ]


def _build_merchant_analysis_rows(receipt_rows: list[list[str]]) -> list[list[object]]:
    merchant_totals: dict[str, dict[str, object]] = {}
    for record in _collect_receipt_records(receipt_rows).values():
        merchant_name = record["merchant_name"] or "(unknown)"
        bucket = merchant_totals.setdefault(merchant_name, {"amount": 0.0, "count": 0})
        bucket["amount"] = float(bucket["amount"]) + float(record["total_amount"])
        bucket["count"] = int(bucket["count"]) + 1

    return [
        [merchant_name, round(float(bucket["amount"]), 2), int(bucket["count"])]
        for merchant_name, bucket in sorted(
            merchant_totals.items(),
            key=lambda item: (-float(item[1]["amount"]), item[0]),
        )
    ]


def _build_month_analysis_rows(receipt_rows: list[list[str]]) -> list[list[object]]:
    month_totals: dict[str, dict[str, object]] = {}
    for record in _collect_receipt_records(receipt_rows).values():
        month_key = _resolve_month_key(record["date_value"]) or "(unknown)"
        bucket = month_totals.setdefault(month_key, {"amount": 0.0, "count": 0})
        bucket["amount"] = float(bucket["amount"]) + float(record["total_amount"])
        bucket["count"] = int(bucket["count"]) + 1

    return [
        [month_key, round(float(bucket["amount"]), 2), int(bucket["count"])]
        for month_key, bucket in sorted(month_totals.items())
    ]


def _collect_receipt_records(receipt_rows: list[list[str]]) -> dict[str, dict[str, object]]:
    latest_receipt_versions: dict[str, dict[str, object]] = {}
    for row_index, row in enumerate(receipt_rows):
        receipt_key = _receipt_key_from_row(row)
        version_id = _receipt_revision_id(row, row_index=row_index)
        version_sort_key = _receipt_revision_sort_key(row, row_index=row_index)
        active_version = latest_receipt_versions.get(receipt_key)

        if active_version is None:
            latest_receipt_versions[receipt_key] = {
                "version_id": version_id,
                "sort_key": version_sort_key,
                "rows": [row],
            }
            continue

        if version_id == active_version["version_id"]:
            active_rows = active_version["rows"]
            if isinstance(active_rows, list):
                active_rows.append(row)
            continue

        if version_sort_key > active_version["sort_key"]:
            latest_receipt_versions[receipt_key] = {
                "version_id": version_id,
                "sort_key": version_sort_key,
                "rows": [row],
            }

    receipt_records: dict[str, dict[str, object]] = {}
    for receipt_key, version in latest_receipt_versions.items():
        rows = list(version["rows"]) if isinstance(version["rows"], list) else []
        if not rows:
            continue
        representative_row = rows[0]
        date_value = _get_row_value(representative_row, RECEIPT_PURCHASE_DATE_INDEX) or _get_row_value(
            representative_row, RECEIPT_PROCESSED_AT_INDEX
        )
        receipt_records[receipt_key] = {
            "merchant_name": _get_row_value(representative_row, RECEIPT_MERCHANT_NAME_INDEX).strip(),
            "total_amount": _resolve_receipt_total_amount(rows),
            "date_value": date_value.strip(),
            "rows": rows,
        }
    return receipt_records


def _receipt_revision_id(row: list[str], *, row_index: int) -> str:
    processed_at = _get_row_value(row, RECEIPT_PROCESSED_AT_INDEX).strip()
    if processed_at:
        return processed_at
    return f"row-{row_index}"


def _receipt_revision_sort_key(row: list[str], *, row_index: int) -> tuple[datetime, int]:
    processed_at = _get_row_value(row, RECEIPT_PROCESSED_AT_INDEX).strip()
    if not processed_at:
        return datetime.min.replace(tzinfo=UTC), row_index
    return _parse_iso_datetime(processed_at), row_index


def _resolve_receipt_total_amount(rows: list[list[str]]) -> float:
    total_cell = _get_row_value(rows[0], RECEIPT_TOTAL_INDEX).strip()
    if total_cell:
        return _parse_number(total_cell)
    return round(
        sum(
            _parse_number(_get_row_value(row, RECEIPT_ITEM_TOTAL_PRICE_INDEX))
            for row in rows
            if _get_row_value(row, RECEIPT_ROW_TYPE_INDEX) == "line_item"
        ),
        2,
    )


def _parse_iso_datetime(value: str) -> datetime:
    normalized_value = value.strip()
    if not normalized_value:
        return datetime.min.replace(tzinfo=UTC)
    try:
        parsed_value = datetime.fromisoformat(normalized_value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    if parsed_value.tzinfo is None:
        return parsed_value.replace(tzinfo=UTC)
    return parsed_value.astimezone(UTC)


def _receipt_key_from_row(row: list[str]) -> str:
    for column_name in ("attachmentName", "attachmentId", "messageId", "processedAt"):
        column_index = RECEIPT_SHEET_HEADERS.index(column_name)
        value = _get_row_value(row, column_index).strip()
        if value:
            return value
    return "receipt-row"


def _parse_number(value: str) -> float:
    normalized_value = value.strip()
    if not normalized_value:
        return 0.0
    try:
        return float(normalized_value)
    except ValueError:
        return 0.0


def _resolve_month_key(value: str) -> str | None:
    match = YEAR_MONTH_PATTERN.search(value)
    if match is None:
        return None
    return f"{match.group(1)}-{int(match.group(2)):02d}"


def _is_year_sheet_name(sheet_name: str) -> bool:
    return YEAR_PATTERN.fullmatch(sheet_name) is not None


def _is_analysis_sheet_name(sheet_name: str) -> bool:
    return sheet_name == ANALYSIS_ALL_YEARS_SHEET_NAME or sheet_name.startswith(ANALYSIS_SHEET_PREFIX)
