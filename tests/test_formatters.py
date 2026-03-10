from app.formatters import build_drive_file_name, format_receipt_summary
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
