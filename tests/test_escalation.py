"""SESTER escalation testleri — insan-onay kuyruğu (KARAR_63B madde-3).

Kapsam: durum-makinesi (pending→approved→consumed / denied / expired),
tek-kezlik tüketim, tek-bilet disiplini, fail-closed TTL, tam denetim-iz
(ledger olayları hash-chain'li), kötü-geçiş retleri.
"""

from __future__ import annotations

import pytest

import sester.escalation as esc_mod
from sester.escalation import (
    APPROVED,
    DENIED,
    EXPIRED,
    PENDING,
    EscalationQueue,
)
from sester.ledger import Ledger


@pytest.fixture()
def led(tmp_path):
    l = Ledger(tmp_path / "esc-led.sqlite3", secret="esc")
    yield l
    l.close()


@pytest.fixture()
def q(tmp_path, led):
    queue = EscalationQueue(tmp_path / "esc.sqlite3", ledger=led, ttl_seconds=900)
    yield queue
    queue.close()


# ------------------------------------------------------------- durum-makinesi

def test_96_park_creates_pending_ticket(q):
    t = q.park("ag-1", "/large", 5.00, "require-human-for-large")
    assert t["status"] == PENDING
    assert t["esc_id"]
    assert t["expires_at"] > t["created_at"]


def test_97_park_is_idempotent_per_agent_resource(q):
    a = q.park("ag-1", "/large", 5.00, "r1")
    b = q.park("ag-1", "/large", 5.00, "r1")
    assert a["esc_id"] == b["esc_id"], "spam-park: aynı çifte ikinci bilet açıldı"
    # farklı kaynak → yeni bilet (haklı)
    c = q.park("ag-1", "/other", 5.00, "r1")
    assert c["esc_id"] != a["esc_id"]


def test_98_approve_then_consume_once(q):
    t = q.park("ag-1", "/large", 5.00, "r1")
    d = q.decide(t["esc_id"], approve=True, by="auditor")
    assert d["status"] == APPROVED
    assert q.consume(t["esc_id"]) is True
    assert q.consume(t["esc_id"]) is False, "onay iki kez tüketildi!"


def test_99_deny_blocks_requests(q):
    t = q.park("ag-1", "/large", 5.00, "r1")
    q.decide(t["esc_id"], approve=False, by="auditor", note="şüpheli")
    assert q.approved_for("ag-1", "/large") is None


def test_100_invalid_transition_rejected(q):
    t = q.park("ag-1", "/large", 5.00, "r1")
    q.decide(t["esc_id"], approve=True, by="auditor")
    with pytest.raises(ValueError):
        q.decide(t["esc_id"], approve=False, by="saldırı")


def test_101_unknown_ticket_keyerror(q):
    with pytest.raises(KeyError):
        q.decide("esc-yok", approve=True, by="auditor")


# ------------------------------------------------- fail-closed TTL (deterministik)

def test_102_expired_ticket_never_approvable(q, monkeypatch):
    t = q.park("ag-1", "/large", 5.00, "r1")
    # saati 1 saat ileri al → TTL 15 dk dolu
    real_time = esc_mod.time.time
    monkeypatch.setattr(esc_mod.time, "time", lambda: real_time() + 3600)
    assert q.approved_for("ag-1", "/large") is None
    assert q.get(t["esc_id"])["status"] == EXPIRED
    with pytest.raises(ValueError):
        q.decide(t["esc_id"], approve=True, by="gecikmiş-onay")


# --------------------------------------------------------- denetim-izi (ledger)

def test_103_full_audit_trail_in_ledger_chain(q, led):
    t = q.park("ag-1", "/large", 5.00, "r1")
    q.decide(t["esc_id"], approve=True, by="auditor", note="ok")
    q.consume(t["esc_id"])
    kinds = [r["event_type"] for r in led.recent_events(20)]
    assert "escalation_parked" in kinds
    assert "escalation_approved" in kinds
    assert led.verify_chain(), "escalation olayları zinciri bozdu"


def test_104_denied_path_also_audited(q, led):
    t = q.park("ag-2", "/large", 9.99, "r1")
    q.decide(t["esc_id"], approve=False, by="auditor")
    kinds = [r["event_type"] for r in led.recent_events(20)]
    assert "escalation_denied" in kinds
    assert led.verify_chain()


# ------------------------------------------------- demo-sarımı (entegrasyon)

def test_105_demo_policy_guard_returns_verdicts():
    from sester.demo_api import policy_guard

    # demo politika: /weather allow; büyük tutar escalate; bilinmeyen host deny
    assert policy_guard("k1", "/weather", 0.05)[0] == "allow"
    assert policy_guard("k1", "/bilinmeyen", 0.05)[0] == "deny"
    v, rule = policy_guard("k1", "/histogram", 25.00)
    assert v == "escalate", "büyük tutar insan-onayına gitmeli"
    assert rule == "require-human-for-large"


def test_106_demo_escalations_endpoint_lists_pending(q):
    # canlı kuyruk (demo modülü) ile: park → /escalations görür
    from sester import demo_api

    t = demo_api.esc_queue.park("demo-esc-agent", "/histogram", 5.00,
                                "require-human-for-large")
    pending = demo_api.esc_queue.pending()
    assert any(r["esc_id"] == t["esc_id"] for r in pending)
    # temizle: reddet (test-artefaktı kalmasın)
    demo_api.esc_queue.decide(t["esc_id"], approve=False, by="test-cleanup")


def test_park_rejects_negative_and_fake_amount(tmp_path):
    """AT-062-ekonomik-ayna (escalation-yüzeyine-yayılım): onaylı-biletin
    amount'u-park'ın-yazdığı-değerdir — negatif-park-onaylanan-harcamayı-sıfırlar
    (kota-bypass). bool-sayı-giydirme-tuzağı-da-rede (float(True)==1.0)."""
    from sester.escalation import EscalationQueue
    q = EscalationQueue(tmp_path / "esc_neg.sqlite3")
    try:
        with pytest.raises(ValueError, match="negatif-escalation-amount"):
            q.park("a1", "/expensive", -5.0, "r")
        with pytest.raises(ValueError, match="sayı-değil"):
            q.park("a1", "/expensive", True, "r")
        with pytest.raises(ValueError, match="sayı-değil"):
            q.park("a1", "/expensive", "free", "r")
        # temiz-park-hâlâ-çalışıyor
        t = q.park("a1", "/expensive", 2.0, "r")
        assert t["amount"] == 2.0
    finally:
        q.close()
