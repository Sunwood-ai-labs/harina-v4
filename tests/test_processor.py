import asyncio

from app.formatters import ReceiptRecordContext
from app.models import ReceiptExtraction
from app.processor import ReceiptProcessor


class _FakeGemini:
    def __init__(self, extraction: ReceiptExtraction) -> None:
        self.extraction = extraction
        self.calls: list[tuple[str, str]] = []

    async def extract(self, *, image_bytes: bytes, mime_type: str, filename: str) -> ReceiptExtraction:
        assert image_bytes == b"receipt-image"
        self.calls.append((mime_type, filename))
        return self.extraction


class _FakeGoogleWorkspace:
    def __init__(self) -> None:
        self.upload_calls: list[tuple[str, str, bytes]] = []
        self.rows: list[list[str]] = []

    async def ensure_receipt_sheet(self) -> None:
        return None

    async def upload_receipt_image(self, *, file_name: str, mime_type: str, image_bytes: bytes):
        self.upload_calls.append((file_name, mime_type, image_bytes))

        class _DriveFile:
            file_id = "drive-123"
            web_view_link = "https://drive.example/file/drive-123"

        return _DriveFile()

    async def append_receipt_row(self, row: list[str]) -> None:
        self.rows.append(row)


def sample_extraction() -> ReceiptExtraction:
    return ReceiptExtraction(
        merchant_name="Cafe Harina",
        purchase_date="2026-03-11",
        currency="JPY",
        total=1100,
        confidence=0.92,
    )


def test_process_receipt_can_skip_google_writes() -> None:
    gemini = _FakeGemini(sample_extraction())
    processor = ReceiptProcessor(gemini=gemini)

    result = asyncio.run(
        processor.process_receipt(
            context=ReceiptRecordContext(
                channel_name="cli",
                author_tag="harina-v4",
                attachment_name="receipt.jpg",
                attachment_url="D:/tmp/receipt.jpg",
            ),
            filename="receipt.jpg",
            mime_type="image/jpeg",
            image_bytes=b"receipt-image",
            write_to_google=False,
        )
    )

    assert gemini.calls == [("image/jpeg", "receipt.jpg")]
    assert result.drive_file_id is None
    assert result.drive_file_url is None
    assert result.google_write_performed is False
    assert result.row[4] == "cli"
    assert result.row[14] == "Cafe Harina"


def test_process_receipt_writes_to_google_when_enabled() -> None:
    workspace = _FakeGoogleWorkspace()
    processor = ReceiptProcessor(gemini=_FakeGemini(sample_extraction()), google_workspace=workspace)

    result = asyncio.run(
        processor.process_receipt(
            context=ReceiptRecordContext(
                channel_name="cli",
                author_tag="harina-v4",
                attachment_name="receipt.jpg",
                attachment_url="D:/tmp/receipt.jpg",
            ),
            filename="receipt.jpg",
            mime_type="image/jpeg",
            image_bytes=b"receipt-image",
            write_to_google=True,
        )
    )

    assert workspace.upload_calls[0][0].startswith("2026-03-11_Cafe-Harina_")
    assert workspace.rows == [result.row]
    assert result.drive_file_id == "drive-123"
    assert result.google_write_performed is True
