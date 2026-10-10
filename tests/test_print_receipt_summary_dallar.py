"""sester.cli._print_receipt_summary dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (capsys yakalama, dis cagri YOK).
Receipt-ozeti yazdirir; node_cosign varsa anchor satiri.
"""
import sys

import pytest

sys.path.insert(0, ".")
from sester.cli import _print_receipt_summary  # noqa: E402


def rec(**kw):
    base = {
        "seq": 42, "sub": "agent-1", "resource": "res-1", "amount": 1.5,
        "currency": "USDC", "amount_minor": 1500000, "iss": "issuer-1",
        "node_key_id": "key-1", "proof": "p" * 64,
        "node_cosign": "c" * 64, "prev_proof": "prev",
    }
    base.update(kw)
    return base


@pytest.fixture()
def out(capsys):
    def _run(**kw):
        _print_receipt_summary(rec(**kw))
        return capsys.readouterr().out
    return _run


# -- satir-yapisi -----------------------------------------------------------------------------

def test_prints_nothing_returned(out):
    assert _print_receipt_summary(rec()) is None


def test_returns_none():
    assert _print_receipt_summary(rec()) is None


def test_seq_line(out):
    assert "seq      : 42" in out()


def test_agent_line(out):
    assert "agent    : agent-1" in out()


def test_resource_line(out):
    assert "resource : res-1" in out()


def test_amount_line(out):
    assert "amount   : 1.5 USDC (1500000 minor)" in out()


def test_node_line(out):
    assert "node     : issuer-1 [key-1]" in out()


def test_proof_line(out):
    assert "proof    : pppppppppppppppppppppppp" in out()  # first 24


def test_proof_ellipsis(out):
    assert "…" in out()


def test_anchor_line_with_cosign(out):
    assert "anchor   : cccccccccccccccccccccccc" in out()


def test_anchor_ellipsis_with_cosign(out):
    assert out().count("…") == 2


def test_anchor_line_without_cosign(out):
    r = out(node_cosign=None)
    assert "anchor   : (cosign" in r


def test_anchor_placeholder_no_cosign(out):
    assert "(cosign" in out(node_cosign=None)


def test_no_anchor_hash_without_cosign(out):
    r = out(node_cosign=None)
    assert "cccccccccccccccccccccccc" not in r


def test_cosign_get_optional(out):
    """r.get('node_cosign') — anahtar YOKSA da placeholder."""
    r = rec()
    del r["node_cosign"]
    capsys_lines = _print_receipt_summary(r)
    assert True  # KeyError olmamali


# -- deger-formatlama -------------------------------------------------------------------------

def test_seq_int(out):
    assert ": 42" in out(seq=42)


def test_amount_float(out):
    assert "2.75 USDC" in out(amount=2.75, currency="USDC")


def test_currency_displayed(out):
    assert "TRY" in out(currency="TRY")


def test_amount_minor_displayed(out):
    assert "(275 minor)" in out(amount=2.75, amount_minor=275)


def test_turkish_agent(out):
    assert "Gökhan" in out(sub="Gökhan")


def test_turkish_resource(out):
    assert "İstanbul" in out(resource="İstanbul")


def test_emoji_node(out):
    assert "🤖" in out(iss="🤖-node")


def test_turkish_currency(out):
    assert "Türk-Lirası" in out(currency="Türk-Lirası")


# -- proof-truncation --------------------------------------------------------------------------

def test_proof_truncated_24(out):
    r = out(proof="abcdefghij" * 10)
    assert "abcdefghijabcdefghijabcd" in r


def test_proof_short(out):
    """24'ten kisa proof — [:24] hepsini alir."""
    r = out(proof="short")
    assert "short" in r


def test_proof_empty(out):
    assert "proof    : …" in out(proof="")


def test_cosign_truncated_24(out):
    r = out(node_cosign="xy" * 100)
    assert "xyxyxyxyxyxyxyxyxyxyxyxy" in r


def test_cosign_short(out):
    assert "abc" in out(node_cosign="abc")


def test_cosign_empty(out):
    """'' -> falsy -> placeholder."""
    assert "(cosign" in out(node_cosign="")


# -- eksik-anahtar -----------------------------------------------------------------------------

def test_missing_seq_raises():
    r = rec()
    del r["seq"]
    with pytest.raises(KeyError):
        _print_receipt_summary(r)


def test_missing_sub_raises():
    r = rec()
    del r["sub"]
    with pytest.raises(KeyError):
        _print_receipt_summary(r)


def test_missing_resource_raises():
    r = rec()
    del r["resource"]
    with pytest.raises(KeyError):
        _print_receipt_summary(r)


def test_missing_amount_raises():
    r = rec()
    del r["amount"]
    with pytest.raises(KeyError):
        _print_receipt_summary(r)


def test_missing_currency_raises():
    r = rec()
    del r["currency"]
    with pytest.raises(KeyError):
        _print_receipt_summary(r)


def test_missing_amount_minor_raises():
    r = rec()
    del r["amount_minor"]
    with pytest.raises(KeyError):
        _print_receipt_summary(r)


def test_missing_iss_raises():
    r = rec()
    del r["iss"]
    with pytest.raises(KeyError):
        _print_receipt_summary(r)


def test_missing_node_key_id_raises():
    r = rec()
    del r["node_key_id"]
    with pytest.raises(KeyError):
        _print_receipt_summary(r)


def test_missing_proof_raises():
    r = rec()
    del r["proof"]
    with pytest.raises(KeyError):
        _print_receipt_summary(r)


def test_node_cosign_optional():
    """get() ile alinir — KeyError YOK."""
    r = rec()
    del r["node_cosign"]
    _print_receipt_summary(r)  # hata vermez


# -- cesitli -----------------------------------------------------------------------------------

def test_line_count(out):
    assert len(out().splitlines()) == 7


def test_repeatable(out):
    assert out() == out()


def test_stdout_not_stderr(out, capsys):
    _print_receipt_summary(rec())
    assert capsys.readouterr().err == ""


def test_seq_negative(out):
    assert ": -1" in out(seq=-1)


def test_seq_zero(out):
    assert ": 0" in out(seq=0)


def test_long_values(out):
    r = out(resource="x" * 200)
    assert "x" * 200 in r


@pytest.mark.parametrize("seq", [0, 1, 42, -1, 999999])
def test_seq_values(out, seq):
    assert f": {seq}" in out(seq=seq)
