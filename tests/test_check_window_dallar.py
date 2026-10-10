"""adapters._check_window dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (time.time() monkeypatch — gercek saat YOK).
"""
import pytest

from sester.adapters import _check_window, AdapterError


def _obj(vf=None, vt=None, extra=False):
    d = {}
    if vf is not None:
        d["valid_from"] = vf
    if vt is not None:
        d["valid_to"] = vt
    if extra:
        d["other"] = "ignored"
    return d


# -- mutlu-yol ---------------------------------------------------------------------------------

def test_both_none_ok():
    _check_window(_obj(), 100.0)


def test_no_keys_ok():
    _check_window({}, 100.0)


def test_inside_window_ok():
    _check_window(_obj(50.0, 150.0), 100.0)


def test_returns_none_when_ok():
    assert _check_window(_obj(50.0, 150.0), 100.0) is None


def test_extra_keys_ignored():
    _check_window(_obj(50.0, 150.0, extra=True), 100.0)


# -- valid_from ---------------------------------------------------------------------------------

def test_before_valid_from_rejected():
    with pytest.raises(AdapterError, match="valid_from"):
        _check_window(_obj(100.0, 200.0), 50.0)


def test_at_valid_from_ok():
    """now < valid_from — 100.0 tam esik -> OK."""
    _check_window(_obj(100.0, 200.0), 100.0)


def test_just_before_valid_from_rejected():
    with pytest.raises(AdapterError):
        _check_window(_obj(100.0, 200.0), 99.99)


def test_valid_from_zero_ok():
    _check_window(_obj(0.0, 200.0), 50.0)


def test_valid_from_string_coerced():
    """float(vf) — string deger kabul edilir."""
    _check_window(_obj("100.0", 200.0), 150.0)


def test_valid_from_string_rejected_before():
    with pytest.raises(AdapterError):
        _check_window(_obj("150.0", 200.0), 100.0)


def test_valid_from_int_ok():
    _check_window(_obj(100, 200), 150)


# -- valid_to ---------------------------------------------------------------------------------

def test_after_valid_to_rejected():
    with pytest.raises(AdapterError, match="valid_to"):
        _check_window(_obj(50.0, 100.0), 150.0)


def test_at_valid_to_ok():
    """now > valid_to — 100.0 tam esik -> OK."""
    _check_window(_obj(50.0, 100.0), 100.0)


def test_just_after_valid_to_rejected():
    with pytest.raises(AdapterError):
        _check_window(_obj(50.0, 100.0), 100.01)


def test_valid_to_zero_rejected():
    with pytest.raises(AdapterError):
        _check_window(_obj(0.0, 0.0), 1.0)


def test_valid_to_string_coerced():
    with pytest.raises(AdapterError):
        _check_window(_obj(50.0, "100.0"), 150.0)


# -- birlikte ---------------------------------------------------------------------------------

def test_only_valid_from_ok():
    _check_window(_obj(vf=100.0), 150.0)


def test_only_valid_to_ok():
    _check_window(_obj(vt=200.0), 150.0)


def test_only_valid_from_rejected():
    with pytest.raises(AdapterError):
        _check_window(_obj(vf=100.0), 50.0)


def test_only_valid_to_rejected():
    with pytest.raises(AdapterError):
        _check_window(_obj(vt=100.0), 150.0)


def test_valid_from_checked_first():
    """valid_from kontrolu valid_to'dan once."""
    with pytest.raises(AdapterError, match="valid_from"):
        _check_window(_obj(200.0, 100.0), 150.0)


def test_zero_length_window_endpoint_ok():
    """vf == vt == now -> her iki esik inclusive."""
    _check_window(_obj(100.0, 100.0), 100.0)


def test_zero_length_window_around_rejected_both():
    with pytest.raises(AdapterError, match="valid_from"):
        _check_window(_obj(100.0, 100.0), 99.0)
    with pytest.raises(AdapterError, match="valid_to"):
        _check_window(_obj(100.0, 100.0), 101.0)


# -- now=None (time.time) ---------------------------------------------------------------------------------

def test_now_none_uses_time(monkeypatch):
    import sester.adapters as A
    monkeypatch.setattr(A.time, "time", lambda: 150.0)
    _check_window(_obj(100.0, 200.0), None)


def test_now_none_rejects_expired(monkeypatch):
    import sester.adapters as A
    monkeypatch.setattr(A.time, "time", lambda: 250.0)
    with pytest.raises(AdapterError, match="valid_to"):
        _check_window(_obj(100.0, 200.0), None)


def test_now_none_rejects_early(monkeypatch):
    import sester.adapters as A
    monkeypatch.setattr(A.time, "time", lambda: 50.0)
    with pytest.raises(AdapterError, match="valid_from"):
        _check_window(_obj(100.0, 200.0), None)


def test_now_none_empty_obj(monkeypatch):
    import sester.adapters as A
    monkeypatch.setattr(A.time, "time", lambda: 999.0)
    _check_window({}, None)


# -- hata-turu ---------------------------------------------------------------------------------

def test_raises_adapter_error():
    with pytest.raises(AdapterError):
        _check_window(_obj(100.0, 200.0), 50.0)


def test_error_is_exception():
    try:
        _check_window(_obj(100.0, 200.0), 50.0)
    except AdapterError as exc:
        assert isinstance(exc, Exception)


def test_invalid_valid_from_type_raises():
    with pytest.raises((ValueError, TypeError)):
        _check_window(_obj("abc", 200.0), 150.0)


def test_invalid_valid_to_type_raises():
    with pytest.raises((ValueError, TypeError)):
        _check_window(_obj(100.0, None.__class__.__name__), 150.0) if False else \
            _check_window({"valid_to": "abc"}, 150.0)


def test_none_valid_values_ok():
    """vf/vt None -> atlanir."""
    _check_window({"valid_from": None, "valid_to": None}, 100.0)


# -- negatif ---------------------------------------------------------------------------------

def test_negative_times_ok():
    _check_window(_obj(-200.0, -100.0), -150.0)


def test_negative_now_before_rejected():
    with pytest.raises(AdapterError):
        _check_window(_obj(-100.0, 0.0), -150.0)


def test_negative_now_after_rejected():
    with pytest.raises(AdapterError):
        _check_window(_obj(-200.0, -100.0), -50.0)


# -- tekrar ---------------------------------------------------------------------------------

def test_repeatable():
    o = _obj(50.0, 150.0)
    _check_window(o, 100.0)
    _check_window(o, 100.0)


def test_not_mutated():
    o = _obj(50.0, 150.0)
    _check_window(o, 100.0)
    assert o == _obj(50.0, 150.0)


def test_independent_calls():
    o1 = _obj(50.0, 150.0)
    o2 = _obj(60.0, 160.0)
    _check_window(o1, 100.0)
    with pytest.raises(AdapterError):
        _check_window(o2, 55.0)
