"""FacilitatorService._metrics_text dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory; ledger stublu (gercek zincir YOK).
"""
import os
import sys
from types import SimpleNamespace

import pytest

from sester.facilitator_svc.service import FacilitatorService


def _svc(metrics=None, chain_ok=True, secret="test-secret"):
    svc = FacilitatorService.__new__(FacilitatorService)
    svc.metrics = metrics if metrics is not None else {
        "verify_ok": 0, "verify_rejected": 0,
    }
    svc.ledger = SimpleNamespace(verify_chain=lambda: chain_ok)
    return svc


def _text(**kw):
    return _svc(**kw)._metrics_text()


# -- format ---------------------------------------------------------------------------------

def test_returns_str():
    assert isinstance(_text(), str)


def test_ends_with_newline():
    assert _text().endswith("\n")


def test_has_type_lines():
    t = _text()
    assert "# TYPE sester_facilitator_verify_ok counter" in t


def test_has_value_lines():
    t = _text(metrics={"verify_ok": 5})
    assert "sester_facilitator_verify_ok 5" in t


def test_has_chain_valid_gauge():
    assert "# TYPE sester_facilitator_chain_valid gauge" in _text()


def test_has_chain_valid_value():
    assert "sester_facilitator_chain_valid 1" in _text()


# -- chain-valid ---------------------------------------------------------------------------------

def test_chain_valid_1_when_ok():
    assert "sester_facilitator_chain_valid 1" in _text(chain_ok=True)


def test_chain_valid_0_when_broken():
    assert "sester_facilitator_chain_valid 0" in _text(chain_ok=False)


def test_chain_gauge_last():
    """chain gauge en son satirlarda."""
    t = _text().splitlines()
    nonempty = [l for l in t if l]
    assert nonempty[-1].startswith("sester_facilitator_chain_valid")


def test_chain_type_before_value():
    t = _text().splitlines()
    i_type = next(i for i, l in enumerate(t) if "chain_valid gauge" in l)
    i_val = next(i for i, l in enumerate(t) if l.startswith("sester_facilitator_chain_valid "))
    assert i_type < i_val


# -- metric-ciftleri ---------------------------------------------------------------------------------

def test_type_value_pair_per_metric():
    m = {"a": 1, "b": 2}
    t = _text(metrics=m)
    for k, v in m.items():
        assert f"# TYPE sester_facilitator_{k} counter" in t
        assert f"sester_facilitator_{k} {v}" in t


def test_metric_count_lines():
    m = {"x": 1, "y": 2, "z": 3}
    t = _text(metrics=m)
    # her metric: TYPE + value; + chain gauge (TYPE + value)
    assert t.count("# TYPE") == 4  # 3 metric + 1 chain
    assert t.count("sester_facilitator_") == 8  # 4 TYPE + 4 value


def test_empty_metrics_only_chain():
    t = _text(metrics={})
    assert t == "# TYPE sester_facilitator_chain_valid gauge\n" \
                "sester_facilitator_chain_valid 1\n"


def test_single_metric():
    t = _text(metrics={"settled": 42})
    assert "sester_facilitator_settled 42" in t


def test_zero_value():
    t = _text(metrics={"verify_ok": 0})
    assert "sester_facilitator_verify_ok 0" in t


def test_large_value():
    t = _text(metrics={"verify_ok": 10**9})
    assert "sester_facilitator_verify_ok 1000000000" in t


def test_negative_value():
    t = _text(metrics={"delta": -5})
    assert "sester_facilitator_delta -5" in t


def test_float_value():
    t = _text(metrics={"ratio": 1.5})
    assert "sester_facilitator_ratio 1.5" in t


# -- tum-uretim-metrikleri ---------------------------------------------------------------------------------

def test_default_metrics_present():
    svc = FacilitatorService.__new__(FacilitatorService)
    svc.metrics = {"verify_ok": 1, "verify_rejected": 2, "settled": 3,
                   "settle_rejected": 4, "refunded": 5, "refund_rejected": 6}
    svc.ledger = SimpleNamespace(verify_chain=lambda: True)
    t = svc._metrics_text()
    for k in svc.metrics:
        assert f"sester_facilitator_{k} " in t


def test_six_metrics_six_types():
    m = {"verify_ok": 0, "verify_rejected": 0, "settled": 0,
         "settle_rejected": 0, "refunded": 0, "refund_rejected": 0}
    t = _text(metrics=m)
    assert t.count("counter") == 6


# -- prometheus-uyumluluk ---------------------------------------------------------------------------------

def test_no_duplicate_types():
    t = _text(metrics={"a": 1, "b": 2})
    types = [l for l in t.splitlines() if l.startswith("# TYPE")]
    assert len(types) == len(set(types))


def test_line_structure():
    for line in _text(metrics={"a": 1}).splitlines():
        if line and not line.startswith("#"):
            parts = line.split()
            assert len(parts) == 2


def test_counter_not_gauge_for_metrics():
    t = _text(metrics={"a": 1})
    assert "sester_facilitator_a counter" in t


def test_gauge_only_for_chain():
    t = _text(metrics={"a": 1})
    assert t.count("gauge") == 1


# -- tekrar ---------------------------------------------------------------------------------

def test_repeatable():
    assert _text(metrics={"a": 1}) == _text(metrics={"a": 1})


def test_changes_with_metrics():
    assert _text(metrics={"a": 1}) != _text(metrics={"a": 2})


def test_changes_with_chain():
    assert _text(chain_ok=True) != _text(chain_ok=False)


def test_metrics_not_mutated():
    svc = _svc(metrics={"a": 1})
    svc._metrics_text()
    assert svc.metrics == {"a": 1}


def test_verify_chain_called():
    calls = {"n": 0}

    def _vc():
        calls["n"] += 1
        return True
    svc = FacilitatorService.__new__(FacilitatorService)
    svc.metrics = {}
    svc.ledger = SimpleNamespace(verify_chain=_vc)
    svc._metrics_text()
    assert calls["n"] == 1


# -- ad-soyad-ve-unicode ---------------------------------------------------------------------------------

def test_underscore_metric_name():
    t = _text(metrics={"verify_rejected": 3})
    assert "sester_facilitator_verify_rejected 3" in t


def test_turkish_chars_in_name():
    t = _text(metrics={"ödeme": 1})
    assert "sester_facilitator_ödeme 1" in t


def test_all_names_prefixed():
    t = _text(metrics={"a": 1, "b": 2})
    for line in t.splitlines():
        if line and not line.startswith("#"):
            assert line.startswith("sester_facilitator_")
