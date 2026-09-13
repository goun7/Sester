"""SESTER S6 testleri — ortak kabul-sözleşmesinin 63-tarafı (test_196–201).

64-Tenderix tarafı senaryoları kendi repo'sunda numaralandırır; burada
facilitator sözleşmesinin S6 yarıları: authorize(verify)→capture(settle)→
refund ters-yazımı, metering-iadesi ve oturum-sonu tek-bundle kanıt-bütünlüğü.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod

import pytest

from sester.facilitator_svc import FacilitatorService
from sester.ledger import Ledger
from sester.settlement import build_settlement_batch

SECRET = "s6-secret"
PRICE_MINOR = 50_000


def pay_for(seller: str, nonce: str, amount_s: str = "0.05") -> str:
    mac = hmac_mod.new(SECRET.encode(),
                       f"{seller}|{nonce}|{amount_s}|/weather".encode(),
                       hashlib.sha256).hexdigest()
    return f"pugio0 {seller}:{nonce}:{amount_s}:{mac}"


@pytest.fixture()
def svc(tmp_path):
    led = Ledger(tmp_path / "s6.sqlite3", secret=SECRET)
    s = FacilitatorService(led, secret=SECRET, free_transactions=10**9)
    yield s
    led.close()


def _authorize_and_capture(svc, seller="müşteri-x", nonce="c1"):
    pay = pay_for(seller, nonce)
    assert svc.verify(pay, "/weather").status == "ok"          # S6.a authorize
    d = svc.settle(pay, "/weather", PRICE_MINOR)               # S6.b capture
    assert d.status == "ok"
    return pay


def test_196_authorize_verify_ok(svc):
    pay = pay_for("müşteri-x", "a1")
    d = svc.verify(pay, "/weather")
    assert d.status == "ok" and d.reason == "verify_ok"


def test_197_capture_settle_ok_single_nonce(svc):
    d = svc.settle(pay_for("müşteri-x", "c1"), "/weather", PRICE_MINOR)
    assert d.status == "ok" and d.reason == "settled"


def test_198_replay_capture_rejected(svc):
    pay = pay_for("müşteri-x", "c2")
    assert svc.settle(pay, "/weather", PRICE_MINOR).status == "ok"
    d2 = svc.settle(pay, "/weather", PRICE_MINOR)
    assert d2.status == "rejected" and d2.reason == "replay_detected"


def test_199_refund_after_capture_ok_and_metering_credit(svc):
    pay = _authorize_and_capture(svc, "müşteri-x", "r1")
    d = svc.refund(pay, "/weather", PRICE_MINOR,
                   reason="inkâr", dispute_ref="disp-1")
    assert d.status == "ok" and d.reason == "refunded"
    # ters-yazım ledger'da: net-harcama 0 olmalı
    assert svc.ledger.spent_today_minor("müşteri-x") == 0
    evs = svc.ledger.export_events(agent_id="müşteri-x")
    assert any(e["event_type"] == "refund" for e in evs)


def test_200_refund_limits_fail_closed(svc):
    # settle-yok → RED
    d0 = svc.refund(pay_for("müşteri-x", "x0"), "/weather", PRICE_MINOR)
    assert d0.status == "rejected" and d0.reason == "refund_without_settlement"
    # tutar-aşımı (settle 0.05, iade 0.10) → RED
    pay = _authorize_and_capture(svc, "müşteri-x", "x1")
    d1 = svc.refund(pay, "/weather", PRICE_MINOR * 2)
    assert d1.status == "rejected" and d1.reason == "refund_exceeds"
    # kural: nonce başına TOPLAM iade ≤ settle — ilk 0.05 iade ok, ikinci RED
    d2 = svc.refund(pay, "/weather", PRICE_MINOR)
    assert d2.status == "ok"
    d3 = svc.refund(pay, "/weather", PRICE_MINOR)
    assert d3.status == "rejected" and d3.reason == "refund_exceeds"


def test_201_session_bundle_integrates_all_events_and_batch(svc):
    _authorize_and_capture(svc, "müşteri-x", "f1")
    svc.refund(pay_for("müşteri-x", "f1"), "/weather", PRICE_MINOR,
               dispute_ref="disp-9")
    b = build_settlement_batch(
        svc.ledger, "müşteri-x", chain_id=8453,
        contract="0x" + "0c" * 20, from_address="0x" + "f4" * 20)
    assert b.total_minor == 0          # 0.05 settle − 0.05 refund
    assert b.calldata.startswith("0x")
    assert svc.ledger.verify_chain()
