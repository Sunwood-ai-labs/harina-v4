import asyncio

import pytest

from app.gemini_client import (
    GeminiReceiptExtractor,
    apply_line_item_categories,
    build_gemini_usage,
    is_daily_quota_exhausted_error,
    is_quota_exhausted_error,
    is_retryable_gemini_error,
    merge_gemini_usage,
    parse_receipt_category_payload,
    parse_receipt_payload,
    pricing_for_model,
)
from app.models import ReceiptCategoryInference, ReceiptExtraction, ReceiptLineItem


class _FakeResponse:
    def __init__(self, text: str, usage_metadata=None) -> None:
        self.text = text
        self.usage_metadata = usage_metadata


class _FakeUsageMetadata:
    def __init__(
        self,
        *,
        prompt_token_count: int,
        candidates_token_count: int,
        thoughts_token_count: int = 0,
        total_token_count: int | None = None,
    ) -> None:
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count
        self.thoughts_token_count = thoughts_token_count
        self.total_token_count = (
            total_token_count
            if total_token_count is not None
            else prompt_token_count + candidates_token_count + thoughts_token_count
        )


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

def test_build_gemini_usage_calculates_estimated_cost() -> None:
    usage = build_gemini_usage(
        model="gemini-3-flash-preview",
        usage_metadata=_FakeUsageMetadata(prompt_token_count=120, candidates_token_count=48, thoughts_token_count=30),
    )

    assert usage is not None
    assert usage.model == "gemini-3-flash-preview"
    assert usage.input_tokens == 120
    assert usage.output_tokens == 78
    assert usage.thinking_tokens == 30
    assert usage.total_tokens == 198
    assert usage.estimated_total_cost_usd == pytest.approx(0.000294)


def test_merge_gemini_usage_sums_request_usage() -> None:
    first = build_gemini_usage(
        model="gemini-3-flash-preview",
        usage_metadata=_FakeUsageMetadata(prompt_token_count=100, candidates_token_count=20, thoughts_token_count=10),
    )
    second = build_gemini_usage(
        model="gemini-3-flash-preview",
        usage_metadata=_FakeUsageMetadata(prompt_token_count=80, candidates_token_count=15, thoughts_token_count=5),
    )

    merged = merge_gemini_usage(first, second)

    assert merged is not None
    assert merged.request_count == 2
    assert merged.input_tokens == 180
    assert merged.output_tokens == 50
    assert merged.thinking_tokens == 15
    assert merged.total_tokens == 230
    assert merged.estimated_total_cost_usd == pytest.approx(0.00024)


def test_pricing_for_model_matches_known_prefixes() -> None:
    assert pricing_for_model("gemini-3-flash-preview") == (0.50, 3.00)
    assert pricing_for_model("gemini-2.5-flash") == (0.30, 2.50)
    assert pricing_for_model("gemini-2.5-flash-lite-preview-09-2025") == (0.10, 0.40)
    assert pricing_for_model("unknown-model") is None


def test_is_quota_exhausted_error_detects_resource_exhausted() -> None:
    assert is_quota_exhausted_error(_QuotaError()) is True
    assert is_quota_exhausted_error(RuntimeError("something else")) is False


def test_is_daily_quota_exhausted_error_detects_per_day_limit() -> None:
    assert (
        is_daily_quota_exhausted_error(
            _QuotaError("429 RESOURCE_EXHAUSTED quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier")
        )
        is True
    )
    assert is_daily_quota_exhausted_error(_QuotaError("429 RESOURCE_EXHAUSTED retry in 48 seconds")) is False


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


def test_extractor_rotates_immediately_on_daily_quota_errors() -> None:
    client_map = {
        "primary": _FakeClient(
            [_QuotaError("429 RESOURCE_EXHAUSTED quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier")]
        ),
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
    assert sleeps == []

def test_extractor_attaches_combined_usage_to_extraction() -> None:
    client_map = {
        "primary": _FakeClient(
            [
                _FakeResponse(
                    '{"merchant_name":"Cafe Harina","total":1100,"line_items":[{"name":"Tea","total_price":1100}]}',
                    usage_metadata=_FakeUsageMetadata(prompt_token_count=120, candidates_token_count=40, thoughts_token_count=20),
                ),
                _FakeResponse(
                    '{"line_items":[{"item_index":1,"category":"Food"}]}',
                    usage_metadata=_FakeUsageMetadata(prompt_token_count=60, candidates_token_count=12, thoughts_token_count=8),
                ),
            ]
        ),
    }

    extractor = GeminiReceiptExtractor(
        api_keys=["primary"],
        model="gemini-3-flash-preview",
        client_factory=lambda key: client_map[key],
    )

    result = asyncio.run(
        extractor.extract(
            image_bytes=b"receipt",
            mime_type="image/jpeg",
            filename="receipt.jpg",
            category_options=["Food"],
        )
    )

    assert result.gemini_usage is not None
    assert result.gemini_usage.model == "gemini-3-flash-preview"
    assert result.gemini_usage.request_count == 2
    assert result.gemini_usage.input_tokens == 180
    assert result.gemini_usage.output_tokens == 80
    assert result.gemini_usage.thinking_tokens == 28
    assert result.gemini_usage.total_tokens == 260
    assert result.gemini_usage.estimated_total_cost_usd == pytest.approx(0.00033)


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


def test_extractor_waits_after_all_keys_are_daily_exhausted_when_configured() -> None:
    client_map = {
        "primary": _FakeClient(
            [
                _QuotaError("429 RESOURCE_EXHAUSTED quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier"),
                _FakeResponse('{"merchant_name":"Cafe Harina","total":1100}'),
            ]
        ),
        "secondary": _FakeClient(
            [_QuotaError("429 RESOURCE_EXHAUSTED quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier")]
        ),
    }
    sleeps: list[float] = []
    wait_events: list[dict[str, object]] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    async def fake_wait_callback(event: dict[str, object]) -> None:
        wait_events.append(event)

    extractor = GeminiReceiptExtractor(
        api_keys=["primary", "secondary"],
        model="gemini-test",
        retry_delay_seconds=60,
        retry_count=5,
        exhausted_keys_retry_delay_seconds=3600,
        exhausted_keys_retry_count=1,
        client_factory=lambda key: client_map[key],
        sleep_func=fake_sleep,
        exhausted_keys_wait_callback=fake_wait_callback,
    )

    result = asyncio.run(
        extractor.extract(
            image_bytes=b"receipt",
            mime_type="image/jpeg",
            filename="receipt.jpg",
        )
    )

    assert result.merchant_name == "Cafe Harina"
    assert sleeps == [3600]
    assert wait_events == [
        {
            "request_name": "receipt extraction",
            "filename": "receipt.jpg",
            "error_kind": "quota",
            "key_count": 2,
            "retry_delay_seconds": 3600,
            "retry_cycle_attempt": 1,
            "retry_cycle_count": 1,
            "daily_quota_exhausted": True,
        }
    ]


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
