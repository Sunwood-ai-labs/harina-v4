from __future__ import annotations

import asyncio
import json

from google import genai
from google.genai import types

from app.models import ReceiptExtraction


class GeminiReceiptExtractor:
    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._prompt = " ".join(
            [
                "You are extracting structured receipt data for bookkeeping automation.",
                "Read the receipt image and return JSON only.",
                "If a field is missing, return null instead of guessing.",
                "Use ISO 8601 date format when the date is clear.",
                "Numbers must be plain numbers without currency symbols or commas.",
                "Include line_items when they can be read confidently.",
                "Set confidence to a value between 0 and 1.",
                "Use snake_case keys matching this schema:",
                json.dumps(
                    {
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
                ),
            ]
        )

    async def extract(self, *, image_bytes: bytes, mime_type: str, filename: str) -> ReceiptExtraction:
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                f"{self._prompt}\nReceipt file name: {filename}",
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )

        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")

        return ReceiptExtraction.model_validate(parse_receipt_payload(response.text))


def parse_receipt_payload(response_text: str) -> dict[str, object]:
    payload = json.loads(response_text)
    if isinstance(payload, list):
        if len(payload) != 1 or not isinstance(payload[0], dict):
            raise RuntimeError("Gemini returned a JSON array instead of a single receipt object.")
        payload = payload[0]

    if not isinstance(payload, dict):
        raise RuntimeError("Gemini returned JSON that was not a receipt object.")

    return payload
