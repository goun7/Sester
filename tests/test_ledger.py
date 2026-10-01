"""SESTER ledger + middleware testleri — zincir-bütünlüğü, replay, kota, sayaç-çakışma."""

from __future__ import annotations

import asyncio
import hmac
import hashlib
import json
import threading

import pytest

from sester.ledger import Ledger
from sester.middleware import SesterMeter

SECRET = "t-secret"


# ---------- yardımcılar ----------

def mac_of(agent: str, nonce: str, amount: str, path: str) -> str:
    return hmac.new(SECRET.encode(), f"{agent}|{nonce}|{amount}|{path}".encode(),
                    hashlib.sha256).hexdigest()


def payment_header(agent: str, nonce: str, amount: str, path: str) -> str:
    return f"pugio0 {agent}:{nonce}:{amount}:{mac_of(agent, nonce, amount, path)}"  # pugio0: DONUK şema


async def dummy_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": b'{"ok":true}'})


def make_meter(tmp_path, ledger, **kw):
    kw.setdefault("price", 0.05)
    kw.setdefault("daily_quota", 25.0)
    kw.setdefault("secret", SECRET)
    return SesterMeter(dummy_app, ledger, **kw)


# ---------- v0.2: kalıcı replay-koruması ----------

def test_64_claim_nonce_first_writer_wins(tmp_path):
    led = Ledger(tmp_path / "n.sqlite3", secret="test-secret-at179")
    assert led.claim_nonce("a", "n1") is True
    assert led.claim_nonce("a", "n1") is False
    assert led.claim_nonce("a", "n2") is True
    assert led.claim_nonce("b", "n1") is True  # farklı ajan = farklı anahtar
    led.close()


def test_65_claim_nonce_survives_reopen(tmp_path):
    path = tmp_path / "n2.sqlite3"
    led1 = Ledger(path, secret="test-secret-at179")
    led1.claim_nonce("a", "kalici")
    led1.close()
    led2 = Ledger(path, secret="test-secret-at179")
    assert led2.claim_nonce("a", "kalici") is False  # restart pencere sıfırlamaz
    led2.close()


def test_66_middleware_replay_persists_across_meters(tmp_path):
    path = tmp_path / "n3.sqlite3"
    h = payment_header("f1", "kalici-n", "0.05", "/weather")
    led1 = Ledger(path, secret=SECRET)
    m1 = make_meter(tmp_path, led1)
    s1, _, _ = call(m1, "/weather", {"X-Payment": h})
    led1.close()
    led2 = Ledger(path, secret=SECRET)
    m2 = make_meter(tmp_path, led2)
    s2, _, body = call(m2, "/weather", {"X-Payment": h})
    assert s1 == 200 and s2 == 402
    assert json.loads(body)["error"] == "replay_detected"
    led2.close()


def call(meter, path, headers=None):
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        messages.append(m)

    scope = {"type": "http", "method": "GET", "path": path,
             "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]}
    asyncio.run(meter(scope, receive, send))
    start = messages[0]
    hdrs = {k.decode(): v.decode() for k, v in start.get("headers", [])}
    body = b"".join(m.get("body", b"") for m in messages[1:] if m["type"] == "http.response.body")
    return start["status"], hdrs, body


# ---------- ledger ----------

def test_23_append_and_verify_chain(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")
    for i in range(5):
        led.append("charge_receipt", f"agent-{i % 2}", "/weather", 0.05)
    assert led.verify_chain() is True
    led.close()


def test_24_chain_detects_tampering(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")
    for i in range(3):
        led.append("charge_receipt", "a", "/weather", 0.05)
    led.conn.execute("UPDATE events SET amount=999 WHERE seq=2")  # inkâr-saldırısı
    assert led.verify_chain() is False
    led.close()


def test_25_spent_today_nets_refunds(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")
    led.append("charge_receipt", "a", "/weather", 0.05)
    led.append("charge_receipt", "a", "/weather", 0.05)
    led.append("refund", "a", "/weather", 0.03)
    assert abs(led.spent_today("a") - 0.07) < 1e-9
    led.close()


def test_26_per_agent_summary_and_recent(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")
    led.append("charge_receipt", "a", "/weather", 0.05)
    led.append("charge_receipt", "b", "/weather", 0.10)
    s = {r["agent_id"]: r for r in led.per_agent_summary()}
    assert s["a"]["calls"] == 1 and abs(s["b"]["spent"] - 0.10) < 1e-9
    assert len(led.recent_events(10)) == 2
    led.close()


def test_27_parallel_appends_chain_intact(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")

    def worker(n):
        for i in range(10):
            led.append("charge_receipt", f"agent-{n}", "/weather", 0.01)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    n = led.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert n == 80
    assert led.verify_chain() is True
    led.close()


# ---------- middleware ----------

def test_28_no_payment_gets_402_challenge(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")
    m = make_meter(tmp_path, led)
    status, hdrs, body = call(m, "/weather")
    assert status == 402
    assert "x-payment-required" in hdrs
    ch = json.loads(body)
    assert ch["accepts"][0]["maxAmountRequired"] == "0.050000"
    led.close()


def test_29_valid_payment_passes_with_receipt(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")
    m = make_meter(tmp_path, led)
    h = payment_header("f1", "n1", "0.05", "/weather")
    status, hdrs, _ = call(m, "/weather", {"X-Sester-Agent": "f1", "X-Payment": h})
    assert status == 200
    assert "x-sester-receipt" in hdrs and "x-sester-seq" in hdrs
    kinds = [e["event_type"] for e in led.recent_events(10)]
    assert "charge_receipt" in kinds
    led.close()


def test_30_bad_signature_denied(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")
    m = make_meter(tmp_path, led)
    bad = f"pugio0 f1:n1:0.05:{'0' * 64}"
    status, _, body = call(m, "/weather", {"X-Payment": bad})
    assert status == 402
    assert json.loads(body)["error"].startswith("malformed_payment")  # + HMAC-detayı
    led.close()


def test_31_amount_too_low_denied(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")
    m = make_meter(tmp_path, led)
    h = payment_header("f1", "n1", "0.01", "/weather")
    status, _, body = call(m, "/weather", {"X-Payment": h})
    assert status == 402
    assert json.loads(body)["error"] == "amount_too_low"
    led.close()


def test_32_replay_denied(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")
    m = make_meter(tmp_path, led)
    h = payment_header("f1", "ayni-nonce", "0.05", "/weather")
    s1, _, _ = call(m, "/weather", {"X-Payment": h})
    s2, _, body = call(m, "/weather", {"X-Payment": h})
    assert s1 == 200 and s2 == 402
    assert json.loads(body)["error"] == "replay_detected"
    led.close()


def test_33_quota_exceeded_at_daily_cap(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")
    m = make_meter(tmp_path, led, daily_quota=0.10)  # 2 çağrı sığar
    ok = [call(m, "/weather", {"X-Payment": payment_header("f1", f"n{i}", "0.05", "/weather")})[0]
          for i in range(3)]
    assert ok == [200, 200, 402]
    led.close()


def test_34_exempt_paths_bypass_meter(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")
    m = make_meter(tmp_path, led)
    status, _, _ = call(m, "/panel")
    assert status == 200  # ödeme-istemi yok
    led.close()


def test_35_malformed_payment_denied(tmp_path):
    led = Ledger(tmp_path / "t.sqlite3", secret="test-secret-at179")
    m = make_meter(tmp_path, led)
    status, _, body = call(m, "/weather", {"X-Payment": "pugio0 onlyonefield"})
    assert status == 402
    assert json.loads(body)["error"].startswith("malformed_payment")
    led.close()


def test_36_spent_today_utc_day_boundary(tmp_path):
    """Gün-sınırı UTC-midnight'a-sabitli: ts(UTC-epoch) ↔ pencere(UTC).

    Kök-neden (2026-09-28): spent_today time.mktime kullanıyordu — mktime
    YEREL-TZ'i-yorumlar-AMA ts-sütunu time.time() ile UTC-yazılır. TZ≠UTC'de
    gün-sınırında-kayma → kota-hesabı-yanlış. Düzeltme: calendar.timegm.
    Bu-test TZ-bağımsız-doğrular: gün-son-çağrısı hâlâ-hesapta-olmalı.
    """
    led = Ledger(tmp_path / "t.sqlite3", secret="test-tz36")
    # bugünün-UTC-tarihinde-events-yaz (ts-UTC-epoch — Ledger.doğal-yolu)
    for i in range(3):
        led.append("charge_receipt", "tz-agent", "h", amount=10.0)
    total = led.spent_today("tz-agent")
    assert total == 30.0, f"UTC-gün-sınırı-kayması: {total} ≠ 30.0"
    # gün-dışı-kontrol: dünü-sorgula → 0 (pencere-dışı)
    import time as _t
    yesterday = _t.strftime("%Y-%m-%d", _t.gmtime(_t.time() - 86400))
    assert led.spent_today("tz-agent", day=yesterday) == 0.0
    led.close()


# LEAD 2026-10-01 — x402 #2332 post-settlement accountability
# "Loglar yeniden yazilabilir; hash-chain anchor olamaz."
# Ucuncu taraf (regulator/auditor) sadece sha256 ile bagimsiz dogrular.
def test_anchor_external_verification_detects_tamper(tmp_path):
    """Harici dogrulayici: ledger temiz i True, cozumlu payload hack'i False."""
    import sqlite3

    led = Ledger(str(tmp_path / "anchor.sqlite3"), secret="k")
    led.append("permission_decision", "agent-a", "/paid", 1.0,
               payload={"decision": "allow"})
    led.append("charge_receipt", "agent-a", "/paid", 0.05,
               payload={"amount_minor": 50000, "currency": "USDC"})
    led.append("permission_decision", "agent-a", "/other", 1.0,
               payload={"decision": "deny"})

    # 1) temiz ledger → bagimsiz dogrulama gecer
    assert led.verify_chain() is True

    # 2) cozumcu 'allow' kararini 'deny' olarak degistirir (EU AI Act log saldirisi)
    conn = sqlite3.connect(str(tmp_path / "anchor.sqlite3"))
    try:
        conn.execute(
            'UPDATE events SET payload=? WHERE rowid=1',
            (json.dumps({"decision": "deny"}),))
        conn.commit()
    finally:
        conn.close()

    # 3) anchor tespit eder: chain kopar
    assert led.verify_chain() is False, "hash-chain anchor tespit etmeli"
    led.close()


# ayni bagimsiz dogrulama FARKLI secret ile yapilamaz (fail-closed)
def test_anchor_verification_rejects_wrong_secret(tmp_path):
    """Yanlis secret → bagimsiz dogrulama reddeder (trust anchor binding)."""
    led = Ledger(str(tmp_path / "anchor2.sqlite3"), secret="dogru")
    led.append("permission_decision", "agent-a", "/paid", 1.0,
               payload={"decision": "allow"})
    led.close()

    led2 = Ledger(str(tmp_path / "anchor2.sqlite3"), secret="yanlis")
    assert led2.verify_chain() is False, "yanlis secret ile dogrulama reddedilir"
    led2.close()
