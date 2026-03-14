from app.models import ReceiptExtraction, ReceiptLineItem
from app.prompting import (
    render_receipt_categorization_prompt,
    render_receipt_extraction_prompt,
)


def test_render_receipt_extraction_prompt_mentions_filename_and_excludes_categories() -> None:
    prompt = render_receipt_extraction_prompt(filename="receipt.jpg")

    assert "Receipt file name: receipt.jpg" in prompt
    assert "Return each purchasable product as its own entry in line_items" in prompt
    assert "Do not assign categories in this stage." in prompt
    assert '"line_items"' in prompt
    assert '"category"' not in prompt


def test_render_receipt_categorization_prompt_mentions_candidates_and_item_indexes() -> None:
    prompt = render_receipt_categorization_prompt(
        filename="receipt.jpg",
        extraction=ReceiptExtraction(
            merchant_name="Cafe Harina",
            line_items=[
                ReceiptLineItem(name="Cabbage", quantity=1, total_price=198),
                ReceiptLineItem(name="Juice", quantity=2, total_price=300),
            ],
        ),
        category_options=["野菜", "飲料"],
    )

    assert "Receipt file name: receipt.jpg" in prompt
    assert "Choose categories from this pre-approved list whenever possible" in prompt
    assert "single-word category names" in prompt
    assert '"野菜"' in prompt
    assert '"item_index"' in prompt
    assert '"category"' in prompt
    assert '"name": "Cabbage"' in prompt
