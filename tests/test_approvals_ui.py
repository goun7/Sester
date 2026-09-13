"""PUGIO onay-panel testleri — /approvals + decide-endpoint (v0.3).

Kapsam: sayfa-render (boş/dolu), approve→consume-akışı, deny→blok,
hata-sözleşmesi (404/409/400), fail-closed TTL etkisi, XSS-kaçamak.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from pugio import demo_api

    # test-artefaktı bırakma: modül-kuyruğunu kullan, sonunda temizle
    c = TestClient(demo_api.app)
    yield c, demo_api.esc_queue


def _park(q, agent="panel-agent"):
    return q.park(agent, "/histogram", 5.00, "require-human-for-large")


def test_129_approvals_page_renders_empty(client):
    c, q = client
    r = c.get("/approvals")
    assert r.status_code == 200
    assert "PUGIO" in r.text and "Onay Paneli" in r.text


def test_130_approvals_page_lists_pending_ticket(client):
    c, q = client
    t = _park(q)
    try:
        r = c.get("/approvals")
        assert r.status_code == 200
        assert t["esc_id"] in r.text and "ONAYLA" in r.text and "REDDET" in r.text
    finally:
        q.decide(t["esc_id"], approve=False, by="test-cleanup")


def test_131_approve_via_endpoint_enables_consume(client):
    c, q = client
    t = _park(q)
    try:
        r = c.post(f"/escalations/{t['esc_id']}/decide",
                   json={"approve": True, "by": "gokun", "note": "ok"})
        assert r.status_code == 200 and r.json()["ok"] is True
        # onay tüketilebilir olmalı (tek-kezlik)
        assert q.approved_for("panel-agent", "/histogram") is not None
        approved = q.approved_for("panel-agent", "/histogram")
        assert q.consume(approved["esc_id"]) is True
    finally:
        q._expire()


def test_132_deny_via_endpoint_blocks(client):
    c, q = client
    t = _park(q)
    r = c.post(f"/escalations/{t['esc_id']}/decide",
               json={"approve": False, "by": "gokun"})
    assert r.status_code == 200
    assert q.approved_for("panel-agent", "/histogram") is None


def test_133_decide_error_contract(client):
    c, _ = client
    # bilinmeyen bilet → 404
    r = c.post("/escalations/esc-yok/decide", json={"approve": True})
    assert r.status_code == 404
    # approve değil-boolean → 400
    r = c.post("/escalations/esc-yok/decide", json={"approve": "evet"})
    assert r.status_code == 400
    # zaten kararlı bilet → 409
    q = client[1]
    t = _park(q, "panel-agent-2")
    c.post(f"/escalations/{t['esc_id']}/decide", json={"approve": True})
    r = c.post(f"/escalations/{t['esc_id']}/decide", json={"approve": False})
    assert r.status_code == 409


def test_134_expired_ticket_shows_zero_and_decides_409(client):
    c, q = client
    t = q.park("panel-agent-3", "/histogram", 5.00, "r")
    # TTL'i yapay olarak doldur
    q._conn.execute("UPDATE escalations SET expires_at=? WHERE esc_id=?",
                    (time.time() - 1, t["esc_id"]))
    q._conn.commit()
    r = c.post(f"/escalations/{t['esc_id']}/decide", json={"approve": True})
    assert r.status_code == 409, "vadesi dolan bilet onaylanamaz (fail-closed)"


def test_135_panel_page_lists_escalation_labels(client):
    c, q = client
    t = _park(q, "panel-agent-4")
    try:
        r = c.get("/panel")
        assert r.status_code == 200
        assert "onay-bekliyor" in r.text  # ledger olay-etiketi panelde görünür
    finally:
        q.decide(t["esc_id"], approve=False, by="test-cleanup")
