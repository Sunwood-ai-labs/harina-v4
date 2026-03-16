import asyncio

import pytest

from app.gemini_client import (
    GeminiReceiptExtractor,
    apply_line_item_categories,
    is_quota_exhausted_error,
    is_retryable_gemini_error,
    parse_receipt_category_payload,
    parse_receipt_payload,
)
from app.models import ReceiptCategoryInference, ReceiptExtraction, ReceiptLineItem


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _QuotaError(Exception):
    def __init__(self, message: str = "429 RESOURCE_EXHAUSTED") -> None:
        super().__init__(message)
        self.status_code = 429


class _ServerError(Exception):
    def __init__(self, message: str = "503 UNAVAILABLE") -> None:
        super().__init__(message)
        self.status_code = 503


class _FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeClient:
    def __init__(self, outcomes):
        self.models = _FakeModels(outcomes)


def test_parse_receipt_payload_accepts_dict() -> None:
    payload = parse_receipt_payload('{"merchant_name":"Cafe Harina","total":1100}')

    assert payload == {"merchant_name": "Cafe Harina", "total": 1100}


def test_parse_receipt_payload_unwraps_singleton_list() -> None:
    payload = parse_receipt_payload('[{"merchant_name":"Cafe Harina","total":1100}]')

    assert payload == {"merchant_name": "Cafe Harina", "total": 1100}


def test_parse_receipt_payload_rejects_non_singleton_list() -> None:
    with pytest.raises(RuntimeError, match="JSON array"):
        parse_receipt_payload('[{"merchant_name":"A"},{"merchant_name":"B"}]')


def test_parse_receipt_category_payload_accepts_array_payload() -> None:
    payload = parse_receipt_category_payload('[{"item_index":1,"category":"飲料"}]')

    assert payload == {"line_items": [{"item_index": 1, "category": "飲料"}]}


def test_parse_receipt_category_payload_requires_line_items() -> None:
    with pytest.raises(RuntimeError, match="line_items"):
        parse_receipt_category_payload('{"category":"飲料"}')


def test_apply_line_item_categories_merges_by_item_index_and_normalizes_names() -> None:
    extraction = ReceiptExtraction(
        line_items=[
            ReceiptLineItem(name="Cabbage", quantity=1, total_price=198),
            ReceiptLineItem(name="Juice", quantity=2, total_price=300),
        ]
    )
    category_inference = ReceiptCategoryInference.model_validate(
        {
            "line_items": [
                {"item_index": 1, "category": "野菜・きのこ"},
                {"item_index": 2, "category": "飲料"},
            ]
        }
    )

    categorized = apply_line_item_categories(extraction, category_inference)

    assert categorized.line_items[0].category == "野菜"
    assert categorized.line_items[1].category == "飲料"


def test_is_quota_exhausted_error_detects_resource_exhausted() -> None:
    assert is_quota_exhausted_error(_QuotaError()) is True
    assert is_quota_exhausted_error(RuntimeError("something else")) is False


def test_is_retryable_gemini_error_detects_transient_errors() -> None:
    assert is_retryable_gemini_error(_QuotaError()) is True
    assert is_retryable_gemini_error(_ServerError()) is True
    assert is_retryable_gemini_error(RuntimeError("Gemini returned an empty response.")) is True
    assert is_retryable_gemini_error(RuntimeError("bad request")) is False


def test_extractor_retries_and_rotates_keys_on_quota_errors() -> None:
    client_map = {
        "primary": _FakeClient([_QuotaError() for _ in range(6)]),
        "secondary": _FakeClient([_FakeResponse('{"merchant_name":"Cafe Harina","total":1100}')]),
    }
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    extractor = GeminiReceiptExtractor(
        api_keys=["primary", "secondary"],
        model="gemini-test",
        retry_delay_seconds=60,
        retry_count=5,
        client_factory=lambda key: client_map[key],
        sleep_func=fake_sleep,
    )

    result = asyncio.run(
        extractor.extract(
            image_bytes=b"receipt",
            mime_type="image/jpeg",
            filename="receipt.jpg",
        )
    )

    assert result.merchant_name == "Cafe Harina"
    assert result.total == 1100
    assert sleeps == [60, 60, 60, 60, 60]


def test_extractor_raises_after_all_rotating_keys_are_exhausted() -> None:
    client_map = {
        "primary": _FakeClient([_QuotaError() for _ in range(6)]),
        "secondary": _FakeClient([_QuotaError() for _ in range(6)]),
    }
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    extractor = GeminiReceiptExtractor(
        api_keys=["primary", "secondary"],
        model="gemini-test",
        retry_delay_seconds=60,
        retry_count=5,
        client_factory=lambda key: client_map[key],
        sleep_func=fake_sleep,
    )

    with pytest.raises(_QuotaError):
        asyncio.run(
            extractor.extract(
                image_bytes=b"receipt",
                mime_type="image/jpeg",
                filename="receipt.jpg",
            )
        )

    assert sleeps == [60] * 10


def test_extractor_waits_and_retries_again_after_all_keys_are_exhausted_when_configured() -> None:
    client_map = {
        "primary": _FakeClient(
            [_QuotaError() for _ in range(6)] + [_FakeResponse('{"merchant_name":"Cafe Harina","total":1100}')]
        ),
        "secondary": _FakeClient([_QuotaError() for _ in range(6)]),
    }
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    extractor = GeminiReceiptExtractor(
        api_keys=["primary", "secondary"],
        model="gemini-test",
        retry_delay_seconds=60,
        retry_count=5,
        exhausted_keys_retry_delay_seconds=3600,
        exhausted_keys_retry_count=1,
        client_factory=lambda key: client_map[key],
        sleep_func=fake_sleep,
    )

    result = asyncio.run(
        extractor.extract(
            image_bytes=b"receipt",
            mime_type="image/jpeg",
            filename="receipt.jpg",
        )
    )

    assert result.merchant_name == "Cafe Harina"
    assert result.total == 1100
    assert sleeps == [60] * 10 + [3600]


def test_extractor_retries_transient_errors_before_succeeding() -> None:
    client_map = {
        "primary": _FakeClient(
            [
                _ServerError(),
                _FakeResponse('{"merchant_name":"Cafe Harina","total":1100}'),
            ]
        ),
    }
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    extractor = GeminiReceiptExtractor(
        api_keys=["primary"],
        model="gemini-test",
        retry_delay_seconds=60,
        retry_count=5,
        client_factory=lambda key: client_map[key],
        sleep_func=fake_sleep,
    )

    result = asyncio.run(
        extractor.extract(
            image_bytes=b"receipt",
            mime_type="image/jpeg",
            filename="receipt.jpg",
        )
    )

    assert result.merchant_name == "Cafe Harina"
    assert sleeps == [60]


def test_extractor_runs_categorization_stage_with_category_options() -> None:
    client = _FakeClient(
        [
            _FakeResponse(
                (
                    '{"merchant_name":"Cafe Harina","total":1100,'
                    '"line_items":[{"name":"Cabbage","quantity":1,"total_price":198}]}'
                )
            ),
            _FakeResponse('{"line_items":[{"item_index":1,"category":"野菜"}]}'),
        ]
    )
    extractor = GeminiReceiptExtractor(
        api_keys=["primary"],
        model="gemini-test",
        client_factory=lambda _key: client,
    )

    result = asyncio.run(
        extractor.extract(
            image_bytes=b"receipt",
            mime_type="image/jpeg",
            filename="receipt.jpg",
            category_options=["野菜", "飲料"],
        )
    )

    assert result.line_items[0].category == "野菜"
    assert len(client.models.calls) == 2
    extraction_prompt = client.models.calls[0]["contents"][1]
    categorization_prompt = client.models.calls[1]["contents"][1]
    assert "Do not assign categories in this stage." in extraction_prompt
    assert "single-word category names" in categorization_prompt
    assert '"野菜"' in categorization_prompt
    assert '"item_index": 1' in categorization_prompt
