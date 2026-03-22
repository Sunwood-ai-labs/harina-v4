from typing import cast

from app.formatters import RECEIPT_SHEET_HEADERS, ReceiptRecordContext, build_receipt_rows
from app.google_workspace import (
    ANALYSIS_AUTHOR_CATEGORY_BREAKDOWN_LABEL,
    ANALYSIS_AUTHOR_CATEGORY_CHART_TITLE,
    ANALYSIS_AUTHOR_CATEGORY_CHART_ANCHOR_COLUMN_INDEX,
    ANALYSIS_AUTHOR_CATEGORY_CHART_TOP_CATEGORY_COUNT,
    ANALYSIS_AUTHOR_CATEGORY_MATRIX_COLUMN_INDEX,
    ANALYSIS_AUTHOR_CHART_ANCHOR_COLUMN_INDEX,
    ANALYSIS_AUTHOR_CHART_TITLE,
    ANALYSIS_AUTHOR_HEADER_LABEL,
    ANALYSIS_AUTHOR_SECTION_COLUMN_INDEX,
    ANALYSIS_CATEGORY_SUMMARY_SECTION_COLUMN_INDEX,
    ANALYSIS_CATEGORY_STATUS_COLUMN_INDEX,
    ANALYSIS_CATEGORY_TOTAL_COLUMN_INDEX,
    ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_COLUMN_INDEX,
    ANALYSIS_HELPER_AUTHOR_CATEGORY_CHART_SOURCE_COLUMN_INDEX,
    ANALYSIS_HELPER_AUTHOR_CATEGORY_CHART_SOURCE_START_COLUMN,
    ANALYSIS_HELPER_CATEGORY_DASHBOARD_COLUMN_INDEX,
    ANALYSIS_HELPER_CATEGORY_DASHBOARD_START_COLUMN,
    ANALYSIS_HELPER_CATEGORY_CHART_SOURCE_COLUMN_INDEX,
    ANALYSIS_HELPER_CATEGORY_CHART_SOURCE_START_COLUMN,
    ANALYSIS_HELPER_CATEGORY_REFERENCE_COLUMN_INDEX,
    ANALYSIS_HELPER_CATEGORY_REFERENCE_START_COLUMN,
    ANALYSIS_HELPER_CATEGORY_ROLLUP_COLUMN_INDEX,
    ANALYSIS_HIDDEN_START_COLUMN_INDEX,
    ANALYSIS_HELPER_ITEM_MONTHS_COLUMN_INDEX,
    ANALYSIS_HELPER_LATEST_RECEIPTS_COLUMN_INDEX,
    ANALYSIS_HELPER_MONTH_REFERENCE_COLUMN_INDEX,
    ANALYSIS_HELPER_MONTH_ROLLUP_COLUMN_INDEX,
    ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX,
    ANALYSIS_MAX_COLUMN_INDEX,
    ANALYSIS_HELPER_RECEIPT_MONTH_LOOKUP_COLUMN_INDEX,
    ANALYSIS_HELPER_RECEIPT_TOTALS_COLUMN_INDEX,
    ANALYSIS_HELPER_SOURCE_COLUMN_INDEX,
    ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX,
    ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER,
    ANALYSIS_MONTHLY_CATEGORY_TIMELINE_TITLE_ROW_NUMBER,
    ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX,
    ANALYSIS_NO_CATEGORY_DATA_LABEL,
    ANALYSIS_NO_AUTHOR_DATA_LABEL,
    ANALYSIS_UNKNOWN_AUTHOR_LABEL,
    ANALYSIS_VISIBLE_COLUMN_COUNT,
    GoogleWorkspaceClient,
    _analysis_compact_chart_anchor_row,
    _analysis_author_category_section_data_row,
    _analysis_author_category_chart_anchor_row,
    _analysis_author_category_section_title_row,
    _analysis_monthly_chart_anchor_row,
    _analysis_stacked_chart_anchor_row,
    _analysis_support_section_data_row,
    _analysis_support_section_header_row,
    _analysis_support_section_title_row,
    _estimated_category_timeline_row_count,
    _expected_category_chart_row_count,
    _expected_category_timeline_column_count,
    _resolved_analysis_hidden_start_column_index,
    _resolved_analysis_visible_column_count,
    _column_letter,
    build_analysis_sheet_rows,
)
from app.models import ReceiptExtraction, ReceiptLineItem


class _Execute:
    def __init__(self, payload: dict | None = None) -> None:
        self._payload = payload or {}

    def execute(self) -> dict:
        return self._payload


class _FakeSheetsValues:
    def __init__(self) -> None:
        self.append_calls: list[dict[str, object]] = []
        self.update_calls: list[dict[str, object]] = []
        self.clear_calls: list[dict[str, object]] = []
        self.values_by_range: dict[str, list[list[str]]] = {}

    def append(
        self,
        *,
        spreadsheetId: str,
        range: str,
        valueInputOption: str,
        insertDataOption: str,
        body: dict[str, object],
    ) -> _Execute:
        self.append_calls.append(
            {
                "spreadsheetId": spreadsheetId,
                "range": range,
                "valueInputOption": valueInputOption,
                "insertDataOption": insertDataOption,
                "body": body,
            }
        )
        return _Execute()

    def update(
        self,
        *,
        spreadsheetId: str,
        range: str,
        valueInputOption: str,
        body: dict[str, object],
    ) -> _Execute:
        self.update_calls.append(
            {
                "spreadsheetId": spreadsheetId,
                "range": range,
                "valueInputOption": valueInputOption,
                "body": body,
            }
        )
        return _Execute()

    def clear(self, *, spreadsheetId: str, range: str, body: dict[str, object]) -> _Execute:
        self.clear_calls.append({"spreadsheetId": spreadsheetId, "range": range, "body": body})
        return _Execute()

    def get(self, *, spreadsheetId: str, range: str, valueRenderOption: str | None = None) -> _Execute:
        del spreadsheetId, valueRenderOption
        return _Execute({"values": self.values_by_range.get(range, [])})


class _FakeSheetsService:
    def __init__(self) -> None:
        self.values_service = _FakeSheetsValues()
        self.sheet_names: list[str] = ["Receipts", "Categories"]
        self.batch_update_calls: list[dict[str, object]] = []

    def spreadsheets(self) -> "_FakeSheetsService":
        return self

    def values(self) -> _FakeSheetsValues:
        return self.values_service

    def get(self, *, spreadsheetId: str, fields: str) -> _Execute:
        del spreadsheetId, fields
        return _Execute({"sheets": [{"properties": {"title": sheet_name}} for sheet_name in self.sheet_names]})

    def batchUpdate(self, *, spreadsheetId: str, body: dict[str, object]) -> _Execute:
        del spreadsheetId
        self.batch_update_calls.append(body)
        for request in body.get("requests", []):
            add_sheet = request.get("addSheet")
            if add_sheet is not None:
                self.sheet_names.append(str(add_sheet["properties"]["title"]))
        return _Execute()


class _FakeDriveFiles:
    def __init__(self, *, existing_folders: dict[tuple[str, str], str] | None = None) -> None:
        self.existing_folders = dict(existing_folders or {})
        self.folder_create_calls: list[dict[str, object]] = []
        self.file_create_calls: list[dict[str, object]] = []
        self.list_calls: list[dict[str, object]] = []
        self._folder_counter = 0
        self._file_counter = 0

    def list(self, *, q: str, fields: str, pageSize: int) -> _Execute:
        self.list_calls.append({"q": q, "fields": fields, "pageSize": pageSize})
        parent_folder_id, folder_name = _parse_drive_folder_query(q)
        folder_id = self.existing_folders.get((parent_folder_id, folder_name))
        files = [{"id": folder_id, "name": folder_name}] if folder_id else []
        return _Execute({"files": files})

    def create(self, *, body: dict[str, object], fields: str, media_body=None) -> _Execute:
        del fields
        if body.get("mimeType") == "application/vnd.google-apps.folder":
            self._folder_counter += 1
            folder_id = f"folder-{self._folder_counter}"
            parent_folder_id = str(body["parents"][0])
            folder_name = str(body["name"])
            self.existing_folders[(parent_folder_id, folder_name)] = folder_id
            self.folder_create_calls.append(body)
            return _Execute({"id": folder_id})

        self._file_counter += 1
        file_id = f"file-{self._file_counter}"
        self.file_create_calls.append({"body": body, "media_body": media_body})
        return _Execute({"id": file_id, "webViewLink": f"https://drive.example/file/{file_id}"})


class _FakeDriveService:
    def __init__(self, *, existing_folders: dict[tuple[str, str], str] | None = None) -> None:
        self.files_service = _FakeDriveFiles(existing_folders=existing_folders)

    def files(self) -> _FakeDriveFiles:
        return self.files_service


def _parse_drive_folder_query(query: str) -> tuple[str, str]:
    parent_prefix = "'"
    parent_suffix = "' in parents"
    name_prefix = "name = '"
    name_suffix = "' and mimeType"
    parent_start = query.index(parent_prefix) + len(parent_prefix)
    parent_end = query.index(parent_suffix)
    name_start = query.index(name_prefix) + len(name_prefix)
    name_end = query.index(name_suffix)
    return query[parent_start:parent_end], query[name_start:name_end]


def _build_workspace_client(
    monkeypatch,
    *,
    sheet_name: str = "Receipts",
    existing_folders: dict[tuple[str, str], str] | None = None,
) -> tuple[GoogleWorkspaceClient, _FakeSheetsService, _FakeDriveService]:
    fake_sheets = _FakeSheetsService()
    fake_drive = _FakeDriveService(existing_folders=existing_folders)
    category_rows = [
        ["Food", "Meals", "TRUE"],
        ["Daily", "Supplies", "TRUE"],
        ["Pets", "Unused", "TRUE"],
    ]
    fake_sheets.values_service.values_by_range["'Categories'!A2:C"] = category_rows
    fake_sheets.values_service.values_by_range["'Categories'!A2:F"] = [row + ["", "", ""] for row in category_rows]

    def _fake_build(service_name: str, version: str, credentials, cache_discovery: bool):
        del version, credentials, cache_discovery
        if service_name == "sheets":
            return fake_sheets
        return fake_drive

    monkeypatch.setattr("app.google_workspace.build", _fake_build)

    client = GoogleWorkspaceClient(
        credentials=object(),
        drive_folder_id="drive-folder-1",
        spreadsheet_id="spreadsheet-1",
        sheet_name=sheet_name,
    )
    monkeypatch.setattr(
        client,
        "_sync_analysis_sheets_sync",
        lambda *args, **kwargs: {"updated_analysis_sheets": [], "years": [], "source_sheet_names": []},
    )
    return client, fake_sheets, fake_drive


def _build_rows(
    *,
    processed_at: str,
    purchase_date: str | None,
    attachment_name: str = "receipt.jpg",
    total: float | None = 120,
    category: str | None = "Tea",
    item_total_price: float | None = 120,
) -> list[list[str]]:
    return build_receipt_rows(
        context=ReceiptRecordContext(
            processed_at=processed_at,
            channel_name="cli",
            author_tag="tester",
            attachment_name=attachment_name,
            attachment_url=f"D:/Prj/harina-v3/tests/fixtures/{attachment_name}",
        ),
        extraction=ReceiptExtraction(
            merchant_name="Cafe Harina",
            purchase_date=purchase_date,
            total=total,
            line_items=[ReceiptLineItem(name="Tea", category=category, quantity=1, total_price=item_total_price)],
        ),
        drive_file_id="drive-file-1",
        drive_file_url="https://drive.example/file/drive-file-1",
    )


def _cell(rows: list[list[object]], row_number: int, column_number: int) -> object:
    row = rows[row_number - 1]
    if column_number - 1 >= len(row):
        return ""
    return row[column_number - 1]


def test_append_receipt_rows_uses_purchase_year_sheet(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    ensured_sheets: list[tuple[str, list[str]]] = []

    def _record_header(*, sheet_name: str, headers: list[str]) -> None:
        ensured_sheets.append((sheet_name, headers))

    monkeypatch.setattr(client, "_ensure_sheet_with_header_sync", _record_header)

    rows = _build_rows(processed_at="2026-03-15T09:30:00+00:00", purchase_date="2025-12-31")
    client._append_receipt_rows_sync(rows)

    assert ensured_sheets == [("2025", RECEIPT_SHEET_HEADERS)]
    assert fake_sheets.values_service.append_calls == [
        {
            "spreadsheetId": "spreadsheet-1",
            "range": "'2025'!A1",
            "valueInputOption": "USER_ENTERED",
            "insertDataOption": "INSERT_ROWS",
            "body": {"values": rows},
        }
    ]


def test_append_receipt_rows_falls_back_to_processed_year_when_purchase_date_missing(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    ensured_sheets: list[str] = []

    def _record_header(*, sheet_name: str, headers: list[str]) -> None:
        del headers
        ensured_sheets.append(sheet_name)

    monkeypatch.setattr(client, "_ensure_sheet_with_header_sync", _record_header)

    rows = _build_rows(processed_at="2024-01-02T03:04:05+00:00", purchase_date=None)
    client._append_receipt_rows_sync(rows)

    assert ensured_sheets == ["2024"]
    assert fake_sheets.values_service.append_calls[0]["range"] == "'2024'!A1"


def test_append_receipt_rows_groups_mixed_year_batches(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    ensured_sheets: list[str] = []

    def _record_header(*, sheet_name: str, headers: list[str]) -> None:
        del headers
        ensured_sheets.append(sheet_name)

    monkeypatch.setattr(client, "_ensure_sheet_with_header_sync", _record_header)

    rows_2025 = _build_rows(processed_at="2026-03-15T09:30:00+00:00", purchase_date="2025-05-01")
    rows_2026 = _build_rows(processed_at="2026-03-15T09:30:00+00:00", purchase_date="2026-06-01")

    client._append_receipt_rows_sync(rows_2025 + rows_2026)

    assert ensured_sheets == ["2025", "2026"]
    assert [call["range"] for call in fake_sheets.values_service.append_calls] == ["'2025'!A1", "'2026'!A1"]
    assert fake_sheets.values_service.append_calls[0]["body"] == {"values": rows_2025}
    assert fake_sheets.values_service.append_calls[1]["body"] == {"values": rows_2026}


def test_append_receipt_rows_refreshes_formula_analysis_for_touched_year(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    client._sync_analysis_sheets_sync = GoogleWorkspaceClient._sync_analysis_sheets_sync.__get__(client, GoogleWorkspaceClient)  # type: ignore[method-assign]
    analysis_write_calls: list[tuple[str, list[list[object]]]] = []
    hint_calls: list[dict[str, object]] = []

    def fake_write(*, sheet_name: str, rows: list[list[object]], **kwargs: object) -> None:
        analysis_write_calls.append((sheet_name, rows))
        hint_calls.append(kwargs)

    monkeypatch.setattr(client, "_replace_sheet_values_sync", fake_write)

    rows = _build_rows(processed_at="2026-03-15T09:30:00+00:00", purchase_date="2025-12-31")
    client._append_receipt_rows_sync(rows)

    assert "2025" in fake_sheets.sheet_names
    assert [sheet_name for sheet_name, _rows in analysis_write_calls] == ["Analysis 2025", "Analysis All Years"]
    assert _cell(analysis_write_calls[0][1], 2, ANALYSIS_HELPER_SOURCE_COLUMN_INDEX) == '=QUERY(\'2025\'!A2:AL, "select * where Col11 is not null", 0)'
    assert hint_calls[0]["category_timeline_row_count"] == _estimated_category_timeline_row_count(source_sheet_names=["2025"])


def test_resolve_receipt_sheet_name_uses_configured_year_when_row_dates_are_missing(monkeypatch) -> None:
    client, _fake_sheets, _fake_drive = _build_workspace_client(monkeypatch, sheet_name="2031")

    assert client._resolve_receipt_sheet_name([""] * len(RECEIPT_SHEET_HEADERS)) == "2031"


def test_upload_receipt_image_creates_year_and_month_folders(monkeypatch) -> None:
    client, _fake_sheets, fake_drive = _build_workspace_client(monkeypatch)

    uploaded = client._upload_receipt_image_sync(
        "receipt.jpg",
        "image/jpeg",
        b"image-bytes",
        "2026-03-11",
    )

    assert fake_drive.files_service.folder_create_calls == [
        {
            "name": "2026",
            "parents": ["drive-folder-1"],
            "mimeType": "application/vnd.google-apps.folder",
        },
        {
            "name": "03",
            "parents": ["folder-1"],
            "mimeType": "application/vnd.google-apps.folder",
        },
    ]
    assert fake_drive.files_service.file_create_calls[0]["body"] == {
        "name": "receipt.jpg",
        "parents": ["folder-2"],
    }
    assert uploaded.file_id == "file-1"
    assert uploaded.web_view_link == "https://drive.example/file/file-1"


def test_upload_receipt_image_reuses_existing_year_and_month_folders(monkeypatch) -> None:
    client, _fake_sheets, fake_drive = _build_workspace_client(
        monkeypatch,
        existing_folders={
            ("drive-folder-1", "2026"): "year-2026",
            ("year-2026", "03"): "month-03",
        },
    )

    uploaded = client._upload_receipt_image_sync(
        "receipt.jpg",
        "image/jpeg",
        b"image-bytes",
        "2026/03/11",
    )

    assert fake_drive.files_service.folder_create_calls == []
    assert fake_drive.files_service.file_create_calls[0]["body"] == {
        "name": "receipt.jpg",
        "parents": ["month-03"],
    }
    assert uploaded.file_id == "file-1"


def _disabled_test_build_analysis_sheet_rows_uses_sheet_formulas_for_all_years_scope() -> None:
    analysis_rows = build_analysis_sheet_rows(
        scope_label="All Years",
        source_sheet_names=["2025", "2026"],
    )

    assert analysis_rows[0] == ["HARINA 分析ダッシュボード"]
    assert analysis_rows[1][:6] == ["対象範囲", "全年度", "", "", "対象シート", "2025, 2026"]
    assert _cell(analysis_rows, 2, 14) == "更新日時"
    assert _cell(analysis_rows, 2, 15) == "=NOW()"
    assert _cell(analysis_rows, 3, 1) == "カテゴリ・店舗・月次のリズムを、一枚で眺めるレシートビュー"
    assert _cell(analysis_rows, 2, ANALYSIS_HELPER_SOURCE_COLUMN_INDEX) == '=QUERY({\'2025\'!A2:AL;\'2026\'!A2:AL}, "select * where Col11 is not null", 0)'
    assert "SORTN(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_LATEST_RECEIPTS_COLUMN_INDEX))
    assert "MATCH(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_COLUMN_INDEX))
    assert "VLOOKUP(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_RECEIPT_TOTALS_COLUMN_INDEX))
    assert "'Categories'!A2:A" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_CATEGORY_REFERENCE_COLUMN_INDEX))
    assert '{"2025-01";"2025-02"' in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_MONTH_REFERENCE_COLUMN_INDEX))
    assert "HSTACK(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_RECEIPT_MONTH_LOOKUP_COLUMN_INDEX))
    assert 'TEXT(IF(ISNUMBER(purchaseDate), purchaseDate, DATEVALUE(LEFT(TO_TEXT(purchaseDate), 10))), "yyyy-mm")' in str(
        _cell(analysis_rows, 2, ANALYSIS_HELPER_ITEM_MONTHS_COLUMN_INDEX)
    )
    assert str(_cell(analysis_rows, 2, 96)).startswith("=IFERROR(LET(")
    assert "topCategories" in str(_cell(analysis_rows, 2, 96))
    assert "MAKEARRAY(" in str(_cell(analysis_rows, 2, 96))
    assert str(_cell(analysis_rows, 5, 1)).startswith("=IFERROR(COUNTA(FILTER(")
    assert _cell(analysis_rows, 8, 1) == "カテゴリ分析"
    assert _cell(analysis_rows, 8, 8) == "店舗分析"
    assert _cell(analysis_rows, 8, 12) == "月次推移"
    assert _cell(analysis_rows, 8, 18) == "トレンド"
    assert _cell(analysis_rows, 9, 1) == "カテゴリ"
    assert _cell(analysis_rows, 9, 8) == "店舗"
    assert _cell(analysis_rows, 9, 12) == "年月"
    assert str(_cell(analysis_rows, 10, 1)).startswith("=IFERROR(SORT(FILTER({INDEX($CB$2:$CC")
    assert ' 4, FALSE), 0)>0, "使用中", "未使用"' in str(_cell(analysis_rows, 10, 1))
    assert str(_cell(analysis_rows, 10, 8)).startswith("=IFERROR(QUERY(FILTER({INDEX($BW$2:$BZ")
    assert str(_cell(analysis_rows, 10, 12)).startswith("=IFERROR(FILTER({$CJ$2:$CJ")
    assert str(_cell(analysis_rows, 10, 18)).startswith("=IFERROR(SPARKLINE(")


def _disabled_test_build_analysis_sheet_rows_uses_single_year_source_formula() -> None:
    analysis_rows = build_analysis_sheet_rows(
        scope_label="2025",
        source_sheet_names=["2025"],
    )

    assert analysis_rows[0] == ["HARINA 分析ダッシュボード"]
    assert analysis_rows[1][:6] == ["対象範囲", "2025", "", "", "対象シート", "2025"]
    assert _cell(analysis_rows, 2, 14) == "更新日時"
    assert _cell(analysis_rows, 3, 1) == "カテゴリ・店舗・月次のリズムを、一枚で眺めるレシートビュー"
    assert _cell(analysis_rows, 2, ANALYSIS_HELPER_SOURCE_COLUMN_INDEX) == '=QUERY(\'2025\'!A2:AL, "select * where Col11 is not null", 0)'
    assert '"2025-01"' in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_MONTH_REFERENCE_COLUMN_INDEX))
    assert "HSTACK(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_RECEIPT_MONTH_LOOKUP_COLUMN_INDEX))
    assert 'TEXT(IF(ISNUMBER(purchaseDate), purchaseDate, DATEVALUE(LEFT(TO_TEXT(purchaseDate), 10))), "yyyy-mm")' in str(
        _cell(analysis_rows, 2, ANALYSIS_HELPER_ITEM_MONTHS_COLUMN_INDEX)
    )
    assert str(_cell(analysis_rows, 2, 96)).startswith("=IFERROR(LET(")


def test_build_analysis_sheet_rows_creates_empty_template_without_year_sources() -> None:
    analysis_rows = build_analysis_sheet_rows(
        scope_label="All Years",
        source_sheet_names=[],
    )
    category_timeline_row_count = _estimated_category_timeline_row_count(source_sheet_names=[])
    support_data_row = _analysis_support_section_data_row(category_timeline_row_count=category_timeline_row_count)
    author_category_title_row = _analysis_author_category_section_title_row(
        category_timeline_row_count=category_timeline_row_count
    )
    author_category_data_row = _analysis_author_category_section_data_row(
        category_timeline_row_count=category_timeline_row_count
    )

    assert analysis_rows[1][:6] == ["対象範囲", "全年度", "", "", "対象シート", "(なし)"]
    assert _cell(analysis_rows, 3, 1) == "カテゴリ・店舗・月次のリズムを、一枚で眺めるレシートビュー"
    assert _cell(analysis_rows, 5, 1) == 0
    assert _cell(analysis_rows, 5, 5) == 0
    assert _cell(analysis_rows, 7, 5) == "(なし)"
    assert _cell(analysis_rows, 10, 1) == ""
    assert _cell(analysis_rows, support_data_row, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX) == "(店舗データなし)"
    assert _cell(analysis_rows, support_data_row, ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX + 1) == 0
    assert _cell(analysis_rows, support_data_row, ANALYSIS_AUTHOR_SECTION_COLUMN_INDEX) == "(支払者データなし)"
    assert _cell(analysis_rows, support_data_row, ANALYSIS_AUTHOR_SECTION_COLUMN_INDEX + 1) == 0
    assert _cell(analysis_rows, support_data_row, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX) == "(月次データなし)"
    assert _cell(analysis_rows, support_data_row, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX + 1) == 0
    assert _cell(analysis_rows, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER, 1) == "(月次データなし)"
    assert _cell(analysis_rows, author_category_title_row, 1) == ANALYSIS_AUTHOR_CATEGORY_BREAKDOWN_LABEL
    assert _cell(analysis_rows, author_category_data_row, 1) == "(支払者データなし)"


def test_build_analysis_sheet_rows_includes_formula_paths_for_rescan_and_total_fallback() -> None:
    analysis_rows = build_analysis_sheet_rows(
        scope_label="2025",
        source_sheet_names=["2025"],
    )
    support_data_row = _analysis_support_section_data_row(
        category_timeline_row_count=_estimated_category_timeline_row_count(source_sheet_names=["2025"])
    )
    author_category_data_row = _analysis_author_category_section_data_row(
        category_timeline_row_count=_estimated_category_timeline_row_count(source_sheet_names=["2025"])
    )

    assert "SORTN(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_LATEST_RECEIPTS_COLUMN_INDEX))
    assert "MATCH(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_ACTIVE_LINE_ITEMS_COLUMN_INDEX))
    assert "VLOOKUP(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_RECEIPT_TOTALS_COLUMN_INDEX))
    assert f'"{ANALYSIS_UNKNOWN_AUTHOR_LABEL}"' in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_RECEIPT_TOTALS_COLUMN_INDEX))
    assert "'Categories'!A2:A" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_CATEGORY_REFERENCE_COLUMN_INDEX))
    assert '"2025-01"' in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_MONTH_REFERENCE_COLUMN_INDEX))
    assert "COUNTUNIQUE(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_CATEGORY_ROLLUP_COLUMN_INDEX))
    assert "COUNTUNIQUE(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_MONTH_ROLLUP_COLUMN_INDEX))
    assert "FILTER(amounts" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_MONTH_ROLLUP_COLUMN_INDEX))
    assert "ISNUMBER(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_MONTH_ROLLUP_COLUMN_INDEX))
    assert "monthlyBreakdown" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_CATEGORY_DASHBOARD_COLUMN_INDEX))
    assert "MAKEARRAY(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_CATEGORY_DASHBOARD_COLUMN_INDEX))
    assert "SUMIFS(amounts" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_CATEGORY_DASHBOARD_COLUMN_INDEX))
    assert "ARRAY_CONSTRAIN(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_CATEGORY_CHART_SOURCE_COLUMN_INDEX))
    assert f"INDEX(${ANALYSIS_HELPER_CATEGORY_DASHBOARD_START_COLUMN}$2:" in str(
        _cell(analysis_rows, 2, ANALYSIS_HELPER_CATEGORY_CHART_SOURCE_COLUMN_INDEX)
    )
    assert "HSTACK(" in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_RECEIPT_MONTH_LOOKUP_COLUMN_INDEX))
    assert 'TEXT(IF(ISNUMBER(purchaseDate), purchaseDate, DATEVALUE(LEFT(TO_TEXT(purchaseDate), 10))), "yyyy-mm")' in str(
        _cell(analysis_rows, 2, ANALYSIS_HELPER_ITEM_MONTHS_COLUMN_INDEX)
    )
    author_category_chart_source_formula = str(
        _cell(analysis_rows, 2, ANALYSIS_HELPER_AUTHOR_CATEGORY_CHART_SOURCE_COLUMN_INDEX)
    )
    assert author_category_chart_source_formula.startswith("=IFERROR(LET(")
    assert "authorSummary" in author_category_chart_source_formula
    assert "authorNames" in author_category_chart_source_formula
    assert "categorySummary" in author_category_chart_source_formula
    assert f'ARRAY_CONSTRAIN(QUERY(categorySummary, "select Col1 label Col1 \'\'", 0), {ANALYSIS_AUTHOR_CATEGORY_CHART_TOP_CATEGORY_COUNT}, 1)' in (
        author_category_chart_source_formula
    )
    assert "topCategories" in author_category_chart_source_formula
    assert "MAKEARRAY(" in author_category_chart_source_formula
    assert "SUM(FILTER(" in author_category_chart_source_formula
    assert "MAP(" in author_category_chart_source_formula
    assert 'headerRow, HSTACK("' in author_category_chart_source_formula
    assert f"$A${author_category_data_row}:$A" in author_category_chart_source_formula
    assert f"$B${author_category_data_row}:$B" in author_category_chart_source_formula
    assert f"$C${author_category_data_row}:$C" in author_category_chart_source_formula
    assert "INDEX(authorNames, rowIndex, 1)" in author_category_chart_source_formula
    assert "INDEX(topCategories, columnIndex, 1)" in author_category_chart_source_formula
    assert "ARRAY_CONSTRAIN(" in str(_cell(analysis_rows, support_data_row, ANALYSIS_AUTHOR_SECTION_COLUMN_INDEX))
    assert "QUERY(FILTER({" in str(_cell(analysis_rows, support_data_row, ANALYSIS_AUTHOR_SECTION_COLUMN_INDEX))
    assert "INDEX(" in str(_cell(analysis_rows, support_data_row, ANALYSIS_AUTHOR_SECTION_COLUMN_INDEX))
    assert "sum(Col2)" in str(_cell(analysis_rows, support_data_row, ANALYSIS_AUTHOR_SECTION_COLUMN_INDEX))
    assert "count(Col2)" in str(_cell(analysis_rows, support_data_row, ANALYSIS_AUTHOR_SECTION_COLUMN_INDEX))
    assert str(_cell(analysis_rows, author_category_data_row, 1)).startswith("=IFERROR(QUERY(FILTER({")
    assert "group by Col1, Col2" in str(_cell(analysis_rows, author_category_data_row, 1))
    assert "sum(Col3)" in str(_cell(analysis_rows, author_category_data_row, 1))
    assert "count(Col3)" in str(_cell(analysis_rows, author_category_data_row, 1))
    assert "order by Col1 asc" in str(_cell(analysis_rows, author_category_data_row, 1))
    assert '$' in str(_cell(analysis_rows, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX))
    assert "MAKEARRAY(" in str(_cell(analysis_rows, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX))
    assert f'INDEX(${ANALYSIS_HELPER_CATEGORY_REFERENCE_START_COLUMN}$2:' in str(_cell(analysis_rows, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX))
    assert "ISNUMBER(" in str(_cell(analysis_rows, 7, 5))
    assert "count distinct" not in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_CATEGORY_ROLLUP_COLUMN_INDEX)).lower()
    assert "count distinct" not in str(_cell(analysis_rows, 2, ANALYSIS_HELPER_MONTH_ROLLUP_COLUMN_INDEX)).lower()


def test_build_analysis_sheet_rows_places_category_timeline_formula_in_visible_timeline_section() -> None:
    analysis_rows = build_analysis_sheet_rows(
        scope_label="2025",
        source_sheet_names=["2025"],
    )
    category_timeline_row_count = _estimated_category_timeline_row_count(source_sheet_names=["2025"])
    support_header_row = _analysis_support_section_header_row(category_timeline_row_count=category_timeline_row_count)
    author_category_title_row = _analysis_author_category_section_title_row(
        category_timeline_row_count=category_timeline_row_count
    )

    assert _cell(analysis_rows, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_TITLE_ROW_NUMBER, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX) == "カテゴリ別月次"
    assert _cell(analysis_rows, support_header_row, ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX) == "年月"
    assert str(_cell(analysis_rows, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX)).startswith("=IFERROR(LET(")
    assert _cell(analysis_rows, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX + 1) == ""
    assert _cell(analysis_rows, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER + 1, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX + 1) == ""
    assert _cell(analysis_rows, support_header_row, ANALYSIS_AUTHOR_SECTION_COLUMN_INDEX) == ANALYSIS_AUTHOR_HEADER_LABEL
    assert _cell(analysis_rows, author_category_title_row, 1) == ANALYSIS_AUTHOR_CATEGORY_BREAKDOWN_LABEL


def test_build_analysis_sheet_rows_zero_fills_blank_category_month_cells() -> None:
    analysis_rows = build_analysis_sheet_rows(
        scope_label="2025",
        source_sheet_names=["2025"],
    )

    timeline_formula = str(_cell(analysis_rows, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_START_ROW_NUMBER, ANALYSIS_MONTHLY_CATEGORY_TIMELINE_COLUMN_INDEX))
    assert timeline_formula.startswith("=IFERROR(LET(")
    assert f'INDEX(${ANALYSIS_HELPER_CATEGORY_REFERENCE_START_COLUMN}$2:' in timeline_formula
    assert f'FILTER(INDEX(${ANALYSIS_HELPER_CATEGORY_REFERENCE_START_COLUMN}$2:' in timeline_formula
    assert "MAKEARRAY(" in timeline_formula
    assert 'TRANSPOSE(categories)' in timeline_formula
    assert "SUMIFS(amounts" in timeline_formula


def test_resolve_category_timeline_shape_uses_spilled_matrix(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    fake_sheets.values_service.values_by_range["'Analysis 2025'!A9:D200"] = [
        ["年月", "Food", "Daily", "Pets"],
        ["2025-01", 10, 0, 0],
    ]

    assert client._resolve_category_timeline_shape_sync(sheet_name="Analysis 2025") == (4, 2)


def test_resolve_category_timeline_shape_stops_before_lower_sections(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    fake_sheets.values_service.values_by_range["'Analysis 2025'!A9:D200"] = [
        ["年月", "Food", "Daily", "Pets"],
        ["2025-01", 10, 0, 0],
        [],
        ["月次推移"],
        ["年月", "レシート合計"],
    ]

    assert client._resolve_category_timeline_shape_sync(sheet_name="Analysis 2025") == (4, 2)


def test_resolve_category_dashboard_row_count_uses_contiguous_helper_rows(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    support_data_row = _analysis_support_section_data_row(category_timeline_row_count=13)
    fake_sheets.values_service.values_by_range[f"'Analysis 2025'!M{support_data_row}:N{support_data_row + 17}"] = [
        ["Food", 100],
        ["Daily", 50],
        [],
        ["Pets", 0],
    ]

    assert client._resolve_category_dashboard_row_count_sync(
        sheet_name="Analysis 2025",
        category_timeline_row_count=13,
    ) == 2


def test_resolve_author_category_chart_shape_uses_contiguous_helper_rows(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    category_timeline_row_count = 13
    chart_start_row = _analysis_author_category_section_data_row(
        category_timeline_row_count=category_timeline_row_count
    )
    end_column = _column_letter(
        ANALYSIS_AUTHOR_CATEGORY_MATRIX_COLUMN_INDEX
        + ANALYSIS_AUTHOR_CATEGORY_CHART_TOP_CATEGORY_COUNT
        + 1
    )
    fake_sheets.values_service.values_by_range[
        f"'Analysis 2025'!{_column_letter(ANALYSIS_AUTHOR_CATEGORY_MATRIX_COLUMN_INDEX)}{chart_start_row}:{end_column}200"
    ] = [
        ["支払者(authorTag)", "Food", "Daily"],
        ["Alice", 100, 20],
        ["Maki", 0, 80],
        [],
        ["ignored", 1, 1],
    ]

    assert client._resolve_author_category_chart_shape_sync(
        sheet_name="Analysis 2025",
        category_timeline_row_count=category_timeline_row_count,
    ) == (3, 3)


def test_resolve_author_category_chart_shape_waits_past_placeholder(monkeypatch) -> None:
    import app.google_workspace as google_workspace_module

    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    category_timeline_row_count = 13
    responses = [
        [
            [ANALYSIS_AUTHOR_HEADER_LABEL, ANALYSIS_NO_CATEGORY_DATA_LABEL, "その他"],
            [ANALYSIS_NO_AUTHOR_DATA_LABEL, 0, 0],
        ],
        [
            [ANALYSIS_AUTHOR_HEADER_LABEL, "Food", "Daily"],
            ["Alice", 100, 20],
            ["Maki", 0, 80],
        ],
    ]

    def fake_get(*, spreadsheetId: str, range: str, valueRenderOption: str | None = None) -> _Execute:
        del spreadsheetId, range, valueRenderOption
        return _Execute({"values": responses.pop(0)})

    monkeypatch.setattr(fake_sheets.values_service, "get", fake_get)
    monkeypatch.setattr(google_workspace_module.time, "sleep", lambda _seconds: None)

    assert client._resolve_author_category_chart_shape_sync(
        sheet_name="Analysis 2025",
        category_timeline_row_count=category_timeline_row_count,
    ) == (3, 3)


def _disabled_test_wait_for_category_timeline_chart_source_sync_accepts_ready_values(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    fake_sheets.values_service.values_by_range["'Analysis 2025'!EJ2:EM3"] = [
        ["年月", "Food", "Daily", "Pets"],
        ["2025-01", 10, 0, 0],
    ]

    client._wait_for_category_timeline_chart_source_sync(sheet_name="Analysis 2025", column_count=4)


def test_apply_analysis_dashboard_layout_sync_styles_subtitle_hides_helper_columns_and_sets_row_sizes(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    visible_column_count = _resolved_analysis_visible_column_count(category_timeline_column_count=4)
    hidden_start_column_index = _resolved_analysis_hidden_start_column_index(category_timeline_column_count=4)
    support_title_row = _analysis_support_section_title_row(category_timeline_row_count=13) - 1
    support_header_row = _analysis_support_section_header_row(category_timeline_row_count=13) - 1

    client._apply_analysis_dashboard_layout_sync(sheet_id=321, category_timeline_column_count=4, category_timeline_row_count=13)

    layout_requests = fake_sheets.batch_update_calls[-1]["requests"]
    assert any(
        request.get("mergeCells", {}).get("range")
        == {
            "sheetId": 321,
            "startRowIndex": 2,
            "endRowIndex": 3,
            "startColumnIndex": 0,
            "endColumnIndex": visible_column_count,
        }
        for request in layout_requests
    )
    assert any(
        request.get("repeatCell", {}).get("range")
        == {
            "sheetId": 321,
            "startRowIndex": 1,
            "endRowIndex": 2,
            "startColumnIndex": 14,
            "endColumnIndex": 17,
        }
        and request["repeatCell"]["cell"]["userEnteredFormat"]["numberFormat"]["type"] == "DATE_TIME"
        for request in layout_requests
        if "repeatCell" in request and "numberFormat" in request["repeatCell"]["cell"]["userEnteredFormat"]
    )
    assert any(
        request.get("updateDimensionProperties", {}).get("range")
        == {"sheetId": 321, "dimension": "ROWS", "startIndex": 0, "endIndex": 1}
        and request["updateDimensionProperties"]["properties"]["pixelSize"] == 54
        for request in layout_requests
    )
    assert any(
        request.get("updateDimensionProperties", {}).get("range")
        == {
            "sheetId": 321,
            "dimension": "COLUMNS",
            "startIndex": hidden_start_column_index,
            "endIndex": ANALYSIS_MAX_COLUMN_INDEX,
        }
        and request["updateDimensionProperties"]["properties"]["hiddenByUser"] is True
        for request in layout_requests
    )
    assert any(
        request.get("repeatCell", {}).get("range")
        == {
            "sheetId": 321,
            "startRowIndex": support_title_row,
            "endRowIndex": support_title_row + 1,
            "startColumnIndex": 0,
            "endColumnIndex": 6,
        }
        and "backgroundColorStyle" in request["repeatCell"]["cell"]["userEnteredFormat"]
        for request in layout_requests
        if "repeatCell" in request
    )
    assert any(
        request.get("repeatCell", {}).get("range")
        == {
            "sheetId": 321,
            "startRowIndex": support_header_row,
            "endRowIndex": support_header_row + 1,
            "startColumnIndex": 0,
            "endColumnIndex": 6,
        }
        and "backgroundColorStyle" in request["repeatCell"]["cell"]["userEnteredFormat"]
        for request in layout_requests
        if "repeatCell" in request
    )
    assert any(
        request.get("repeatCell", {}).get("range")
        == {
            "sheetId": 321,
            "startRowIndex": _analysis_author_category_section_data_row(category_timeline_row_count=13) - 1,
            "endRowIndex": _analysis_author_category_section_data_row(category_timeline_row_count=13),
            "startColumnIndex": 0,
            "endColumnIndex": 4,
        }
        and "backgroundColorStyle" in request["repeatCell"]["cell"]["userEnteredFormat"]
        for request in layout_requests
        if "repeatCell" in request
    )
    assert any(
        request.get("updateBorders", {}).get("range")
        == {
            "sheetId": 321,
            "startRowIndex": _analysis_author_category_section_title_row(category_timeline_row_count=13) - 1,
            "endRowIndex": 200,
            "startColumnIndex": 0,
            "endColumnIndex": 4,
        }
        for request in layout_requests
    )
    assert not any(
        request.get("mergeCells", {}).get("range")
        == {
            "sheetId": 321,
            "startRowIndex": 7,
            "endRowIndex": 8,
            "startColumnIndex": 0,
            "endColumnIndex": ANALYSIS_CATEGORY_STATUS_COLUMN_INDEX,
        }
        for request in layout_requests
    )


def test_apply_analysis_dashboard_charts_creates_category_merchant_monthly_and_stacked_charts(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    monkeypatch.setattr(client, "_resolve_category_timeline_shape_sync", lambda **kwargs: (4, 13))
    monkeypatch.setattr(client, "_resolve_author_category_chart_shape_sync", lambda **kwargs: (4, 3))
    compact_chart_anchor_row = _analysis_compact_chart_anchor_row(category_timeline_row_count=13) - 1
    monthly_chart_anchor_row = _analysis_monthly_chart_anchor_row(category_timeline_row_count=13) - 1
    stacked_chart_anchor_row = _analysis_stacked_chart_anchor_row(category_timeline_row_count=13) - 1
    author_category_chart_anchor_row = _analysis_author_category_chart_anchor_row(
        category_timeline_row_count=13,
        author_category_row_count=3,
    ) - 1

    client._apply_analysis_dashboard_charts_sync(
        sheet_id=321,
        sheet_name="Analysis 2025",
        category_chart_row_count=5,
    )

    chart_requests = fake_sheets.batch_update_calls[-1]["requests"]
    assert len(chart_requests) == 6

    category_chart = chart_requests[0]["addChart"]["chart"]
    merchant_chart = chart_requests[1]["addChart"]["chart"]
    author_chart = chart_requests[2]["addChart"]["chart"]
    monthly_chart = chart_requests[3]["addChart"]["chart"]
    stacked_chart = chart_requests[4]["addChart"]["chart"]
    author_category_chart = chart_requests[5]["addChart"]["chart"]

    assert category_chart["spec"]["title"] == "カテゴリ別支出"
    assert category_chart["spec"]["altText"] == "カテゴリ別支出"
    assert category_chart["spec"]["fontName"] == "Noto Sans JP"
    assert category_chart["spec"]["basicChart"]["chartType"] == "COLUMN"
    assert category_chart["spec"]["basicChart"]["series"][0]["colorStyle"]["rgbColor"]["green"] > 0.2
    assert category_chart["position"]["overlayPosition"]["anchorCell"] == {"sheetId": 321, "rowIndex": compact_chart_anchor_row, "columnIndex": 0}
    assert category_chart["spec"]["basicChart"]["domains"][0]["domain"]["sourceRange"]["sources"][0]["startColumnIndex"] == ANALYSIS_CATEGORY_SUMMARY_SECTION_COLUMN_INDEX - 1
    assert category_chart["spec"]["basicChart"]["domains"][0]["domain"]["sourceRange"]["sources"][0]["startRowIndex"] == _analysis_support_section_data_row(category_timeline_row_count=13) - 1
    assert category_chart["spec"]["basicChart"]["domains"][0]["domain"]["sourceRange"]["sources"][0]["endRowIndex"] == _analysis_support_section_data_row(category_timeline_row_count=13) - 1 + 5
    assert category_chart["spec"]["basicChart"]["series"][0]["series"]["sourceRange"]["sources"][0]["startColumnIndex"] == ANALYSIS_CATEGORY_SUMMARY_SECTION_COLUMN_INDEX

    assert merchant_chart["spec"]["title"] == "店舗別支出"
    assert merchant_chart["spec"]["basicChart"]["chartType"] == "BAR"
    assert merchant_chart["spec"]["basicChart"]["series"][0]["colorStyle"]["rgbColor"]["red"] > 0.7
    assert merchant_chart["position"]["overlayPosition"]["anchorCell"] == {"sheetId": 321, "rowIndex": compact_chart_anchor_row, "columnIndex": 11}
    assert merchant_chart["spec"]["basicChart"]["domains"][0]["domain"]["sourceRange"]["sources"][0]["startColumnIndex"] == ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX - 1
    assert merchant_chart["spec"]["basicChart"]["series"][0]["series"]["sourceRange"]["sources"][0]["startColumnIndex"] == ANALYSIS_MERCHANT_SECTION_COLUMN_INDEX

    assert author_chart["spec"]["title"] == ANALYSIS_AUTHOR_CHART_TITLE
    assert author_chart["spec"]["basicChart"]["chartType"] == "BAR"
    assert author_chart["spec"]["basicChart"]["series"][0]["colorStyle"]["rgbColor"]["green"] > 0.3
    assert author_chart["position"]["overlayPosition"]["anchorCell"] == {
        "sheetId": 321,
        "rowIndex": compact_chart_anchor_row,
        "columnIndex": ANALYSIS_AUTHOR_CHART_ANCHOR_COLUMN_INDEX,
    }
    assert author_chart["spec"]["basicChart"]["domains"][0]["domain"]["sourceRange"]["sources"][0]["startColumnIndex"] == ANALYSIS_AUTHOR_SECTION_COLUMN_INDEX - 1
    assert author_chart["spec"]["basicChart"]["series"][0]["series"]["sourceRange"]["sources"][0]["startColumnIndex"] == ANALYSIS_AUTHOR_SECTION_COLUMN_INDEX
    assert author_chart["spec"]["basicChart"]["axis"][0]["title"] == "レシート合計"
    assert author_chart["spec"]["basicChart"]["axis"][1]["title"] == ANALYSIS_AUTHOR_HEADER_LABEL

    assert monthly_chart["spec"]["title"] == "月次支出推移"
    assert monthly_chart["spec"]["basicChart"]["chartType"] == "COLUMN"
    assert monthly_chart["spec"]["basicChart"]["series"][0]["colorStyle"]["rgbColor"]["green"] > 0.5
    assert monthly_chart["position"]["overlayPosition"]["anchorCell"] == {"sheetId": 321, "rowIndex": monthly_chart_anchor_row, "columnIndex": 0}
    assert monthly_chart["spec"]["basicChart"]["domains"][0]["domain"]["sourceRange"]["sources"][0]["startColumnIndex"] == ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX - 1
    assert monthly_chart["spec"]["basicChart"]["series"][0]["series"]["sourceRange"]["sources"][0]["startColumnIndex"] == ANALYSIS_MONTHLY_SECTION_COLUMN_INDEX
    assert monthly_chart["spec"]["basicChart"]["headerCount"] == 0

    assert stacked_chart["spec"]["title"] == "月次カテゴリ別支出"
    assert stacked_chart["spec"]["basicChart"]["chartType"] == "COLUMN"
    assert stacked_chart["spec"]["basicChart"]["stackedType"] == "STACKED"
    assert stacked_chart["spec"]["basicChart"]["legendPosition"] == "RIGHT_LEGEND"
    assert stacked_chart["spec"]["basicChart"]["headerCount"] == 1
    assert stacked_chart["position"]["overlayPosition"]["anchorCell"] == {"sheetId": 321, "rowIndex": stacked_chart_anchor_row, "columnIndex": 0}
    assert stacked_chart["spec"]["basicChart"]["domains"][0]["domain"]["sourceRange"]["sources"][0]["startColumnIndex"] == 0
    assert len(stacked_chart["spec"]["basicChart"]["series"]) == 3
    assert stacked_chart["spec"]["basicChart"]["series"][0]["series"]["sourceRange"]["sources"][0]["startColumnIndex"] == 1
    assert stacked_chart["spec"]["basicChart"]["series"][0]["series"]["sourceRange"]["sources"][0]["endColumnIndex"] == 2
    assert stacked_chart["spec"]["basicChart"]["series"][1]["colorStyle"]["rgbColor"]["red"] > 0.7

    assert author_category_chart["spec"]["title"] == ANALYSIS_AUTHOR_CATEGORY_CHART_TITLE
    assert author_category_chart["spec"]["basicChart"]["chartType"] == "BAR"
    assert author_category_chart["spec"]["basicChart"]["stackedType"] == "STACKED"
    assert author_category_chart["spec"]["basicChart"]["legendPosition"] == "RIGHT_LEGEND"
    assert author_category_chart["spec"]["basicChart"]["headerCount"] == 1
    assert author_category_chart["position"]["overlayPosition"]["anchorCell"] == {
        "sheetId": 321,
        "rowIndex": author_category_chart_anchor_row,
        "columnIndex": ANALYSIS_AUTHOR_CATEGORY_CHART_ANCHOR_COLUMN_INDEX,
    }
    assert author_category_chart["spec"]["basicChart"]["domains"][0]["domain"]["sourceRange"]["sources"][0][
        "startColumnIndex"
    ] == ANALYSIS_AUTHOR_CATEGORY_MATRIX_COLUMN_INDEX - 1
    assert len(author_category_chart["spec"]["basicChart"]["series"]) == 3
    assert author_category_chart["spec"]["basicChart"]["series"][0]["series"]["sourceRange"]["sources"][0][
        "startColumnIndex"
    ] == ANALYSIS_AUTHOR_CATEGORY_MATRIX_COLUMN_INDEX


def test_replace_sheet_values_sync_recreates_chart_requests(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    monkeypatch.setattr(client, "_recreate_analysis_sheet_sync", lambda **kwargs: 777)
    monkeypatch.setattr(client, "_resolve_category_timeline_shape_sync", lambda **kwargs: (4, 13))
    monkeypatch.setattr(client, "_resolve_author_category_chart_shape_sync", lambda **kwargs: (4, 3))
    monkeypatch.setattr(client, "_resolve_category_dashboard_row_count_sync", lambda **kwargs: 5)

    client._replace_sheet_values_sync(sheet_name="Analysis 2025", rows=[["HARINA 分析ダッシュボード"]])

    assert fake_sheets.values_service.update_calls[0]["range"] == "'Analysis 2025'!A1"
    chart_requests = fake_sheets.batch_update_calls[-1]["requests"]
    assert [request["addChart"]["chart"]["spec"]["title"] for request in chart_requests] == [
        "カテゴリ別支出",
        "店舗別支出",
        "支払者別支出",
        "月次支出推移",
        "月次カテゴリ別支出",
        ANALYSIS_AUTHOR_CATEGORY_CHART_TITLE,
    ]


def test_sync_analysis_sheets_updates_year_and_all_years_tabs(monkeypatch) -> None:
    client, _fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    client._sync_analysis_sheets_sync = GoogleWorkspaceClient._sync_analysis_sheets_sync.__get__(client, GoogleWorkspaceClient)  # type: ignore[method-assign]
    monkeypatch.setattr(client, "_list_receipt_sheet_names_sync", lambda: ["2025", "2026", "Receipts"])
    monkeypatch.setattr(client, "_list_receipt_categories_sync", lambda: ["Food", "Daily", "Pets"])

    write_calls: list[tuple[str, list[list[object]]]] = []
    hint_calls: list[dict[str, object]] = []

    def fake_write(*, sheet_name: str, rows: list[list[object]], **kwargs: object) -> None:
        write_calls.append((sheet_name, rows))
        hint_calls.append(kwargs)

    monkeypatch.setattr(client, "_replace_sheet_values_sync", fake_write)

    summary = client._sync_analysis_sheets_sync(["2025"], include_all_years=True)

    assert summary["updated_analysis_sheets"] == ["Analysis 2025", "Analysis All Years"]
    assert summary["source_sheet_names"] == ["2025", "2026"]
    assert summary["missing_years"] == []
    assert write_calls[0][0] == "Analysis 2025"
    assert write_calls[0][1][0] == ["HARINA 分析ダッシュボード"]
    assert _cell(write_calls[0][1], 2, ANALYSIS_HELPER_SOURCE_COLUMN_INDEX) == '=QUERY(\'2025\'!A2:AL, "select * where Col11 is not null", 0)'
    assert write_calls[1][0] == "Analysis All Years"
    assert write_calls[1][1][0] == ["HARINA 分析ダッシュボード"]
    assert _cell(write_calls[1][1], 2, ANALYSIS_HELPER_SOURCE_COLUMN_INDEX) == '=QUERY({\'2025\'!A2:AL;\'2026\'!A2:AL}, "select * where Col11 is not null", 0)'
    assert hint_calls[0]["category_timeline_column_count"] == _expected_category_timeline_column_count(3)
    assert hint_calls[0]["category_timeline_row_count"] == _estimated_category_timeline_row_count(source_sheet_names=["2025"])
    assert hint_calls[0]["category_chart_row_count"] == _expected_category_chart_row_count(3)
    assert hint_calls[1]["category_timeline_column_count"] == _expected_category_timeline_column_count(3)
    assert hint_calls[1]["category_timeline_row_count"] == _estimated_category_timeline_row_count(
        source_sheet_names=["2025", "2026"]
    )
    assert hint_calls[1]["category_chart_row_count"] == _expected_category_chart_row_count(3)


def test_sync_analysis_sheets_reports_missing_years_without_creating_empty_analysis(monkeypatch) -> None:
    client, _fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    client._sync_analysis_sheets_sync = GoogleWorkspaceClient._sync_analysis_sheets_sync.__get__(client, GoogleWorkspaceClient)  # type: ignore[method-assign]
    monkeypatch.setattr(client, "_list_receipt_sheet_names_sync", lambda: ["2025", "Receipts"])
    monkeypatch.setattr(client, "_list_receipt_categories_sync", lambda: ["Food", "Daily"])

    write_calls: list[str] = []

    def fake_write(*, sheet_name: str, rows: list[list[object]], **kwargs: object) -> None:
        del rows
        del kwargs
        write_calls.append(sheet_name)

    monkeypatch.setattr(client, "_replace_sheet_values_sync", fake_write)

    summary = client._sync_analysis_sheets_sync(["2025", "2027"], include_all_years=False)

    assert summary["years"] == ["2025"]
    assert summary["missing_years"] == ["2027"]
    assert summary["updated_analysis_sheets"] == ["Analysis 2025"]
    assert write_calls == ["Analysis 2025"]


def test_sync_analysis_sheets_creates_empty_all_years_when_no_year_tabs_exist(monkeypatch) -> None:
    client, _fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    client._sync_analysis_sheets_sync = GoogleWorkspaceClient._sync_analysis_sheets_sync.__get__(client, GoogleWorkspaceClient)  # type: ignore[method-assign]
    monkeypatch.setattr(client, "_list_receipt_sheet_names_sync", lambda: ["Receipts"])
    monkeypatch.setattr(client, "_list_receipt_categories_sync", lambda: ["Food", "Daily"])

    write_calls: list[tuple[str, list[list[object]]]] = []
    hint_calls: list[dict[str, object]] = []

    def fake_write(*, sheet_name: str, rows: list[list[object]], **kwargs: object) -> None:
        write_calls.append((sheet_name, rows))
        hint_calls.append(kwargs)

    monkeypatch.setattr(client, "_replace_sheet_values_sync", fake_write)

    summary = client._sync_analysis_sheets_sync(include_all_years=True)

    assert summary["years"] == []
    assert summary["source_sheet_names"] == []
    assert summary["updated_analysis_sheets"] == ["Analysis All Years"]
    assert write_calls[0][0] == "Analysis All Years"
    assert write_calls[0][1][1][:6] == ["対象範囲", "全年度", "", "", "対象シート", "(なし)"]
    assert hint_calls[0]["category_timeline_column_count"] == _expected_category_timeline_column_count(2)
    assert hint_calls[0]["category_timeline_row_count"] == _estimated_category_timeline_row_count(source_sheet_names=[])
    assert hint_calls[0]["category_chart_row_count"] == _expected_category_chart_row_count(2)


def test_sync_analysis_sheets_all_years_excludes_legacy_receipts_when_year_tabs_exist(monkeypatch) -> None:
    client, _fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    client._sync_analysis_sheets_sync = GoogleWorkspaceClient._sync_analysis_sheets_sync.__get__(client, GoogleWorkspaceClient)  # type: ignore[method-assign]
    monkeypatch.setattr(client, "_list_receipt_sheet_names_sync", lambda: ["2025", "Receipts"])
    monkeypatch.setattr(client, "_list_receipt_categories_sync", lambda: ["Food", "Daily"])

    write_calls: list[tuple[str, list[list[object]]]] = []
    hint_calls: list[dict[str, object]] = []

    def fake_write(*, sheet_name: str, rows: list[list[object]], **kwargs: object) -> None:
        write_calls.append((sheet_name, rows))
        hint_calls.append(kwargs)

    monkeypatch.setattr(client, "_replace_sheet_values_sync", fake_write)

    summary = client._sync_analysis_sheets_sync(["2025"], include_all_years=True)

    assert summary["source_sheet_names"] == ["2025"]
    assert write_calls[1][0] == "Analysis All Years"
    assert write_calls[1][1][1][:6] == ["対象範囲", "全年度", "", "", "対象シート", "2025"]
    assert _cell(write_calls[1][1], 2, ANALYSIS_HELPER_SOURCE_COLUMN_INDEX) == '=QUERY(\'2025\'!A2:AL, "select * where Col11 is not null", 0)'
    assert hint_calls[1]["category_timeline_column_count"] == _expected_category_timeline_column_count(2)
    assert hint_calls[1]["category_timeline_row_count"] == _estimated_category_timeline_row_count(source_sheet_names=["2025"])
    assert hint_calls[1]["category_chart_row_count"] == _expected_category_chart_row_count(2)


def test_list_receipt_sheet_names_excludes_analysis_tabs(monkeypatch) -> None:
    client, fake_sheets, _fake_drive = _build_workspace_client(monkeypatch)
    fake_sheets.sheet_names = ["Categories", "2025", "Analysis 2025", "Analysis All Years", "Receipts"]

    assert client._list_receipt_sheet_names_sync() == ["2025", "Receipts"]
