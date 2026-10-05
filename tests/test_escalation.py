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


# ------------------------------------------- decide() doğrudan testleri

def test_107_decide_missing_ticket_raises_keyerror(q):
    """Olmayan bilet → KeyError (boş sorgu)."""
    with pytest.raises(KeyError, match="bilet yok"):
        q.decide("yok-ki", approve=True, by="auditor")


def test_108_decide_is_one_way_pending_to_approved(q):
    """Tek-yönlü: approved bilete tekrar karar → ValueError."""
    t = q.park("ag-1", "/large", 5.00, "r1")
    r1 = q.decide(t["esc_id"], approve=True, by="auditor", note="ilk")
    assert r1["status"] == APPROVED
    assert r1["decided_by"] == "auditor"
    assert r1["note"] == "ilk"
    # tekrar karar verilemez
    with pytest.raises(ValueError):
        q.decide(t["esc_id"], approve=False, by="baska")


def test_109_decide_denied_path_sets_status_and_by(q):
    t = q.park("ag-2", "/large", 9.99, "r1")
    r = q.decide(t["esc_id"], approve=False, by="red-verici", note="çok pahalı")
    assert r["status"] == DENIED
    assert r["decided_by"] == "red-verici"
    # denied da tekrar karar verilemez
    with pytest.raises(ValueError):
        q.decide(t["esc_id"], approve=True, by="baska")


def test_110_decide_note_defaults_empty_and_persists(q):
    t = q.park("ag-3", "/x", 1.00, "r1")
    r = q.decide(t["esc_id"], approve=True, by="auditor")
    assert r["note"] == ""
    assert r["decided_at"] is not None


# LEAD 2026-10-01 — x402 #2887: dispute layer, oracle-bound resolution
# "Resolution runs against a source NEITHER PARTY CONTROLS"
def test_oracle_bound_decision_kaydedilir(tmp_path):
    """decide_with_oracle — payload'da oracle_ref tasiyan ledger kaydi."""
    led_path = tmp_path / "oracle.sqlite3"
    q = EscalationQueue(str(tmp_path / "esc.db"), ledger=None, ttl_seconds=60)
    t = q.park("agent-d", "/api/paid", 1.0, "rule-1", reason="buyuk-tutar")
    out = q.decide_with_oracle(
        t["esc_id"], approve=True, by="auditor-1",
        oracle_ref="github.com/x/y/pull/42", note="PR merge kaniti")
    assert out["status"] == "approved"
    q.close()


def test_bos_oracle_reddedilir(tmp_path):
    """oracle_ref bos olamaz — 'bagli degil' diye sey yoktur (#2887)."""
    q = EscalationQueue(str(tmp_path / "esc2.db"), ledger=None, ttl_seconds=60)
    t = q.park("agent-e", "/api/x", 0.5, "rule-2")
    for bos in ("", "   "):
        with pytest.raises(ValueError, match="oracle_ref bos"):
            q.decide_with_oracle(t["esc_id"], True, "a", oracle_ref=bos)
    q.close()


def test_oracle_ledger_payload_taşir(tmp_path):
    """Ledger'a yazilan kayit oracle_ref tasiyor (denetci teyit edebilir)."""
    from sester.ledger import Ledger
    led = Ledger(str(tmp_path / "led.sqlite3"), secret="k")
    q = EscalationQueue(str(tmp_path / "esc3.db"), ledger=led, ttl_seconds=60)
    t = q.park("agent-f", "/api/y", 0.5, "rule-3")
    q.decide_with_oracle(
        t["esc_id"], approve=False, by="auditor-2",
        oracle_ref="kalshi.com/markets/XYZ/settled", note="pazar sonucu")

    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "led.sqlite3"))
    try:
        rows = conn.execute(
            "SELECT event_type, payload FROM events "
            "WHERE event_type IN ('escalation_approved','escalation_denied')"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    import json
    payload = json.loads(rows[0][1])
    assert payload["oracle_ref"] == "kalshi.com/markets/XYZ/settled"
    assert rows[0][0] == "escalation_denied"
    led.close()
    q.close()


def test_klasik_decide_oracle_taşimaz(tmp_path):
    """decide() (insan karari) oracle_ref eklemez — geri-uyumlu."""
    from sester.ledger import Ledger
    led = Ledger(str(tmp_path / "led2.sqlite3"), secret="k")
    q = EscalationQueue(str(tmp_path / "esc4.db"), ledger=led, ttl_seconds=60)
    t = q.park("agent-g", "/api/z", 0.5, "rule-4")
    q.decide(t["esc_id"], approve=True, by="human-1")

    import sqlite3, json
    conn = sqlite3.connect(str(tmp_path / "led2.sqlite3"))
    try:
        rows = conn.execute(
            "SELECT payload FROM events WHERE event_type='escalation_approved'"
        ).fetchall()
    finally:
        conn.close()
    payload = json.loads(rows[0][0])
    assert "oracle_ref" not in payload
    led.close()
    q.close()


# ----------------------------------------------- decide() davranış-testleri
# LEAD-2026-10-05 audit-kapanışı: EscalationQueue.decide — approve/reject
# yolları, opsiyonel-note, tek-yönlü-disiplin (consume-sonrası-dahil),
# decide'ın-kendi-TTL-süpürmesi ve (agent,resource)-izolasyonu.

def test_decide_approve_returns_full_ticket_consistent_with_get(q):
    """approve yolu: dönen bilet park'taki TÜM alanları korur (karar-yazımı
    orijinal-alanları-ezmez) ve DB'den-tekrar-okunduğu-için get() ile birebirdir."""
    t = q.park("agent-keep", "/keep", 7.50, "rule-keep", reason="neden-1")
    d = q.decide(t["esc_id"], approve=True, by="auditor-keep", note="tamam")
    assert d["esc_id"] == t["esc_id"]
    assert d["agent"] == "agent-keep"
    assert d["resource"] == "/keep"
    assert d["amount"] == 7.50
    assert d["rule_id"] == "rule-keep"
    assert d["reason"] == "neden-1"
    assert d["created_at"] == t["created_at"]
    assert d["expires_at"] == t["expires_at"]
    assert d["status"] == APPROVED
    assert d["decided_by"] == "auditor-keep"
    assert d["note"] == "tamam"
    assert d["decided_at"] is not None
    # dönen dict DB'den-tekrar-okunur → get() ile birebir-aynı
    assert q.get(t["esc_id"]) == d


def test_decide_approve_enables_approved_for(q):
    """approve yolu: onaydan-sonra approved_for(agent, resource) biletin-kendisini
    döner (decided_by + note ile) — bu tüketilebilir-onay-contract'idir."""
    t = q.park("agent-ap", "/ap", 3.00, "r-ap")
    assert q.approved_for("agent-ap", "/ap") is None
    d = q.decide(t["esc_id"], approve=True, by="onaylayan", note="go")
    ap = q.approved_for("agent-ap", "/ap")
    assert ap is not None
    assert ap["esc_id"] == d["esc_id"]
    assert ap["decided_by"] == "onaylayan"
    assert ap["note"] == "go"


def test_decide_deny_removes_from_pending_and_blocks_consumption(q):
    """reject yolu: denied bilet pending()'ten-düşer, approved_for yine None'dır
    ve consume red 'tek-kezlik-tüketim' kuralını-delmez."""
    t = q.park("agent-dn", "/dn", 12.00, "r-dn")
    assert any(r["esc_id"] == t["esc_id"] for r in q.pending())
    q.decide(t["esc_id"], approve=False, by="reddeden", note="çok pahalı")
    assert not any(r["esc_id"] == t["esc_id"] for r in q.pending())
    assert q.approved_for("agent-dn", "/dn") is None
    assert q.consume(t["esc_id"]) is False, "reddedilen bilet tüketilemez"
    assert q.get(t["esc_id"])["status"] == DENIED


def test_decide_note_optional_defaults_empty_and_persists_arbitrary(q):
    """note opsiyonel: verilmezse ''; uzun + unicode + tırnaklı-note aynen
    persist-olur (karar-gerekçesi denetim-icin-saklanır)."""
    t = q.park("agent-note", "/n", 1.00, "r-n")
    d0 = q.decide(t["esc_id"], approve=True, by="a")
    assert d0["note"] == ""
    assert q.get(t["esc_id"])["note"] == ""
    t2 = q.park("agent-note", "/n2", 1.00, "r-n")
    long_note = "ışık: äöüß-\"tırnak\"—" + "x" * 200
    d1 = q.decide(t2["esc_id"], approve=True, by="a", note=long_note)
    assert d1["note"] == long_note
    assert q.get(t2["esc_id"])["note"] == long_note


def test_decide_on_consumed_ticket_is_rejected(q):
    """tek-yönlü-disiplin consume-sonrası-da-geçerli: consumed bilete tekrar
    karar → ValueError (karar yalnızca-pending'de-verilir)."""
    t = q.park("agent-c", "/c", 2.00, "r-c")
    q.decide(t["esc_id"], approve=True, by="a")
    assert q.consume(t["esc_id"]) is True
    with pytest.raises(ValueError):
        q.decide(t["esc_id"], approve=False, by="too-late")
    with pytest.raises(ValueError):
        q.decide(t["esc_id"], approve=True, by="too-late")


def test_decide_sweeps_own_ttl_expirations_fail_closed(q, monkeypatch):
    """decide kendi _expire() süpürmesini-çalıştırır: TTL'i-dolmuş-pending,
    karar-anında expired'a-döner → fail-closed (sessiz post-expiry onay YOK),
    ValueError 'expired' sözcüğünü-taşır; durum-makinesi tek-yönlü."""
    t = q.park("agent-ex", "/ex", 4.00, "r-ex")
    real_time = esc_mod.time.time
    monkeypatch.setattr(esc_mod.time, "time", lambda: real_time() + 3600)
    with pytest.raises(ValueError, match="expired"):
        q.decide(t["esc_id"], approve=True, by="gec-onay")
    assert q.get(t["esc_id"])["status"] == EXPIRED
    assert q.approved_for("agent-ex", "/ex") is None


def test_decide_isolated_across_agent_resource_pairs(q):
    """bir biletin-kararı diğer (agent, resource) biletlerini-etkilemez —
    karar yanlışlıkla-komşu-kaynağa-taşmaz."""
    t1 = q.park("agent-iso-a", "/x", 5.00, "r")
    t2 = q.park("agent-iso-b", "/x", 5.00, "r")
    t3 = q.park("agent-iso-a", "/y", 5.00, "r")
    q.decide(t1["esc_id"], approve=False, by="a")
    assert q.get(t2["esc_id"])["status"] == PENDING, "komşu bilet bozuldu"
    assert q.get(t3["esc_id"])["status"] == PENDING, "komşu bilet bozuldu"
    assert q.approved_for("agent-iso-b", "/x") is None
    assert q.approved_for("agent-iso-a", "/y") is None
    q.decide(t3["esc_id"], approve=True, by="a")
    assert q.approved_for("agent-iso-a", "/y") is not None
    assert q.approved_for("agent-iso-b", "/x") is None, "izolasyon-delindi"
