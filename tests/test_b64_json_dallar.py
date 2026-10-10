"""sester.adapters._b64_json dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (base64/json saf, dis cagri YOK).
HTTP `X-Facilitator-<PREFIX> <urlsafe-b64-json>` zarf parser'i.
"""
import base64
import json

import pytest

from sester.adapters import _b64_json, AdapterError


def b64(payload) -> str:
    if isinstance(payload, str):
        payload = payload.encode()
    return base64.urlsafe_b64encode(payload).decode()


# -- mutlu-yol ---------------------------------------------------------------------------------

def test_valid_json_object():
    tok = b64(json.dumps({"a": 1}))
    assert _b64_json(f"PREFIX {tok}", "PREFIX") == {"a": 1}


def test_valid_json_array():
    tok = b64(json.dumps([1, 2]))
    assert _b64_json(f"P {tok}", "P") == [1, 2]


def test_valid_json_string():
    tok = b64(json.dumps("merhaba"))
    assert _b64_json(f"P {tok}", "P") == "merhaba"


def test_returns_dict_or_any():
    tok = b64(json.dumps({"x": "y"}))
    r = _b64_json(f"P {tok}", "P")
    assert isinstance(r, dict) and r["x"] == "y"


def test_json_number():
    tok = b64(json.dumps(42))
    assert _b64_json(f"P {tok}", "P") == 42


def test_json_bool_null():
    tok = b64(json.dumps(None))
    assert _b64_json(f"P {tok}", "P") is None


# -- prefix ---------------------------------------------------------------------------------

def test_missing_prefix_raises():
    with pytest.raises(AdapterError, match="öneki"):
        _b64_json("OTHER " + b64("{}"), "PREFIX")


def test_prefix_without_space_raises():
    with pytest.raises(AdapterError):
        _b64_json("PREFIX" + b64("{}"), "PREFIX")


def test_empty_header_raises():
    with pytest.raises(AdapterError):
        _b64_json("", "P")


def test_prefix_only_raises():
    with pytest.raises(AdapterError):
        _b64_json("PREFIX", "PREFIX")


def test_case_sensitive_prefix():
    with pytest.raises(AdapterError):
        _b64_json("prefix " + b64("{}"), "PREFIX")


def test_prefix_exact_match():
    tok = b64("{}")
    assert _b64_json(f"AB {tok}", "AB") == {}


def test_prefix_with_digit():
    tok = b64("{}")
    assert _b64_json(f"X1 {tok}", "X1") == {}


def test_prefix_is_substr_not_token():
    """'PRE' prefix 'PREFIX ...' ile baslar ama 'PRE ' degil."""
    with pytest.raises(AdapterError):
        _b64_json("PREFIX " + b64("{}"), "PRE")


# -- strip ---------------------------------------------------------------------------------

def test_leading_whitespace_stripped():
    tok = b64(json.dumps({"a": 1}))
    assert _b64_json(f"   P {tok}", "P") == {"a": 1}


def test_trailing_whitespace_stripped():
    tok = b64(json.dumps({"a": 1}))
    assert _b64_json(f"P {tok}   ", "P") == {"a": 1}


def test_both_sides_whitespace():
    tok = b64("{}")
    assert _b64_json(f"  P {tok} ", "P") == {}


def test_inner_space_tolerated():
    """ORTAM: ikinci bosluk base64-decode'da YOK-SAYILIR (padding-bosluk)."""
    tok = b64("{}")
    assert _b64_json(f"P  {tok}", "P") == {}


# -- padding ---------------------------------------------------------------------------------

def test_no_padding_urlsafe():
    """urlsafe-b64 padding'i '-'/'_' ile: _-ve-=."""
    tok = base64.urlsafe_b64encode(b'{"a":1}').decode().rstrip("=")
    assert _b64_json(f"P {tok}", "P") == {"a": 1}


def test_padding_readded_1():
    raw = b64('{"a":1}').rstrip("=")
    assert _b64_json(f"P {raw}", "P") == {"a": 1}


def test_padding_readded_2():
    raw = b64('{"ab":12}').rstrip("=")
    assert _b64_json(f"P {raw}", "P") == {"ab": 12}


def test_padding_readded_0():
    raw = b64('{"abc":123}').rstrip("=")
    assert _b64_json(f"P {raw}", "P") == {"abc": 123}


def test_standard_b64_also_works():
    """urlsafe_b64decode '-'/'_' de kabul eder."""
    tok = base64.b64encode(b'{"a":1}').decode()
    assert _b64_json(f"P {tok}", "P") == {"a": 1}


def test_urlsafe_chars():
    tok = b64(json.dumps({"u": 255}))
    assert _b64_json(f"P {tok}", "P") == {"u": 255}


# -- hata-dallari ---------------------------------------------------------------------------------

def test_invalid_base64_raises():
    with pytest.raises(AdapterError, match="bozuk"):
        _b64_json("P !!!", "P")


def test_invalid_json_raises():
    with pytest.raises(AdapterError, match="bozuk"):
        _b64_json("P " + b64("{not-closed"), "P")


def test_empty_payload_prefix_error():
    """'P ' -> strip 'P' -> startswith('P ') DEGIL -> prefix hatasi."""
    with pytest.raises(AdapterError, match="öneki"):
        _b64_json("P ", "P")


def test_json_not_b64_raises():
    with pytest.raises(AdapterError):
        _b64_json("P {a:1}", "P")


def test_error_message_includes_detail():
    with pytest.raises(AdapterError) as exc:
        _b64_json("P !!!", "P")
    assert "bozuk" in str(exc.value)


def test_prefix_error_message_includes_prefix():
    with pytest.raises(AdapterError) as exc:
        _b64_json("X y", "PREFIX")
    assert "PREFIX" in str(exc.value)


# -- unicode ---------------------------------------------------------------------------------

def test_turkish_payload():
    tok = b64(json.dumps({"ad": "Gökhan", "sehir": "İstanbul"}))
    assert _b64_json(f"P {tok}", "P") == {"ad": "Gökhan", "sehir": "İstanbul"}


def test_emoji_payload():
    tok = b64(json.dumps("😀"))
    assert _b64_json(f"P {tok}", "P") == "😀"


def test_nested_unicode():
    payload = {"tr": ["ç", "ğ", "ı", "ö", "ş", "ü"]}
    tok = b64(json.dumps(payload))
    assert _b64_json(f"P {tok}", "P") == payload


# -- buyuk-payload ---------------------------------------------------------------------------------

def test_large_payload():
    payload = {"k": "x" * 5000}
    tok = b64(json.dumps(payload))
    assert _b64_json(f"P {tok}", "P") == payload


def test_deep_nested():
    payload = {"a": {"b": {"c": {"d": {"e": 1}}}}}
    tok = b64(json.dumps(payload))
    assert _b64_json(f"P {tok}", "P") == payload


# -- tekrar ---------------------------------------------------------------------------------

def test_repeatable():
    tok = b64(json.dumps({"a": 1}))
    assert _b64_json(f"P {tok}", "P") == _b64_json(f"P {tok}", "P")


def test_independent_calls():
    tok = b64("{}")
    assert _b64_json(f"P {tok}", "P") == {} and _b64_json(f"P {tok}", "P") == {}


def test_different_prefixes_same_payload():
    tok = b64(json.dumps({"a": 1}))
    assert _b64_json(f"A {tok}", "A") == _b64_json(f"B {tok}", "B")


# -- cesitli-tipler ---------------------------------------------------------------------------------

@pytest.mark.parametrize("v", [
    {}, [], "str", 0, 1, -1, 3.14, True, False, None,
    {"nested": {"deep": [1, 2, 3]}},
])
def test_roundtrip_types(v):
    tok = b64(json.dumps(v))
    assert _b64_json(f"P {tok}", "P") == v


def test_empty_object():
    assert _b64_json("P " + b64("{}"), "P") == {}


def test_empty_array():
    assert _b64_json("P " + b64("[]"), "P") == []


def test_empty_string_payload():
    assert _b64_json("P " + b64('""'), "P") == ""
