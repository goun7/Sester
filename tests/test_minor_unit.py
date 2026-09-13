"""SESTER minör-birim testleri — v0.4 tam-sayı sayaç-kolonu (dual-read, tek-yaz).

K0 kontratı korunur: canonical_line donmuştur — amount_minor kolonu zincir-
hash'lerine girmez; hash-koruyan migrasyon ve eski-bundle doğrulaması bozulmaz.
"""

from __future__ import annotations

import json

import pytest

from sester.evidence import produce_bundle, verify_bundle
from sester.ledger import Ledger, MINOR
from sester.pg_ledger import PgLedger

PG_DSN = __import__("os").environ.get("SESTER_PG_DSN", "")


def test_167_minor_column_chain_neutral(tmp_path):
    """Kolona rağmen zincir-hash'leri değişmez: aynı olaylar, kolonlu ledger
    ile donmuş-format beklentisi — verify_chain SAĞLAM."""
    led = Ledger(tmp_path / "m1.sqlite3", secret="s-minor")
    led.append("charge_receipt", "ag-m", "/weather", 0.05,
               amount_minor=50_000, payload={"nonce": "n1"})
    led.append("refund", "ag-m", "/weather", 0.05, amount_minor=50_000)
    assert led.verify_chain(), "amount_minor zinciri bozdu"
    # kolon gerçekten yazıldı
    evs = led.export_events("ag-m")
    assert evs[0]["amount_minor"] == 50_000 and evs[1]["amount_minor"] == 50_000


def test_168_legacy_rows_backfill_and_dual_read(tmp_path):
    """Eski DB (kolon=NULL) + backfill → spent_today_minor tam-sayı okur."""
    led = Ledger(tmp_path / "m2.sqlite3", secret="s-minor")
    led.append("charge_receipt", "ag-l", "/x", 0.05)
    led.append("charge_receipt", "ag-l", "/x", 0.10)
    # kolon-null simülasyonu (eski-kayıt)
    led.conn.execute("UPDATE events SET amount_minor = NULL")
    assert led.spent_today_minor("ag-l") == 150_000      # NULL → major'dan türetim
    assert led.spent_today("ag-l") == pytest.approx(0.15)
    n = led.backfill_amount_minor()
    assert n == 2
    assert led.spent_today_minor("ag-l") == 150_000      # kolondan
    # ikinci koşum idempotent
    assert led.backfill_amount_minor() == 0


def test_169_spent_today_minor_refund_and_precision(tmp_path):
    """refund negatif-düşer; float-akümülasyonu yok (tam-sayı aritmetik)."""
    led = Ledger(tmp_path / "m3.sqlite3", secret="s-minor")
    led.append("charge_receipt", "ag-r", "/x", 0.05, amount_minor=50_000)
    led.append("charge_receipt", "ag-r", "/x", 0.05, amount_minor=50_000)
    led.append("refund", "ag-r", "/x", 0.05, amount_minor=50_000)
    assert led.spent_today_minor("ag-r") == 50_000
    # kolon-yok (NULL) + türetim-yolu da refund'ı düşer
    led.conn.execute("UPDATE events SET amount_minor = NULL")
    assert led.spent_today_minor("ag-r") == 50_000


def test_170_insert_event_preserves_minor_migration(tmp_path):
    """Hash-koruyan migrasyon kolonu da taşır — hedef zincir SAĞLAM."""
    src = Ledger(tmp_path / "src.sqlite3", secret="s-mig")
    src.append("charge_receipt", "ag-mig", "/x", 0.07,
               amount_minor=70_123, payload={"nonce": "z"})
    ev = src.export_events("ag-mig")[0]
    assert ev["amount_minor"] == 70_123

    dst = Ledger(tmp_path / "dst.sqlite3", secret="s-mig")
    dst.insert_event(ev)
    got = dst.export_events("ag-mig")[0]
    assert got["hash"] == ev["hash"] and got["amount_minor"] == 70_123
    assert dst.verify_chain() and src.verify_chain()


def test_171_bundle_unaffected_by_minor_column(tmp_path):
    """K0 kontratı: bundle kanıt-hash'leri kolondan bağımsız — doğrulayıcı SAĞLAM."""
    led = Ledger(tmp_path / "m5.sqlite3", secret="s-b")
    led.append("charge_receipt", "ag-b", "/x", 0.05,
               amount_minor=50_000, payload={"nonce": "k1"})
    b = produce_bundle(led, agent_id="ag-b")
    ok, why = verify_bundle(b)
    assert ok, why
    # bundle olay-şeması değişmedi (minor alanı taşımıyor — K0 donmuş)
    assert "amount_minor" not in b["events"][0]


def _scenario(led):
    led.append("permission_decision", "ag-mp", "/x",
               payload={"decision": "deny", "rule_id": "replay"})
    led.append("charge_receipt", "ag-mp", "/x", 0.05,
               amount_minor=50_000, payload={"nonce": "p1"})
    led.append("refund", "ag-mp", "/x", 0.05, amount_minor=50_000)
    led.claim_nonce("ag-mp", "p1")


def test_172_pg_minor_parity(tmp_path, monkeypatch):
    if not PG_DSN:
        pytest.skip("SESTER_PG_DSN yok — PG-bacağı atlanır")
    # bundle-paritesi için deterministik saat (proof'lar ts içerir — test_141 düzeni)
    import time as _t

    base = {"t": _t.time()}
    state = {"n": 0}

    def fake():
        state["n"] += 1
        return base["t"] + state["n"] * 0.001

    monkeypatch.setattr(_t, "time", fake)

    s = Ledger(tmp_path / "parity-minor-sqlite.sqlite3", secret="s-mp")
    p = PgLedger(secret="s-mp", dsn=PG_DSN)
    with p.conn().cursor() as cur:
        cur.execute("TRUNCATE events RESTART IDENTITY")
        cur.execute("TRUNCATE seen_nonces")
    p.conn().commit()
    state["n"] = 0; _scenario(s)
    state["n"] = 0; _scenario(p)
    assert s.spent_today_minor("ag-mp") == p.spent_today_minor("ag-mp") == 0
    # kolonlu append zincir-paritesini korur; permission_decision(0.0) → 0 türetilir
    try:
        se = s.export_events("ag-mp")
        pe = p.export_events("ag-mp")
        assert [e["amount_minor"] for e in se] == [e["amount_minor"] for e in pe] \
            == [0, 50_000, 50_000]
        # bundle-paritesi: kolon bundle'a sızmaz
        bs = produce_bundle(s, agent_id="ag-mp")
        bp = produce_bundle(p, agent_id="ag-mp")
        assert bs["merkle_root"] == bp["merkle_root"]
    finally:
        s.close()
        p.close()


def test_173_middleware_integer_quota_path(tmp_path):
    """Middleware tam-sayı kota-yolunda: pugio0 HMAC akışı 200→402 (kolondan
    sayaç), makbuz amount_minor'u tam-sayı yazılır, zincir SAĞLAM kalır."""
    import asyncio
    import hashlib
    import hmac

    from sester.middleware import SesterMeter

    led = Ledger(tmp_path / "mw.sqlite3", secret="s-mw")
    meter = SesterMeter(None, led, price=0.05, daily_quota=0.06, secret="s-mw")
    W = "0xmw-agent-0001"

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})

    async def call(nonce):
        meter.app = app
        out = []
        amount_s = "0.05"
        mac = hmac.new(b"s-mw", f"{W}|{nonce}|{amount_s}|/weather".encode(),
                       hashlib.sha256).hexdigest()
        payment = f"{meter.VERSION} {W}:{nonce}:{amount_s}:{mac}"
        scope = {"type": "http", "path": "/weather",
                 "headers": [(b"x-payment", payment.encode())]}

        async def s2(m):
            out.append(m)

        await meter(scope, None, s2)
        return out[0]["status"]

    assert asyncio.run(call("n-a")) == 200              # 0.05 harcandı
    assert asyncio.run(call("n-b")) == 402              # 50k+50k > 60k — tam-sayı ret
    assert led.spent_today_minor(W) == 50_000           # kolon tam-sayı yazıldı
    assert led.verify_chain()
