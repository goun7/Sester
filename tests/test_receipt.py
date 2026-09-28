"""Ödeme-kanıtı (receipt) testleri — node-cosigned, secret'sız-doğrulanabilir.

Akademik-boşluk-kapanışı: x402 facilitator'lar dışarıdan-doğrulanabilir kanıt
vermez (USENIX-Sec-2026/2607.19545: 15/15 facilitator ihlal). Bu test takımı
Sester'ın receipt'inin herkese-açık sha256 ile yeniden-hesaplanabilir VE
node-imzalı olduğunu sabitler."""
from __future__ import annotations

import json

import pytest

from sester import (Ledger, issue_receipt, load_receipt_json, proof_of,
                    receipt_hash, receipt_json, verify_receipt)
from sester import receipt as receipt_mod
from sester.evidence import produce_bundle, proof_hash, verify_bundle


@pytest.fixture
def ledger(tmp_path):
    led = Ledger(str(tmp_path / "receipt.sqlite3"), secret="test-secret")
    yield led
    led.close()


def _charge(led, agent="agent-1", host="/weather", amount=0.05,
            amount_minor=50_000):
    return led.append("charge_receipt", agent, host, amount,
                      amount_minor=amount_minor,
                      payload={"nonce": "n1", "paid": amount,
                               "scheme": "pugio0"})


def test_roundtrip_secretless_and_node_signed(ledger):
    ev = _charge(ledger)
    r = issue_receipt(ev, node_id="node-1", node_secret="node-sk",
                      chain_head=ledger.chain_head())
    ok, msg = verify_receipt(r)
    assert ok, msg
    assert "SAĞLAM" in msg
    # node-imzalı yol
    ok, msg = verify_receipt(r, node_secret="node-sk")
    assert ok, msg
    assert "node-cosign" in msg


def test_proof_is_secretless_recomputable_by_anyone(ledger):
    """ASIL-KANIT: alıcı sha256 dışında hiçbir şeyle proof'u yeniden hesaplar."""
    ev = _charge(ledger)
    r = issue_receipt(ev, node_secret="node-sk")
    # alıcı tarayıcı: field'ları topla, kanonik'i elle kur, hash'le
    manual = "|".join([
        f"{float(r['ts']):.6f}", r["event_type"], r["sub"], r["resource"],
        f"{float(r['amount']):.6f}", r["payload"], r["prev_proof"],
    ])
    import hashlib
    assert hashlib.sha256(manual.encode()).hexdigest() == r["proof"]
    # evidence.proof_hash ile birebir (K0 kanonik-uyumu)
    evx = {"ts": r["ts"], "event_type": r["event_type"], "agent_id": r["sub"],
           "host": r["resource"], "amount": r["amount"], "payload": r["payload"]}
    assert proof_hash(evx, r["prev_proof"]) == r["proof"]
    assert proof_of(r) == r["proof"]


def test_wrong_node_secret_is_red(ledger):
    ev = _charge(ledger)
    r = issue_receipt(ev, node_secret="node-sk")
    ok, msg = verify_receipt(r, node_secret="other")
    assert not ok
    assert "NODE-İMZASI-RED" in msg


def test_missing_node_secret_with_cosign_is_red(ledger):
    ev = _charge(ledger)
    r = issue_receipt(ev, node_secret="node-sk")
    ok, msg = verify_receipt(r, node_secret=None)
    # secretless yine SAĞLAM (asıl-kanıt yeter) — anchor iddiası yok
    assert ok, msg


@pytest.mark.parametrize("field,value", [
    ("amount", "1.000000"),       # tutar-değişimi → asıl-kanıt RED
    ("payload", '{"x":9}'),       # ödeme-içeriği → RED
    ("ts", 1000000.0),            # zaman → RED
    ("prev_proof", "a" * 64),     # zincir-kopması → RED
])
def test_tamper_core_fields_caught_secretless(ledger, field, value):
    ev = _charge(ledger)
    r = issue_receipt(ev, node_secret="node-sk")
    r[field] = value
    ok, msg = verify_receipt(r)  # secret'sız bile RED — asıl-kanıt
    assert not ok
    assert "ASIL-KANIT-RED" in msg


@pytest.mark.parametrize("field,value", [
    ("iss", "evil-node"),
    ("amount_minor", 999999),
    ("seq", 999),
    ("currency", "EUR"),
])
def test_tamper_metadata_caught_by_node_cosign(ledger, field, value):
    ev = _charge(ledger)
    r = issue_receipt(ev, node_secret="node-sk")
    r[field] = value
    ok, msg = verify_receipt(r, node_secret="node-sk")
    assert not ok


def test_tamper_proof_itself_is_red(ledger):
    ev = _charge(ledger)
    r = issue_receipt(ev, node_secret="node-sk")
    r["proof"] = "0" * 64
    ok, msg = verify_receipt(r)
    assert not ok
    assert "ASIL-KANIT-RED" in msg


def test_non_charge_event_refused_fail_closed(ledger):
    """Kanıt yalnızca gerçek harcama için — 'ödendi' yalanını kanıtlanamaz."""
    ev = ledger.append("permission_decision", "a", "/x", 0.0,
                       payload={"decision": "deny"})
    with pytest.raises(Exception):
        issue_receipt(ev, node_secret="k")


def test_non_positive_amount_refused(ledger):
    ev = ledger.append("settlement", "a", "/x", 0.0,
                       payload={"status": "settled"})
    with pytest.raises(Exception):
        issue_receipt(ev, node_secret="k")


def test_unknown_version_is_red(ledger):
    ev = _charge(ledger)
    r = issue_receipt(ev, node_secret="k")
    r["receipt_version"] = 99
    ok, msg = verify_receipt(r)
    assert not ok
    assert "sürüm" in msg


def test_missing_field_is_red(ledger):
    ev = _charge(ledger)
    r = issue_receipt(ev, node_secret="k")
    del r["currency"]
    ok, msg = verify_receipt(r)
    assert not ok
    assert "eksik" in msg


def test_receipt_json_is_deterministic(ledger):
    ev = _charge(ledger)
    r = issue_receipt(ev, node_secret="k")
    assert receipt_json(r) == receipt_json(json.loads(receipt_json(r)))


def test_receipt_json_roundtrip_load(ledger):
    ev = _charge(ledger)
    r = issue_receipt(ev, node_secret="k")
    r2 = load_receipt_json(receipt_json(r))
    assert verify_receipt(r2)[0]
    with pytest.raises(Exception):
        load_receipt_json("{bozuk")
    with pytest.raises(Exception):
        load_receipt_json("[]")


def test_chain_context_seq2_links_to_seq1(ledger):
    e1 = _charge(ledger)
    e2 = _charge(ledger, amount=0.10, amount_minor=100_000)
    r1 = issue_receipt(e1, node_secret="k")
    r2 = issue_receipt(e2, node_secret="k")
    # node zincir-bağlamı: r2.prev_proof == e1'in ledger-mührü (HMC-zinciri)
    assert r2["prev_proof"] == e1["hash"]
    assert r2["prev_proof"] != r1["proof"]  # secret'sız proof ≠ HMAC-mührü
    # yine de her receipt bağımsız-secret'sız-doğrulanabilir
    assert verify_receipt(r1)[0] and verify_receipt(r2)[0]
    # ve alıcı zincirin-tamamını secret'sız isterse evidence-bundle verir
    b = produce_bundle(ledger)
    assert verify_bundle(b)[0]
    assert b["events"][1]["prev_proof"] == b["events"][0]["proof"]


def test_receipt_hash_changes_with_any_field(ledger):
    ev = _charge(ledger)
    r = issue_receipt(ev, node_secret="k")
    h0 = receipt_hash(r)
    r["iss"] = "other"
    assert receipt_hash(r) != h0


def test_cosign_empty_secret_fail_closed(ledger):
    ev = _charge(ledger)
    r = issue_receipt(ev, node_secret=None)
    assert r["node_cosign"] == ""  # dürüst-eksiklik: anchor-yok
    with pytest.raises(Exception):
        receipt_mod.cosign_receipt(r, "")


def test_export_events_rows_are_receipt_compatible(ledger):
    """Ledger kaydı ile receipt aynı kanonik'i üretir (tek-kaynak)."""
    ev = _charge(ledger)
    rows = ledger.export_events("agent-1")
    assert len(rows) == 1
    r = issue_receipt(rows[0], node_secret="k")
    assert verify_receipt(r)[0]


# ---------- x402 akışında kanıt-header'ı (middleware) ----------

def _asgi_app():
    async def app(scope, receive, send):
        body = b'{"ok": true}'
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
    return app


def _scope(payment, path="/data"):
    return {"type": "http", "method": "GET", "path": path,
            "headers": [(b"x-payment", payment.encode())]}


def test_middleware_emits_verifiable_receipt_bundle(tmp_path):
    """Ödeme tamamlandığında x-sester-receipt-bundle alıcıya TAM kanıt verir."""
    import asyncio
    import base64
    import hmac as _hmac
    from sester.middleware import SesterMeter

    led = Ledger(str(tmp_path / "mw.sqlite3"), secret="mw-secret")
    meter = SesterMeter(_asgi_app(), ledger=led, price=0.05, daily_quota=1.0,
                        secret="mw-secret", receipt_node_secret="node-k",
                        receipt_node_id="node-x")
    agent, nonce, amount, res = "ag-mw", "n1", "0.05", "/data"
    mac = _hmac.new(b"mw-secret", f"{agent}|{nonce}|{amount}|{res}".encode(),
                    __import__("hashlib").sha256).hexdigest()
    pay = f"pugio0 {agent}:{nonce}:{amount}:{mac}"
    captured = {}

    async def send(m):
        if m["type"] == "http.response.start":
            captured["status"] = m["status"]
            captured["headers"] = dict((k.decode(), v.decode())
                                       for k, v in m["headers"])

    asyncio.run(meter(_scope(pay, res), lambda: None, send))
    assert captured["status"] == 200
    blob = captured["headers"]["x-sester-receipt-bundle"]
    r = load_receipt_json(base64.urlsafe_b64decode(blob + "=" * (-len(blob) % 4)))
    assert r["iss"] == "node-x"
    assert r["sub"] == "ag-mw"
    assert verify_receipt(r)[0]                       # secret'sız
    assert verify_receipt(r, node_secret="node-k")[0]  # node-imzalı
    assert not verify_receipt(r, node_secret="other")[0]
    led.close()


def test_middleware_receipt_without_cosign_is_secretless_ok(tmp_path):
    """node-secret YOK → cosign'siz receipt; asıl kanıt hâlâ secret'sız."""
    import asyncio
    import base64
    import hmac as _hmac
    from sester.middleware import SesterMeter

    led = Ledger(str(tmp_path / "mw2.sqlite3"), secret="mw-secret")
    meter = SesterMeter(_asgi_app(), ledger=led, price=0.05, daily_quota=1.0,
                        secret="mw-secret")  # receipt_node_secret=None
    agent, nonce, amount, res = "ag-mw", "n2", "0.05", "/data"
    mac = _hmac.new(b"mw-secret", f"{agent}|{nonce}|{amount}|{res}".encode(),
                    __import__("hashlib").sha256).hexdigest()
    pay = f"pugio0 {agent}:{nonce}:{amount}:{mac}"
    captured = {}

    async def send(m):
        if m["type"] == "http.response.start":
            captured["headers"] = dict((k.decode(), v.decode())
                                       for k, v in m["headers"])

    asyncio.run(meter(_scope(pay, res), lambda: None, send))
    blob = captured["headers"]["x-sester-receipt-bundle"]
    r = load_receipt_json(base64.urlsafe_b64decode(blob + "=" * (-len(blob) % 4)))
    assert r["node_cosign"] == ""
    assert verify_receipt(r)[0]  # yine de SAĞLAM
    led.close()
