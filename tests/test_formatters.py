from pathlib import Path

from app.formatters import (
    RECEIPT_SHEET_HEADERS,
    build_debug_status_embed,
    build_drive_intake_embed,
    build_drive_file_name,
    build_local_receipt_context,
    build_receipt_embed,
    build_receipt_links_view,
    build_receipt_rows,
    format_receipt_summary,
)
from app.models import ReceiptExtraction, ReceiptGeminiUsage, ReceiptLineItem


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
            ReceiptLineItem(name="Cabbage", category="野菜", quantity=1, total_price=198),
            ReceiptLineItem(name="Juice", category="飲料", quantity=2, unit_price=150, total_price=300),
        ],
    )


def row_to_dict(row: list[str]) -> dict[str, str]:
    return dict(zip(RECEIPT_SHEET_HEADERS, row, strict=True))


def test_build_drive_file_name_includes_merchant_and_date() -> None:
    file_name = build_drive_file_name("photo 1.jpg", sample_extraction())
    assert file_name.startswith("2026-03-11_Cafe-Harina_")


def test_format_receipt_summary_contains_expected_fields() -> None:
    summary = format_receipt_summary(sample_extraction(), "https://drive.example/file")
    assert summary == "Cafe Harina | 1100.0 JPY | 2026-03-11 | 商品数: 2 | Drive: https://drive.example/file"


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
    assert first_row["itemCategory"] == "野菜"
    assert first_row["itemTotalPrice"] == "198.0"

    assert second_row["itemIndex"] == "2"
    assert second_row["itemName"] == "Juice"
    assert second_row["itemCategory"] == "飲料"
    assert second_row["itemQuantity"] == "2.0"
    assert second_row["itemUnitPrice"] == "150.0"
    assert second_row["itemTotalPrice"] == "300.0"


def test_build_receipt_embed_includes_line_items_and_saved_destinations() -> None:
    embed = build_receipt_embed(
        title="Receipt",
        extraction=sample_extraction(),
        drive_file_url="https://drive.example/file",
        spreadsheet_url="https://docs.google.com/spreadsheets/d/sheet-id/edit",
        source_label="receipt.jpg",
    )

    assert embed.title == "Receipt"
    assert embed.description == "Cafe Harina | 1100.0 JPY | 2026-03-11 | 商品数: 2"
    assert any(field.name == "保存先" and "Google Drive" in field.value and "Google Sheets" in field.value for field in embed.fields)
    assert any(field.name == "カテゴリ" and "野菜: 1件" in field.value and "飲料: 1件" in field.value for field in embed.fields)
    assert any(field.name == "商品カテゴリ" and "1. Cabbage: 野菜" in field.value and "2. Juice: 飲料" in field.value for field in embed.fields)
    assert any(field.name == "明細" and "Cabbage [野菜]" in field.value for field in embed.fields)

def test_build_receipt_embed_can_include_gemini_model_and_cost() -> None:
    embed = build_receipt_embed(
        title="Drive Receipt // Alice",
        extraction=sample_extraction(),
        drive_file_url="https://drive.example/file",
        spreadsheet_url="https://docs.google.com/spreadsheets/d/sheet-id/edit",
        source_label="Alice / receipt.jpg",
        gemini_usage=ReceiptGeminiUsage(
            model="gemini-3-flash-preview",
            request_count=2,
            input_tokens=120,
            output_tokens=48,
            thinking_tokens=30,
            total_tokens=198,
            estimated_input_cost_usd=0.00006,
            estimated_output_cost_usd=0.000144,
            estimated_total_cost_usd=0.000204,
        ),
    )

    assert any(field.name == "Gemini Model" and field.value == "gemini-3-flash-preview" for field in embed.fields)
    assert any(
        field.name == "API Cost (est.)" and "$0.000204" in field.value and "req 2" in field.value
        for field in embed.fields
    )


def test_build_receipt_links_view_creates_drive_and_sheet_buttons() -> None:
    view = build_receipt_links_view(
        drive_file_url="https://drive.example/file",
        spreadsheet_url="https://docs.google.com/spreadsheets/d/sheet-id/edit",
    )

    assert view is not None
    assert [child.label for child in view.children] == ["Open Drive", "Open Sheet"]


def test_build_local_receipt_context_uses_cli_labels(tmp_path: Path) -> None:
    image_path = tmp_path / "receipt.jpg"
    image_path.write_bytes(b"image")

    context = build_local_receipt_context(image_path, source_name="debug-cli", author_tag="tester")

    assert context.channel_name == "debug-cli"
    assert context.author_tag == "tester"
    assert context.attachment_name == "receipt.jpg"
    assert context.attachment_url == str(image_path.resolve())


def test_build_debug_status_embed_contains_operational_fields() -> None:
    embed = build_debug_status_embed(
        test_prefix="[HARINA-TEST]",
        caption="debug-log-check",
        image_count=3,
        timeout_seconds=45,
    )

    assert embed.title == "デバッグログ確認"
    assert embed.description == "画像を送信し、処理スレッドからの応答を待っています。"
    assert any(field.name == "モード" and field.value == "Discord送信確認" for field in embed.fields)
    assert any(field.name == "画像数" and field.value == "3枚" for field in embed.fields)
    assert any(field.name == "待機時間" and field.value == "45秒" for field in embed.fields)
    assert all(field.name != "Trigger" for field in embed.fields)


def test_build_drive_intake_embed_contains_route_status() -> None:
    embed = build_drive_intake_embed(
        route_label="Alice",
        file_name="receipt.jpg",
        drive_file_url="https://drive.example/file/123",
        image_url="attachment://receipt.jpg",
    )

    assert embed.title == "HARINA V4 Intake // Alice"
    assert embed.description == "Google Drive watcher が新しい画像を検知し、レシート処理を開始しました。"
    assert any(field.name == "担当" and field.value == "Alice" for field in embed.fields)
    assert any(field.name == "状態" and field.value == "処理中" for field in embed.fields)
    assert all(field.name != "Drive Source" for field in embed.fields)
    assert embed.image.url == "attachment://receipt.jpg"
