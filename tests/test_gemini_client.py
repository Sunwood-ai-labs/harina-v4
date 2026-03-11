import pytest

from app.gemini_client import parse_receipt_payload


def test_parse_receipt_payload_accepts_dict() -> None:
    payload = parse_receipt_payload('{"merchant_name":"Cafe Harina","total":1100}')

    assert payload == {"merchant_name": "Cafe Harina", "total": 1100}


def test_parse_receipt_payload_unwraps_singleton_list() -> None:
    payload = parse_receipt_payload('[{"merchant_name":"Cafe Harina","total":1100}]')

    assert payload == {"merchant_name": "Cafe Harina", "total": 1100}


def test_parse_receipt_payload_rejects_non_singleton_list() -> None:
    with pytest.raises(RuntimeError, match="JSON array"):
        parse_receipt_payload('[{"merchant_name":"A"},{"merchant_name":"B"}]')
