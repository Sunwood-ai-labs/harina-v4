from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.models import ReceiptExtraction


_TEMPLATE_DIR = Path(__file__).with_name("templates")
_RECEIPT_EXTRACTION_SCHEMA = {
    "merchant_name": "string | null",
    "merchant_phone": "string | null",
    "purchase_date": "string | null",
    "purchase_time": "string | null",
    "currency": "string | null",
    "subtotal": "number | null",
    "tax": "number | null",
    "total": "number | null",
    "payment_method": "string | null",
    "receipt_number": "string | null",
    "language": "string | null",
    "notes": "string | null",
    "confidence": "number | null",
    "raw_text": "string | null",
    "line_items": [
        {
            "name": "string | null",
            "quantity": "number | null",
            "unit_price": "number | null",
            "total_price": "number | null",
        }
    ],
}
_RECEIPT_CATEGORY_SCHEMA = {
    "line_items": [
        {
            "item_index": "integer",
            "category": "string | null",
        }
    ],
}


@lru_cache(maxsize=1)
def _prompt_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=False,
        lstrip_blocks=True,
        trim_blocks=True,
        undefined=StrictUndefined,
    )


def render_receipt_extraction_prompt(*, filename: str) -> str:
    template = _prompt_environment().get_template("receipt_extraction_prompt.j2")
    return template.render(
        filename=filename,
        schema_json=json.dumps(_RECEIPT_EXTRACTION_SCHEMA, ensure_ascii=False, indent=2),
    )


def render_receipt_categorization_prompt(
    *,
    filename: str,
    extraction: ReceiptExtraction,
    category_options: list[str] | None = None,
) -> str:
    template = _prompt_environment().get_template("receipt_categorization_prompt.j2")
    normalized_category_options = [value for value in (category_options or []) if value]
    return template.render(
        filename=filename,
        category_options=normalized_category_options,
        category_options_json=json.dumps(normalized_category_options, ensure_ascii=False, indent=2),
        receipt_json=json.dumps(_build_receipt_categorization_input(extraction), ensure_ascii=False, indent=2),
        schema_json=json.dumps(_RECEIPT_CATEGORY_SCHEMA, ensure_ascii=False, indent=2),
    )


def _build_receipt_categorization_input(extraction: ReceiptExtraction) -> dict[str, object]:
    payload = extraction.model_dump(mode="json")
    payload["line_items"] = [
        {
            "item_index": index,
            "name": item.name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total_price": item.total_price,
        }
        for index, item in enumerate(extraction.line_items, start=1)
    ]
    return payload
