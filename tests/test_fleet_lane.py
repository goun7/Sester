"""F1 filo-rayı (dogfood) entegrasyon-testleri — planın 1. gün-adımı kod-karşılığı.

Kapsam: mutlu-yol (200 + receipt), replay-402, kota-402, politika-red
(bilinmeyen-host), zincir-bütünlüğü. App'i env-izole DB ile import eder;
istekler ASGI-düzeyinde koşar (port-dinlemeden).
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "examples"))

import fleet_lane.app as fleet  # noqa: E402

from sester.ledger import Ledger  # noqa: E402


def _mac_header(agent: str, nonce: str, amount: str = "0.05",
                resource: str = "/telemetry") -> str:
    import hashlib
    import hmac as hmac_mod
    msg = f"{agent}|{nonce}|{amount}|{resource}".encode()
    mac = hmac_mod.new(fleet.SECRET.encode(), msg, hashlib.sha256).hexdigest()
    return f"{fleet.app.VERSION} {agent}:{nonce}:{amount}:{mac}"


async def _call(m, path="/telemetry", headers=None, method=b"GET"):
    scope = {"type": "http", "method": method, "path": path,
             "headers": headers or []}
    req_body = b""

    async def receive():
        return {"type": "http.request", "body": req_body, "more_body": False}

    out = {"status": None, "body": b"", "headers": {}}

    async def send(msg):
        if msg["type"] == "http.response.start":
            out["status"] = msg["status"]
            for k, v in msg.get("headers", []):
                out["headers"][k.decode().lower()] = v.decode()
        elif msg["type"] == "http.response.body":
            out["body"] += msg.get("body", b"")

    await m(scope, receive, send)
    return out


@pytest.fixture()
def m(tmp_path, monkeypatch):
    """Env-izole filo-rayı: tmp-DB, tmp-politika (çalışma-saati-uyumu testte sabit)."""
    # Politikanın hour_between penceresi (07:00–23:00) gerçek-zamana bağlıdır;
    # test gece yarısı koşunca sessizce RED düşmesin diye sabit bir
    # iş-saatleri anı enjekte ediyoruz (FleetPolicyMeter(now=...)).
    import datetime as _dt
    led = Ledger(tmp_path / "fleet.sqlite3", secret=fleet.SECRET)
    meter = fleet.FleetPolicyMeter(
        fleet.inner_router, led,
        price=fleet.PRICE, daily_quota=fleet.DAILY_QUOTA,
        secret=fleet.SECRET, pay_to="f1:treasury",
        now=_dt.datetime(2026, 9, 19, 12, 0),
    )
    yield meter, led
    led.close()


def test_fleet_paid_request_happy_path(m):
    meter, led = m
    h = _mac_header("f1-n1", f"n{time.time()}")
    rec = asyncio.run(_call(
        meter, headers=[(b"x-payment", h.encode()),
                        (b"x-sester-agent", b"f1-n1")]))
    assert rec["status"] == 200
    assert "x-sester-receipt" in rec["headers"]
    body = json.loads(rec["body"])
    assert body["car"] == "f1-63"


def test_fleet_replay_rejected(m):
    meter, led = m
    h = _mac_header("f1-n1", "replay-nonce")
    r1 = asyncio.run(_call(meter, headers=[(b"x-payment", h.encode())]))
    r2 = asyncio.run(_call(meter, headers=[(b"x-payment", h.encode())]))
    assert r1["status"] == 200
    assert r2["status"] == 402


def test_fleet_quota_exhausts(m):
    meter, led = m
    from sester.ledger import MINOR
    meter.quota_minor = int(round(0.22 * MINOR))  # 4×0.05=0.20 içinde, 5. aşar
    statuses = []
    for i in range(5):
        h = _mac_header("f1-q", f"q{i}")
        r = asyncio.run(_call(meter, headers=[(b"x-payment", h.encode())]))
        statuses.append(r["status"])
    assert statuses[:4] == [200, 200, 200, 200]
    assert statuses[4] == 402  # kota-aşımı
    assert b"quota" in r["body"]


def test_fleet_unknown_host_denied(m):
    meter, led = m
    h = _mac_header("f1-n1", "host-nonce", resource="/secret")
    r = asyncio.run(_call(
        meter, path="/secret", headers=[(b"x-payment", h.encode())]))
    assert r["status"] == 402
    assert b"policy_denied" in r["body"] or "policy" in r["body"].decode()


def test_fleet_chain_intact_after_traffic(m):
    meter, led = m
    for i in range(3):
        h = _mac_header("f1-n2", f"c{i}")
        asyncio.run(_call(meter, headers=[(b"x-payment", h.encode())]))
    assert led.verify_chain() is True


def test_fleet_policy_gate_uses_injected_now(m):
    """Regresyon (2026-09-19): politika gate'i GERÇEK-ZAMANA bağımlıydı —
    hour_between [07:00,23:00] penceresi yüzünden test takımı gece yarısı
    sessizce RED düşürüyordu (iş-saatleri-yeşil / gece-kırmızı). Artık 'now'
    enjekte ediliyor; bu test iki yönü de kilitler."""
    import datetime as _dt
    meter, led = m
    # pencere DIŞI (23:30) → allow kuralı eşleşmez → RED
    meter._now = _dt.datetime(2026, 9, 19, 23, 30)
    h_night = _mac_header("f1-tw", "tw-night")
    r_night = asyncio.run(_call(meter, headers=[(b"x-payment", h_night.encode())]))
    assert r_night["status"] == 402
    # pencere İÇİ (12:00) → GREEN (fixture default'u ile aynı)
    meter._now = _dt.datetime(2026, 9, 19, 12, 0)
    h_day = _mac_header("f1-tw2", "tw-day")
    r_day = asyncio.run(_call(meter, headers=[(b"x-payment", h_day.encode())]))
    assert r_day["status"] == 200
