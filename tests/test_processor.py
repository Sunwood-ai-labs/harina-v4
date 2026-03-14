import asyncio
from pathlib import Path

from app.formatters import ReceiptRecordContext
from app.models import ReceiptExtraction, ReceiptLineItem
from app.processor import ReceiptProcessor


class _FakeGemini:
    def __init__(self, extraction: ReceiptExtraction, *, expected_image_bytes: bytes) -> None:
        self.extraction = extraction
        self.expected_image_bytes = expected_image_bytes
        self.calls: list[tuple[str, str, list[str]]] = []

    async def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        filename: str,
        category_options: list[str] | None = None,
    ) -> ReceiptExtraction:
        assert image_bytes == self.expected_image_bytes
        self.calls.append((mime_type, filename, list(category_options or [])))
        return self.extraction


class _FakeGoogleWorkspace:
    def __init__(self) -> None:
        self.upload_calls: list[tuple[str, str, bytes]] = []
        self.rows: list[list[str]] = []
        self.categories = ["野菜", "飲料"]
        self.added_categories: list[tuple[list[str], str]] = []
        self.spreadsheet_url = "https://docs.google.com/spreadsheets/d/sheet-id/edit"

    async def ensure_receipt_sheet(self) -> None:
        return None

    async def list_receipt_categories(self) -> list[str]:
        return self.categories

    async def append_receipt_categories(self, categories: list[str], *, source: str = "gemini") -> list[str]:
        self.added_categories.append((categories, source))
        return ["新カテゴリ"]

    async def upload_receipt_image(self, *, file_name: str, mime_type: str, image_bytes: bytes):
        self.upload_calls.append((file_name, mime_type, image_bytes))

        class _DriveFile:
            file_id = "drive-123"
            web_view_link = "https://drive.example/file/drive-123"

        return _DriveFile()

    async def append_receipt_rows(self, rows: list[list[str]]) -> None:
        self.rows.extend(rows)


def sample_extraction() -> ReceiptExtraction:
    return ReceiptExtraction(
        merchant_name="Cafe Harina",
        purchase_date="2026-03-11",
        currency="JPY",
        total=1100,
        confidence=0.92,
        line_items=[
            ReceiptLineItem(name="Cabbage", category="野菜", quantity=1, total_price=198),
            ReceiptLineItem(name="Juice", category="新カテゴリ", quantity=2, unit_price=150, total_price=300),
        ],
    )


def test_process_receipt_can_skip_google_writes(
    dataset_receipt_image_path: Path,
    dataset_receipt_image_bytes: bytes,
) -> None:
    gemini = _FakeGemini(sample_extraction(), expected_image_bytes=dataset_receipt_image_bytes)
    processor = ReceiptProcessor(gemini=gemini)

    result = asyncio.run(
        processor.process_receipt(
            context=ReceiptRecordContext(
                channel_name="cli",
                author_tag="harina-v4",
                attachment_name=dataset_receipt_image_path.name,
                attachment_url=str(dataset_receipt_image_path),
            ),
            filename=dataset_receipt_image_path.name,
            mime_type="image/jpeg",
            image_bytes=dataset_receipt_image_bytes,
            write_to_google=False,
        )
    )

    assert gemini.calls == [("image/jpeg", dataset_receipt_image_path.name, [])]
    assert result.drive_file_id is None
    assert result.drive_file_url is None
    assert result.spreadsheet_url is None
    assert result.google_write_performed is False
    assert len(result.rows) == 2
    assert result.row[4] == "cli"
    assert result.row[14] == "Cafe Harina"
    assert result.rows[0][31] == "Cabbage"
    assert result.rows[0][32] == "野菜"
    assert result.rows[1][31] == "Juice"
    assert result.rows[1][32] == "新カテゴリ"


def test_process_receipt_writes_to_google_when_enabled(
    dataset_receipt_image_path: Path,
    dataset_receipt_image_bytes: bytes,
) -> None:
    workspace = _FakeGoogleWorkspace()
    gemini = _FakeGemini(sample_extraction(), expected_image_bytes=dataset_receipt_image_bytes)
    processor = ReceiptProcessor(
        gemini=gemini,
        google_workspace=workspace,
    )

    result = asyncio.run(
        processor.process_receipt(
            context=ReceiptRecordContext(
                channel_name="cli",
                author_tag="harina-v4",
                attachment_name=dataset_receipt_image_path.name,
                attachment_url=str(dataset_receipt_image_path),
            ),
            filename=dataset_receipt_image_path.name,
            mime_type="image/jpeg",
            image_bytes=dataset_receipt_image_bytes,
            write_to_google=True,
        )
    )

    assert workspace.upload_calls[0][0].startswith("2026-03-11_Cafe-Harina_")
    assert workspace.rows == result.rows
    assert len(result.rows) == 2
    assert result.drive_file_id == "drive-123"
    assert result.spreadsheet_url == "https://docs.google.com/spreadsheets/d/sheet-id/edit"
    assert result.google_write_performed is True
    assert gemini.calls == [("image/jpeg", dataset_receipt_image_path.name, ["野菜", "飲料"])]
    assert workspace.added_categories == [(["野菜", "新カテゴリ"], "gemini")]
