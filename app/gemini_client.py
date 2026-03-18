from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from typing import Any

from google import genai
from google.genai import types

from app.category_catalog import normalize_category_name
from app.models import ReceiptCategoryInference, ReceiptExtraction, ReceiptGeminiUsage, ReceiptLineItem
from app.prompting import render_receipt_categorization_prompt, render_receipt_extraction_prompt


logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 60
RETRY_COUNT = 5
EXHAUSTED_KEYS_RETRY_DELAY_SECONDS = 0
EXHAUSTED_KEYS_RETRY_COUNT = 0
MODEL_INPUT_OUTPUT_PRICING_USD_PER_1M_TOKENS = {
    "gemini-3-flash": (0.50, 3.00),
    "gemini-3-flash-preview": (0.50, 3.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}


@dataclass(slots=True)
class _JsonPayloadResult:
    payload: dict[str, object]
    usage: ReceiptGeminiUsage | None


def is_quota_exhausted_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True

    message = str(exc).upper()
    return "RESOURCE_EXHAUSTED" in message or "QUOTA EXCEEDED" in message


def is_daily_quota_exhausted_error(exc: Exception) -> bool:
    if not is_quota_exhausted_error(exc):
        return False

    message = str(exc).upper()
    daily_quota_markers = (
        "GENERATEREQUESTSPERDAYPERPROJECTPERMODEL-FREETIER",
        "PERDAY",
        "PER DAY",
        "REQUESTS PER DAY",
        "DAILY",
        "RPD",
    )
    return any(marker in message for marker in daily_quota_markers)


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
        exhausted_keys_retry_delay_seconds: int = EXHAUSTED_KEYS_RETRY_DELAY_SECONDS,
        exhausted_keys_retry_count: int = EXHAUSTED_KEYS_RETRY_COUNT,
        client_factory: Callable[[str], Any] | None = None,
        sleep_func: Callable[[float], Awaitable[None]] | None = None,
        exhausted_keys_wait_callback: Callable[[dict[str, object]], Awaitable[None]] | None = None,
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
        self._exhausted_keys_retry_delay_seconds = exhausted_keys_retry_delay_seconds
        self._exhausted_keys_retry_count = exhausted_keys_retry_count
        self._sleep = sleep_func or asyncio.sleep
        self._exhausted_keys_wait_callback = exhausted_keys_wait_callback

    async def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        filename: str,
        category_options: list[str] | None = None,
    ) -> ReceiptExtraction:
        extraction_result = await self._generate_json_payload(
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                render_receipt_extraction_prompt(filename=filename),
            ],
            parse_func=parse_receipt_payload,
            request_name="receipt extraction",
            temperature=0.1,
            filename=filename,
        )
        extraction = ReceiptExtraction.model_validate(extraction_result.payload)
        extraction.gemini_usage = extraction_result.usage

        if not any(item.has_meaningful_data() for item in extraction.line_items):
            return extraction

        category_result = await self._generate_json_payload(
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                render_receipt_categorization_prompt(
                    filename=filename,
                    extraction=extraction,
                    category_options=category_options,
                ),
            ],
            parse_func=parse_receipt_category_payload,
            request_name="receipt categorization",
            temperature=0.0,
            filename=filename,
        )
        category_inference = ReceiptCategoryInference.model_validate(category_result.payload)
        combined_extraction = apply_line_item_categories(extraction, category_inference)
        combined_extraction.gemini_usage = merge_gemini_usage(extraction_result.usage, category_result.usage)
        return combined_extraction

    async def _generate_json_payload(
        self,
        *,
        contents: list[object],
        parse_func: Callable[[str], dict[str, object]],
        request_name: str,
        temperature: float,
        filename: str,
    ) -> _JsonPayloadResult:
        last_retryable_error: Exception | None = None
        exhausted_keys_retry_attempts = 0

        while True:
            should_restart_from_first_key = False

            for client_index, client in enumerate(self._clients, start=1):
                retry_failures = 0
                while True:
                    try:
                        response = await asyncio.to_thread(
                            client.models.generate_content,
                            model=self._model,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                temperature=temperature,
                                response_mime_type="application/json",
                            ),
                        )
                        if not response.text:
                            raise RuntimeError("Gemini returned an empty response.")

                        return _JsonPayloadResult(
                            payload=parse_func(response.text),
                            usage=build_gemini_usage(
                                model=self._model,
                                usage_metadata=getattr(response, "usage_metadata", None),
                            ),
                        )
                    except Exception as exc:  # noqa: BLE001
                        if not is_retryable_gemini_error(exc):
                            raise

                        last_retryable_error = exc
                        error_kind = "quota" if is_quota_exhausted_error(exc) else "transient"
                        daily_quota_exhausted = is_daily_quota_exhausted_error(exc)

                        if daily_quota_exhausted:
                            if client_index < len(self._clients):
                                logger.warning(
                                    "Gemini daily quota exhausted during %s on key %s/%s. Rotating to the next key without local retries.",
                                    request_name,
                                    client_index,
                                    len(self._clients),
                                )
                                break

                            if exhausted_keys_retry_attempts >= self._exhausted_keys_retry_count:
                                raise

                            exhausted_keys_retry_attempts += 1
                            logger.warning(
                                "Gemini daily quota exhausted after exhausting all %s key(s) during %s. Waiting %s seconds before retry cycle %s/%s from the first key.",
                                len(self._clients),
                                request_name,
                                self._exhausted_keys_retry_delay_seconds,
                                exhausted_keys_retry_attempts,
                                self._exhausted_keys_retry_count,
                            )
                            await self._notify_exhausted_keys_wait(
                                request_name=request_name,
                                filename=filename,
                                error_kind=error_kind,
                                key_count=len(self._clients),
                                retry_delay_seconds=self._exhausted_keys_retry_delay_seconds,
                                retry_cycle_attempt=exhausted_keys_retry_attempts,
                                retry_cycle_count=self._exhausted_keys_retry_count,
                                daily_quota_exhausted=True,
                            )
                            await self._sleep(self._exhausted_keys_retry_delay_seconds)
                            should_restart_from_first_key = True
                            break

                        if retry_failures >= self._retry_count:
                            if client_index < len(self._clients):
                                logger.warning(
                                    "Gemini %s error remained after %s retries during %s on key %s/%s. Rotating to the next key.",
                                    error_kind,
                                    self._retry_count,
                                    request_name,
                                    client_index,
                                    len(self._clients),
                                )
                                break

                            if exhausted_keys_retry_attempts >= self._exhausted_keys_retry_count:
                                raise

                            exhausted_keys_retry_attempts += 1
                            logger.warning(
                                "Gemini %s error remained after exhausting all %s key(s) during %s. Waiting %s seconds before retry cycle %s/%s from the first key.",
                                error_kind,
                                len(self._clients),
                                request_name,
                                self._exhausted_keys_retry_delay_seconds,
                                exhausted_keys_retry_attempts,
                                self._exhausted_keys_retry_count,
                            )
                            await self._notify_exhausted_keys_wait(
                                request_name=request_name,
                                filename=filename,
                                error_kind=error_kind,
                                key_count=len(self._clients),
                                retry_delay_seconds=self._exhausted_keys_retry_delay_seconds,
                                retry_cycle_attempt=exhausted_keys_retry_attempts,
                                retry_cycle_count=self._exhausted_keys_retry_count,
                                daily_quota_exhausted=False,
                            )
                            await self._sleep(self._exhausted_keys_retry_delay_seconds)
                            should_restart_from_first_key = True
                            break

                        retry_failures += 1
                        logger.warning(
                            "Gemini %s error during %s on key %s/%s. Waiting %s seconds before retry %s/%s.",
                            error_kind,
                            request_name,
                            client_index,
                            len(self._clients),
                            self._retry_delay_seconds,
                            retry_failures,
                            self._retry_count,
                        )
                        await self._sleep(self._retry_delay_seconds)

                if should_restart_from_first_key:
                    break

            if should_restart_from_first_key:
                continue
            break

        if last_retryable_error is not None:
            raise last_retryable_error
        raise RuntimeError("Gemini extraction failed without returning a response.")

    async def _notify_exhausted_keys_wait(
        self,
        *,
        request_name: str,
        filename: str,
        error_kind: str,
        key_count: int,
        retry_delay_seconds: int,
        retry_cycle_attempt: int,
        retry_cycle_count: int,
        daily_quota_exhausted: bool,
    ) -> None:
        if self._exhausted_keys_wait_callback is None:
            return

        try:
            await self._exhausted_keys_wait_callback(
                {
                    "request_name": request_name,
                    "filename": filename,
                    "error_kind": error_kind,
                    "key_count": key_count,
                    "retry_delay_seconds": retry_delay_seconds,
                    "retry_cycle_attempt": retry_cycle_attempt,
                    "retry_cycle_count": retry_cycle_count,
                    "daily_quota_exhausted": daily_quota_exhausted,
                }
            )
        except Exception:  # noqa: BLE001
            logger.exception("Gemini wait callback failed during %s for %s", request_name, filename)


def parse_receipt_payload(response_text: str) -> dict[str, object]:
    payload = json.loads(response_text)
    if isinstance(payload, list):
        if len(payload) != 1 or not isinstance(payload[0], dict):
            raise RuntimeError("Gemini returned a JSON array instead of a single receipt object.")
        payload = payload[0]

    if not isinstance(payload, dict):
        raise RuntimeError("Gemini returned JSON that was not a receipt object.")

    return payload


def parse_receipt_category_payload(response_text: str) -> dict[str, object]:
    payload = json.loads(response_text)
    if isinstance(payload, list):
        payload = {"line_items": payload}

    if not isinstance(payload, dict):
        raise RuntimeError("Gemini returned JSON that was not a category assignment object.")

    line_items = payload.get("line_items")
    if line_items is None:
        raise RuntimeError("Gemini category response did not include line_items.")
    if not isinstance(line_items, list):
        raise RuntimeError("Gemini category response line_items was not a JSON array.")

    return payload


def apply_line_item_categories(
    extraction: ReceiptExtraction,
    category_inference: ReceiptCategoryInference,
) -> ReceiptExtraction:
    assignments = {
        assignment.item_index: normalize_category_name(assignment.category or "") or None
        for assignment in category_inference.line_items
        if assignment.item_index > 0
    }
    line_items = [
        _apply_category_to_line_item(item, assignments.get(index))
        for index, item in enumerate(extraction.line_items, start=1)
    ]
    return extraction.model_copy(update={"line_items": line_items})


def _apply_category_to_line_item(item: ReceiptLineItem, category: str | None) -> ReceiptLineItem:
    return item.model_copy(update={"category": category})


def build_gemini_usage(*, model: str, usage_metadata: object | None) -> ReceiptGeminiUsage | None:
    if usage_metadata is None:
        return None

    input_tokens = int(getattr(usage_metadata, "prompt_token_count", 0) or 0)
    candidate_tokens = int(getattr(usage_metadata, "candidates_token_count", 0) or 0)
    thinking_tokens = int(getattr(usage_metadata, "thoughts_token_count", 0) or 0)
    total_tokens = int(getattr(usage_metadata, "total_token_count", 0) or 0)
    output_tokens = candidate_tokens + thinking_tokens

    input_cost_usd: float | None = None
    output_cost_usd: float | None = None
    total_cost_usd: float | None = None
    pricing = pricing_for_model(model)
    if pricing is not None:
        input_rate_usd_per_1m, output_rate_usd_per_1m = pricing
        input_cost_usd = (input_tokens / 1_000_000) * input_rate_usd_per_1m
        output_cost_usd = (output_tokens / 1_000_000) * output_rate_usd_per_1m
        total_cost_usd = input_cost_usd + output_cost_usd

    return ReceiptGeminiUsage(
        model=model,
        request_count=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        total_tokens=total_tokens,
        estimated_input_cost_usd=input_cost_usd,
        estimated_output_cost_usd=output_cost_usd,
        estimated_total_cost_usd=total_cost_usd,
    )


def merge_gemini_usage(*usages: ReceiptGeminiUsage | None) -> ReceiptGeminiUsage | None:
    present_usages = [usage for usage in usages if usage is not None]
    if not present_usages:
        return None

    model = present_usages[0].model
    total_input_cost_usd: float | None = 0.0
    total_output_cost_usd: float | None = 0.0
    total_cost_usd: float | None = 0.0
    if any(usage.estimated_total_cost_usd is None for usage in present_usages):
        total_input_cost_usd = None
        total_output_cost_usd = None
        total_cost_usd = None
    else:
        total_input_cost_usd = sum(usage.estimated_input_cost_usd or 0.0 for usage in present_usages)
        total_output_cost_usd = sum(usage.estimated_output_cost_usd or 0.0 for usage in present_usages)
        total_cost_usd = sum(usage.estimated_total_cost_usd or 0.0 for usage in present_usages)

    return ReceiptGeminiUsage(
        model=model,
        request_count=sum(usage.request_count for usage in present_usages),
        input_tokens=sum(usage.input_tokens for usage in present_usages),
        output_tokens=sum(usage.output_tokens for usage in present_usages),
        thinking_tokens=sum(usage.thinking_tokens for usage in present_usages),
        total_tokens=sum(usage.total_tokens for usage in present_usages),
        estimated_input_cost_usd=total_input_cost_usd,
        estimated_output_cost_usd=total_output_cost_usd,
        estimated_total_cost_usd=total_cost_usd,
    )


def pricing_for_model(model: str) -> tuple[float, float] | None:
    normalized_model = model.strip().lower()
    for prefix, pricing in sorted(
        MODEL_INPUT_OUTPUT_PRICING_USD_PER_1M_TOKENS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if normalized_model == prefix or normalized_model.startswith(f"{prefix}-"):
            return pricing
    return None
