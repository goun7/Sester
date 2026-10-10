"""sester.receipt._proof_canonical + _fmt_float dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (string formatlama, dis cagri YOK).
_fmt_float: f"{float(v):.6f}" — 6-ondalik sabit-format.
"""
import sys

import pytest

sys.path.insert(0, ".")
from sester.receipt import _proof_canonical, _fmt_float  # noqa: E402


# == _fmt_float ==============================================================================

def test_fmt_zero():
    assert _fmt_float(0) == "0.000000"


def test_fmt_int():
    assert _fmt_float(5) == "5.000000"


def test_fmt_float():
    assert _fmt_float(1.5) == "1.500000"


def test_fmt_six_decimals():
    assert _fmt_float(1.123456) == "1.123456"


def test_fmt_rounds_7th_digit():
    """yedigi ondalik yuvarlanir (banker's?)."""
    assert _fmt_float(1.1234565) == "1.123456" or _fmt_float(1.1234565) == "1.123457"


def test_fmt_negative():
    assert _fmt_float(-1.5) == "-1.500000"


def test_fmt_large():
    assert _fmt_float(1e9) == "1000000000.000000"


def test_fmt_tiny():
    """1e-7 < 0.0000005 -> '0.000000'."""
    assert _fmt_float(1e-7) == "0.000000"


def test_fmt_inf():
    """inf -> 'inf'."""
    assert _fmt_float(float("inf")) == "inf"


def test_fmt_neg_inf():
    assert _fmt_float(float("-inf")) == "-inf"


def test_fmt_nan():
    assert _fmt_float(float("nan")) == "nan"


def test_fmt_string_number():
    assert _fmt_float("3.5") == "3.500000"


def test_fmt_bool_true():
    """float(True) = 1.0."""
    assert _fmt_float(True) == "1.000000"


def test_fmt_bool_false():
    assert _fmt_float(False) == "0.000000"


def test_fmt_raises_on_str():
    with pytest.raises(ValueError):
        _fmt_float("abc")


def test_fmt_raises_on_none():
    with pytest.raises(TypeError):
        _fmt_float(None)


def test_fmt_returns_str():
    assert isinstance(_fmt_float(1), str)


def test_fmt_precision():
    """0.1+0.2 ondalik hassasiyet."""
    assert _fmt_float(0.1 + 0.2) == "0.300000"


# == _proof_canonical ========================================================================

def rec(**kw):
    base = {"ts": 1000.0, "event_type": "ev", "sub": "a", "resource": "r",
            "amount": 1.5, "payload": "u", "prev_proof": "p"}
    base.update(kw)
    return base


def test_canonical_returns_str():
    assert isinstance(_proof_canonical(rec()), str)


def test_canonical_delimiter():
    """7 alan, 6 '|'. """
    assert _proof_canonical(rec()).count("|") == 6


def test_canonical_exact():
    r = rec()
    assert _proof_canonical(r) == "1000.000000|ev|a|r|1.500000|u|p"


def test_canonical_field_order():
    """ts|event_type|sub|resource|amount|payload|prev_proof."""
    r = rec(ts=1.0, event_type="X", sub="Y", resource="Z",
            amount=2.0, payload="W", prev_proof="V")
    assert _proof_canonical(r) == "1.000000|X|Y|Z|2.000000|W|V"


def test_canonical_ts_formatted():
    assert _proof_canonical(rec(ts=3.1415926535)).split("|")[0] == "3.141593"


def test_canonical_amount_formatted():
    assert _proof_canonical(rec(amount=2.5)).split("|")[4] == "2.500000"


def test_canonical_int_ts():
    assert _proof_canonical(rec(ts=42)).split("|")[0] == "42.000000"


def test_canonical_str_ts():
    """float('42') kabul."""
    assert _proof_canonical(rec(ts="42")).split("|")[0] == "42.000000"


def test_canonical_str_amount():
    assert _proof_canonical(rec(amount="1.5")).split("|")[4] == "1.500000"


# -- ayraç-enjeksiyon --------------------------------------------------------------------------

def test_pipe_in_field():
    """ORTAM-SINIR: '|' ESCAPE EDILMEZ — ayirac enjeksiyonu acik.

    event_type='a|b'+sub='c' ile event_type='a'+sub='b|c' AYNI kanonik.
    """
    a = _proof_canonical(rec(event_type="a|b", sub="c"))
    b = _proof_canonical(rec(event_type="a", sub="b|c"))
    assert a == b


def test_pipe_in_sub_resource():
    a = _proof_canonical(rec(sub="x|y", resource="z"))
    b = _proof_canonical(rec(sub="x", resource="y|z"))
    assert a == b


def test_pipe_in_amount():
    """float('1|5') ValueError -> ayirac-enjeksiyonu amount'ta ZOR."""
    with pytest.raises(ValueError):
        _proof_canonical(rec(amount="1|5"))


# -- ondali-carpisma ---------------------------------------------------------------------------

def test_decimal_collision():
    """ORTAM-SINIR: 6-ondali sinir ts=1e-7 ile ts=0 ayni."""
    assert _proof_canonical(rec(ts=1e-7)).split("|")[0] == "0.000000"
    assert _proof_canonical(rec(ts=0)).split("|")[0] == "0.000000"


def test_inf_collision():
    """inf ts -> 'inf' — taklit-edilebilir kanonik."""
    assert "inf" in _proof_canonical(rec(ts=float("inf")))


def test_nan_canonical():
    assert "nan" in _proof_canonical(rec(ts=float("nan")))


# -- eksik-anahtar -----------------------------------------------------------------------------

def test_missing_ts_raises():
    r = rec()
    del r["ts"]
    with pytest.raises(KeyError):
        _proof_canonical(r)


def test_missing_event_type_raises():
    r = rec()
    del r["event_type"]
    with pytest.raises(KeyError):
        _proof_canonical(r)


def test_missing_prev_proof_raises():
    r = rec()
    del r["prev_proof"]
    with pytest.raises(KeyError):
        _proof_canonical(r)


def test_missing_sub_raises():
    r = rec()
    del r["sub"]
    with pytest.raises(KeyError):
        _proof_canonical(r)


def test_missing_payload_raises():
    r = rec()
    del r["payload"]
    with pytest.raises(KeyError):
        _proof_canonical(r)


def test_missing_amount_raises():
    r = rec()
    del r["amount"]
    with pytest.raises(KeyError):
        _proof_canonical(r)


# -- cesitli ---------------------------------------------------------------------------------

def test_turkish_fields():
    r = rec(event_type="İzin", sub="Gökhan", resource="İstanbul")
    s = _proof_canonical(r)
    assert "Gökhan" in s and "İstanbul" in s and "İzin" in s


def test_emoji_fields():
    r = rec(event_type="😀", sub="🤖")
    assert "😀" in _proof_canonical(r)


def test_empty_strings():
    r = rec(event_type="", sub="", resource="", payload="", prev_proof="")
    assert _proof_canonical(r) == "1000.000000||||1.500000||"


def test_long_fields():
    r = rec(prev_proof="x" * 1000)
    assert _proof_canonical(r).endswith("|" + "x" * 1000)


def test_long_payload():
    r = rec(payload="y" * 500)
    assert ("y" * 500) in _proof_canonical(r)


def test_repeatable():
    r = rec()
    assert _proof_canonical(r) == _proof_canonical(r)


def test_input_not_mutated():
    r = rec()
    before = str(r)
    _proof_canonical(r)
    assert str(r) == before


def test_deterministic():
    """ayni rec ayni kanonik."""
    assert _proof_canonical(rec(ts=1.5)) == _proof_canonical(rec(ts=1.5))
