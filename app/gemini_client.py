from __future__ import annotations

import asyncio
import json

from google import genai
from google.genai import types

from app.models import ReceiptExtraction
from app.prompting import render_receipt_extraction_prompt


class GeminiReceiptExtractor:
    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def extract(self, *, image_bytes: bytes, mime_type: str, filename: str) -> ReceiptExtraction:
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                render_receipt_extraction_prompt(filename=filename),
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
