from app.prompting import render_receipt_extraction_prompt


def test_render_receipt_extraction_prompt_mentions_filename_and_line_items() -> None:
    prompt = render_receipt_extraction_prompt(
        filename="receipt.jpg",
        category_options=["野菜・きのこ", "飲料"],
    )

    assert "Receipt file name: receipt.jpg" in prompt
    assert "Return each purchasable product as its own entry in line_items" in prompt
    assert "Choose categories from this pre-approved list whenever possible" in prompt
    assert '"野菜・きのこ"' in prompt
    assert '"category"' in prompt
    assert '"line_items"' in prompt
