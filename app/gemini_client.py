from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from google import genai
from google.genai import types

from app.models import ReceiptExtraction
from app.prompting import render_receipt_extraction_prompt


logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 60
RETRY_COUNT = 5


def is_quota_exhausted_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True

    message = str(exc).upper()
    return "RESOURCE_EXHAUSTED" in message or "QUOTA EXCEEDED" in message


def is_retryable_gemini_error(exc: Exception) -> bool:
    if is_quota_exhausted_error(exc):
        return True

    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and status_code >= 500:
        return True

    message = str(exc).upper()
    retryable_markers = (
        "UNAVAILABLE",
        "INTERNAL",
        "TIMEOUT",
        "TIMED OUT",
        "CONNECTION RESET",
        "CONNECTION ABORTED",
        "SERVER DISCONNECTED",
        "SESSION IS CLOSED",
        "TRY AGAIN LATER",
        "EMPTY RESPONSE",
    )
    return any(marker in message for marker in retryable_markers)


class GeminiReceiptExtractor:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_keys: list[str] | None = None,
        model: str,
        retry_delay_seconds: int = RETRY_DELAY_SECONDS,
        retry_count: int = RETRY_COUNT,
        client_factory: Callable[[str], Any] | None = None,
        sleep_func: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        normalized_keys = [value.strip() for value in (api_keys or []) if value.strip()]
        if api_key and api_key.strip():
            normalized_keys.insert(0, api_key.strip())

        deduped_keys: list[str] = []
        for normalized_key in normalized_keys:
            if normalized_key not in deduped_keys:
                deduped_keys.append(normalized_key)

        if not deduped_keys:
            raise ValueError("At least one Gemini API key is required.")

        self._api_keys = deduped_keys
        self._client_factory = client_factory or (lambda key: genai.Client(api_key=key))
        self._clients = [self._client_factory(key) for key in self._api_keys]
        self._model = model
        self._retry_delay_seconds = retry_delay_seconds
        self._retry_count = retry_count
        self._sleep = sleep_func or asyncio.sleep

    async def extract(self, *, image_bytes: bytes, mime_type: str, filename: str) -> ReceiptExtraction:
        last_retryable_error: Exception | None = None

        for client_index, client in enumerate(self._clients, start=1):
            retry_failures = 0
            while True:
                try:
                    response = await asyncio.to_thread(
                        client.models.generate_content,
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
                except Exception as exc:  # noqa: BLE001
                    if not is_retryable_gemini_error(exc):
                        raise

                    last_retryable_error = exc
                    error_kind = "quota" if is_quota_exhausted_error(exc) else "transient"
                    if retry_failures >= self._retry_count:
                        if client_index < len(self._clients):
                            logger.warning(
                                "Gemini %s error remained after %s retries on key %s/%s. Rotating to the next key.",
                                error_kind,
                                self._retry_count,
                                client_index,
                                len(self._clients),
                            )
                            break
                        raise

                    retry_failures += 1
                    logger.warning(
                        "Gemini %s error on key %s/%s. Waiting %s seconds before retry %s/%s.",
                        error_kind,
                        client_index,
                        len(self._clients),
                        self._retry_delay_seconds,
                        retry_failures,
                        self._retry_count,
                    )
                    await self._sleep(self._retry_delay_seconds)

        if last_retryable_error is not None:
            raise last_retryable_error
        raise RuntimeError("Gemini extraction failed without returning a response.")


def parse_receipt_payload(response_text: str) -> dict[str, object]:
    payload = json.loads(response_text)
    if isinstance(payload, list):
        if len(payload) != 1 or not isinstance(payload[0], dict):
            raise RuntimeError("Gemini returned a JSON array instead of a single receipt object.")
        payload = payload[0]

    if not isinstance(payload, dict):
        raise RuntimeError("Gemini returned JSON that was not a receipt object.")

    return payload
