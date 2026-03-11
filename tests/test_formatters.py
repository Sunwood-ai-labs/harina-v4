from pathlib import Path

from app.formatters import (
    RECEIPT_SHEET_HEADERS,
    build_drive_file_name,
    build_local_receipt_context,
    build_receipt_embed,
    build_receipt_rows,
    format_receipt_summary,
)
from app.models import ReceiptExtraction, ReceiptLineItem


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
        line_items=[
            ReceiptLineItem(name="Cabbage", quantity=1, total_price=198),
            ReceiptLineItem(name="Juice", quantity=2, unit_price=150, total_price=300),
        ],
    )


def row_to_dict(row: list[str]) -> dict[str, str]:
    return dict(zip(RECEIPT_SHEET_HEADERS, row, strict=True))


def test_build_drive_file_name_includes_merchant_and_date() -> None:
    file_name = build_drive_file_name("photo 1.jpg", sample_extraction())
    assert file_name.startswith("2026-03-11_Cafe-Harina_")


def test_format_receipt_summary_contains_expected_fields() -> None:
    summary = format_receipt_summary(sample_extraction(), "https://drive.example/file")
    assert summary == "Cafe Harina | 1100.0 JPY | 2026-03-11 | Items: 2 | Drive: https://drive.example/file"


def test_build_receipt_rows_creates_one_row_per_line_item() -> None:
    rows = build_receipt_rows(
        context=build_local_receipt_context(Path("receipt.jpg")),
        extraction=sample_extraction(),
        drive_file_id="drive-123",
        drive_file_url="https://drive.example/file/drive-123",
    )

    assert len(rows) == 2

    first_row = row_to_dict(rows[0])
    second_row = row_to_dict(rows[1])

    assert first_row["merchantName"] == "Cafe Harina"
    assert first_row["lineItemsCount"] == "2"
    assert first_row["rowType"] == "line_item"
    assert first_row["itemIndex"] == "1"
    assert first_row["itemName"] == "Cabbage"
    assert first_row["itemTotalPrice"] == "198.0"

    assert second_row["itemIndex"] == "2"
    assert second_row["itemName"] == "Juice"
    assert second_row["itemQuantity"] == "2.0"
    assert second_row["itemUnitPrice"] == "150.0"
    assert second_row["itemTotalPrice"] == "300.0"


def test_build_receipt_embed_includes_line_items_and_drive_link() -> None:
    embed = build_receipt_embed(
        title="Receipt",
        extraction=sample_extraction(),
        drive_file_url="https://drive.example/file",
        source_label="receipt.jpg",
    )

    assert embed.title == "Receipt"
    assert embed.description == "Cafe Harina | 1100.0 JPY | 2026-03-11 | Items: 2"
    assert any(field.name == "Drive" and field.value == "https://drive.example/file" for field in embed.fields)
    assert any(field.name == "Line Items" and "Cabbage" in field.value for field in embed.fields)


def test_build_local_receipt_context_uses_cli_labels(tmp_path: Path) -> None:
    image_path = tmp_path / "receipt.jpg"
    image_path.write_bytes(b"image")

    context = build_local_receipt_context(image_path, source_name="debug-cli", author_tag="tester")

    assert context.channel_name == "debug-cli"
    assert context.author_tag == "tester"
    assert context.attachment_name == "receipt.jpg"
    assert context.attachment_url == str(image_path.resolve())
