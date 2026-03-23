from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.cli import build_parser, handle_google_sync_analysis


def test_google_sync_analysis_parser_accepts_repeatable_years() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "google",
            "sync-analysis",
            "--year",
            "2025",
            "--year",
            "2026",
            "--skip-all-years",
        ]
    )

    assert args.command == "google"
    assert args.google_command == "sync-analysis"
    assert args.year == ["2025", "2026"]
    assert args.skip_all_years is True


def test_handle_google_sync_analysis_calls_workspace(monkeypatch, capsys) -> None:
    captured_calls: list[dict[str, object]] = []

    class _FakeWorkspace:
        def __init__(self, *, credentials, drive_folder_id: str, spreadsheet_id: str, sheet_name: str, category_sheet_name: str) -> None:
            del credentials
            captured_calls.append(
                {
                    "drive_folder_id": drive_folder_id,
                    "spreadsheet_id": spreadsheet_id,
                    "sheet_name": sheet_name,
                    "category_sheet_name": category_sheet_name,
                }
            )

        async def sync_analysis_sheets(self, *, years, include_all_years: bool) -> dict[str, object]:
            return {
                "years": years,
                "include_all_years": include_all_years,
                "updated_analysis_sheets": ["Analysis 2025", "Analysis All Years"],
            }

    monkeypatch.setattr("app.cli.GoogleWorkspaceClient", _FakeWorkspace)

    settings = SimpleNamespace(
        has_google_auth=lambda: True,
        google_credentials=object(),
        google_drive_folder_id="drive-folder-1",
        google_sheets_spreadsheet_id="spreadsheet-1",
        google_sheets_sheet_name="Receipts",
        google_sheets_category_sheet_name="Categories",
    )
    args = SimpleNamespace(year=["2025"], skip_all_years=False)

    handle_google_sync_analysis(args, settings)

    assert captured_calls == [
        {
            "drive_folder_id": "drive-folder-1",
            "spreadsheet_id": "spreadsheet-1",
            "sheet_name": "Receipts",
            "category_sheet_name": "Categories",
        }
    ]
    assert json.loads(capsys.readouterr().out) == {
        "years": ["2025"],
        "include_all_years": True,
        "updated_analysis_sheets": ["Analysis 2025", "Analysis All Years"],
    }


def test_handle_google_sync_analysis_rejects_invalid_year_values() -> None:
    settings = SimpleNamespace(
        has_google_auth=lambda: True,
        google_credentials=object(),
        google_drive_folder_id="drive-folder-1",
        google_sheets_spreadsheet_id="spreadsheet-1",
        google_sheets_sheet_name="Receipts",
        google_sheets_category_sheet_name="Categories",
    )
    args = SimpleNamespace(year=["202A"], skip_all_years=False)

    with pytest.raises(RuntimeError, match="--year must be four digits like 2025"):
        handle_google_sync_analysis(args, settings)
