from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


_TEMPLATE_DIR = Path(__file__).with_name("templates")
_RECEIPT_SCHEMA = {
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
            "category": "string | null",
            "quantity": "number | null",
            "unit_price": "number | null",
            "total_price": "number | null",
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


def render_receipt_extraction_prompt(*, filename: str, category_options: list[str] | None = None) -> str:
    template = _prompt_environment().get_template("receipt_extraction_prompt.j2")
    normalized_category_options = [value for value in (category_options or []) if value]
    return template.render(
        filename=filename,
        category_options=normalized_category_options,
        category_options_json=json.dumps(normalized_category_options, ensure_ascii=False, indent=2),
        schema_json=json.dumps(_RECEIPT_SCHEMA, ensure_ascii=False, indent=2),
    )
