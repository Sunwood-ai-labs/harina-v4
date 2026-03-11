from app.prompting import render_receipt_extraction_prompt


def test_render_receipt_extraction_prompt_mentions_filename_and_line_items() -> None:
    prompt = render_receipt_extraction_prompt(filename="receipt.jpg")

    assert "Receipt file name: receipt.jpg" in prompt
    assert "Return each purchasable product as its own entry in line_items" in prompt
    assert '"line_items"' in prompt
