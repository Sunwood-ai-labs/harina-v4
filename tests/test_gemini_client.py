import asyncio

import pytest

from app.gemini_client import (
    GeminiReceiptExtractor,
    is_quota_exhausted_error,
    is_retryable_gemini_error,
    parse_receipt_payload,
)


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

    def generate_content(self, **kwargs):
        del kwargs
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


def test_extractor_retries_transient_errors_before_succeeding() -> None:
    client_map = {
        "primary": _FakeClient([
            _ServerError(),
            _FakeResponse('{"merchant_name":"Cafe Harina","total":1100}'),
        ]),
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
