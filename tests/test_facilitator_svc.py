"""SESTER S5 testleri — hosted-facilitator MVP (docs/S5_FACILITATOR_MILESTONE.md §3).

Kapsam: verify/settle çekirdeği (satıcı-tarafıyla AYNI parser-kompozisyonu),
idempotent-settle (nonce bir-kez), verify'in nonce-YAKMAMASI, satıcı-metering
(free-band + %1+$0.005), batch entegrasyonu (settlement.py, fail-closed),
HTTP yüzeyi (auth-guard 401; httpx ASGI-transport — ağ-izolasyonlu).
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod

import pytest

from sester.ledger import Ledger

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from sester.facilitator_svc import FacilitatorService, create_app  # noqa: E402

SECRET = "svc-test-secret"
PRICE_MINOR = 50_000  # 0.05


def hmac_payment(seller: str, nonce: str, amount_s: str, resource: str,
                 secret: str = SECRET) -> str:
    mac = hmac_mod.new(secret.encode(),
                       f"{seller}|{nonce}|{amount_s}|{resource}".encode(),
                       hashlib.sha256).hexdigest()
    return f"pugio0 {seller}:{nonce}:{amount_s}:{mac}"


@pytest.fixture()
def svc(tmp_path):
    led = Ledger(tmp_path / "svc.sqlite3", secret=SECRET)
    s = FacilitatorService(led, secret=SECRET, free_transactions=2)
    yield s
    led.close()


# ------------------------------------------------- S5.a verify

def test_186_verify_ok_writes_proof_event(svc):
    pay = hmac_payment("sat1", "n1", "0.05", "/weather")
    d = svc.verify(pay, "/weather")
    assert d.status == "ok" and d.reason == "verify_ok"
    evs = svc.ledger.export_events(agent_id="sat1")
    assert any(e["event_type"] == "facilitator_verify"
               and e["payload"] == '{"decision":"allow","rule_id":"verify_ok"}'
               for e in evs)


def test_187_verify_rejects_tampered_mac_fail_closed(svc):
    pay = hmac_payment("sat1", "n1", "0.05", "/weather")
    bad = pay[:-6] + "000000"
    d = svc.verify(bad, "/weather")
    assert d.status == "rejected" and "malformed" in d.reason


def test_188_verify_rejects_unknown_scheme(svc):
    d = svc.verify("weird-scheme a:b:c:d", "/weather")
    assert d.status == "rejected" and d.reason == "unknown_scheme"


# ------------------------------------------------- S5.b settle + idempotency

def test_189_verify_does_not_burn_nonce_then_settle_ok(svc):
    pay = hmac_payment("sat1", "n2", "0.05", "/weather")
    assert svc.verify(pay, "/weather").status == "ok"      # verify-only
    d = svc.settle(pay, "/weather", PRICE_MINOR)           # aynı zarf
    assert d.status == "ok" and d.reason == "settled"
    assert d.receipt["receipt"]


def test_190_settle_is_idempotent_second_is_replay(svc):
    pay = hmac_payment("sat1", "n3", "0.05", "/weather")
    assert svc.settle(pay, "/weather", PRICE_MINOR).status == "ok"
    d2 = svc.settle(pay, "/weather", PRICE_MINOR)
    assert d2.status == "rejected" and d2.reason == "replay_detected"


def test_191_settle_rejects_unknown_and_malformed(svc):
    assert svc.settle("weird x:y", "/weather", 1).reason == "unknown_scheme"
    bad = hmac_payment("sat1", "n4", "0.05", "/weather")[:-4] + "ffff"
    assert svc.settle(bad, "/weather", 1).status == "rejected"


# ------------------------------------------------- S5.d metering (free-band)

def test_192_metering_free_band_then_fee(svc):
    # svc free_transactions=2: tx1-2 bedava; tx3 ücretli (%1 + $0.005)
    for i in (1, 2):
        pay = hmac_payment("sat2", f"m{i}", "0.05", "/weather")
        d = svc.settle(pay, "/weather", PRICE_MINOR)
        assert d.status == "ok" and d.receipt["free_band"]
    pay = hmac_payment("sat2", "m3", "0.05", "/weather")
    d = svc.settle(pay, "/weather", PRICE_MINOR)
    assert d.status == "ok" and not d.receipt["free_band"]
    # round(50000*0.01)=500 + 5000 flat = 5500 minor = $0.0055
    assert d.receipt["charged_minor"] == 5_500
    inv = svc.seller_invoice("sat2")
    assert inv["transactions"] == 3 and inv["charged_minor"] == 5_500


# ------------------------------------------------- S5.e batch entegrasyonu

def test_193_build_batch_produces_calldata_and_proof(svc):
    for i in (1, 2):
        svc.settle(hmac_payment("sat3", f"b{i}", "0.05", "/weather"),
                   "/weather", PRICE_MINOR)
    b = svc.build_batch("sat3")
    assert b["calldata"].startswith("0x")
    assert len(b["merkle_root"]) == 66          # 0x + 32-byte keccak
    assert b["total_minor"] == 100_000          # 2×0.05
    assert b["chain_id"] == svc.chain_id
    evs = svc.ledger.export_events(agent_id="sat3")
    assert any(e["event_type"] == "facilitator_batch" for e in evs)


def test_193b_build_batch_fail_closed_on_broken_chain(svc, tmp_path):
    from sester.settlement import SettlementError

    led2 = Ledger(tmp_path / "broken.sqlite3", secret=SECRET)
    try:
        s2 = FacilitatorService(led2, secret=SECRET)
        s2.settle(hmac_payment("satx", "z1", "0.05", "/weather"),
                  "/weather", PRICE_MINOR)
        # zinciri yerinde kurcala (hash-değerini değiştir — verify_chain kırılır)
        conn = led2.conn
        conn.execute("UPDATE events SET hash=? WHERE seq=1", ("00" * 32,))
        conn.commit()
        with pytest.raises(SettlementError):
            s2.build_batch("satx")
    finally:
        led2.close()


# ------------------------------------------------- HTTP yüzeyi (test_194)

def test_193b_facilitator_secret_fail_closed(tmp_path, monkeypatch):
    """x402-audit (2026-09-20): secret-yokken-açılış tahmin-edilebilir
    varsayılan-key'le-değil, RuntimeError-la-fail-etsin (fail-closed).
    Eski-davranış: secret='facilitator-secret' varsayılanı → auth-key
    SHA256-türevi-tahmin-edilebilir → uzaktan-refund. Üç-yol-da-kilitli:
    (a) secret=None + env-yok, (b) secret='' + env-yok, (c) env-set + secret=None
    → env-kullanılır (üretim-yolu-çalışır)."""
    import os as _os
    from sester.facilitator_svc import FacilitatorService, create_app

    led = Ledger(str(tmp_path / "f.db"), secret=SECRET)
    try:
        # (a) + (b): env'i-temizle, secret-verme/boş
        monkeypatch.delenv("SESTER_FACILITATOR_SECRET", raising=False)
        with pytest.raises(RuntimeError):
            FacilitatorService(led)
        with pytest.raises(RuntimeError):
            FacilitatorService(led, secret="")
        with pytest.raises(RuntimeError):
            create_app(led)
        # (c): env-set-i-çin-secret-geçilmez → env-okunur, açılır
        monkeypatch.setenv("SESTER_FACILITATOR_SECRET", "prod-secret-x")
        s = FacilitatorService(led)  # çalışmalı
        assert s.secret == b"prod-secret-x"
    finally:
        led.close()


@pytest.fixture()
def app(svc):
    return create_app(svc.ledger, secret=SECRET, auth_key="k-test")


def test_194_http_auth_guard_and_happy_paths(app):
    from fastapi.testclient import TestClient

    client = TestClient(app)
    # auth yok / bozuk → 401
    r = client.post("/verify", json={"payment": "pugio0 a:b:c:d", "resource": "/w"})
    assert r.status_code == 401
    r = client.post("/verify", json={"payment": "pugio0 a:b:c:d", "resource": "/w"},
                    headers={"X-Facilitator-Key": "yanlis"})
    assert r.status_code == 401
    # temiz akış
    pay = hmac_payment("sat4", "h1", "0.05", "/weather")
    r = client.post("/verify", json={"payment": pay, "resource": "/weather"},
                    headers={"X-Facilitator-Key": "k-test"})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    r = client.post("/settle",
                    json={"payment": pay, "resource": "/weather",
                          "amount_minor": PRICE_MINOR},
                    headers={"X-Facilitator-Key": "k-test"})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    r2 = client.post("/settle",
                     json={"payment": pay, "resource": "/weather",
                           "amount_minor": PRICE_MINOR},
                     headers={"X-Facilitator-Key": "k-test"})
    assert r2.json()["status"] == "rejected"      # idempotent
    from sester import __version__ as pkg_version

    hz = client.get("/healthz").json()
    assert hz["chain_valid"] is True and hz["version"] == pkg_version
    panel = client.get("/panel", headers={"X-Facilitator-Key": "k-test"}).json()
    assert "sat4" in panel["sellers"]


def test_195_http_negative_amount_422(app):
    from fastapi.testclient import TestClient

    client = TestClient(app)
    pay = hmac_payment("sat5", "h2", "0.05", "/weather")
    r = client.post("/settle",
                    json={"payment": pay, "resource": "/weather",
                          "amount_minor": -1},
                    headers={"X-Facilitator-Key": "k-test"})
    assert r.status_code == 422
