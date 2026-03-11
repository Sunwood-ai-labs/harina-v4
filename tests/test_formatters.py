from pathlib import Path

from app.formatters import build_drive_file_name, build_local_receipt_context, format_receipt_summary
from app.models import ReceiptExtraction


def sample_extraction() -> ReceiptExtraction:
    return ReceiptExtraction(
        merchant_name="Cafe Harina",
        purchase_date="2026-03-11",
        currency="JPY",
        subtotal=1000,
        tax=100,
        total=1100,
        payment_method="VISA",
        receipt_number="12345",
        language="ja",
        confidence=0.94,
    )


def test_build_drive_file_name_includes_merchant_and_date() -> None:
    file_name = build_drive_file_name("photo 1.jpg", sample_extraction())
    assert file_name.startswith("2026-03-11_Cafe-Harina_")


def test_format_receipt_summary_contains_expected_fields() -> None:
    summary = format_receipt_summary(sample_extraction(), "https://drive.example/file")
    assert summary == "Cafe Harina | 1100.0 JPY | 2026-03-11 | Drive: https://drive.example/file"


def test_build_local_receipt_context_uses_cli_labels(tmp_path: Path) -> None:
    image_path = tmp_path / "receipt.jpg"
    image_path.write_bytes(b"image")

    context = build_local_receipt_context(image_path, source_name="debug-cli", author_tag="tester")

    assert context.channel_name == "debug-cli"
    assert context.author_tag == "tester"
    assert context.attachment_name == "receipt.jpg"
    assert context.attachment_url == str(image_path.resolve())
