"""SESTER v0.2 — facilitator hattı + integer-kota testleri."""

from __future__ import annotations

import asyncio
import json
import tempfile
import os

import pytest
from eth_account import Account

from sester.facilitator import Facilitator, FacilitatorError, FakeTransport, UrllibTransport
from sester.ledger import Ledger
from sester.middleware import MINOR, SesterMeter
from sester.schemes import ExactSesterV2

SK1 = "0x" + "44" * 32
ADDR1 = Account.from_key(SK1).address.lower()
TO = "0x" + "55" * 20


def _mk_ledger():
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    return Ledger(path, secret="v02")


def _meter(led, facilitator=None, quota=25.0, **kw):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    return SesterMeter(app, led, price=0.05, daily_quota=quota,
                      facilitator=facilitator, **kw)


def _call(meter, path, headers):
    messages: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        messages.append(m)

    scope = {"type": "http", "method": "GET", "path": path,
             "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    asyncio.run(meter(scope, receive, send))
    body = b"".join(m.get("body", b"") for m in messages[1:] if m["type"] == "http.response.body")
    try:
        parsed = json.loads(body) if body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        parsed = {}  # düz-metin gövde (örn. b"ok") — JSON yanıtı bekleyen testler 402'de
    return messages[0]["status"], parsed


def _exact_header(nonce_hex: str) -> str:
    return ExactSesterV2.client_header(from_addr=ADDR1, to_addr=TO, amount_usd=0.05,
                                      private_key=SK1, nonce_hex=nonce_hex)


def test_67_exact_verify_ok_settles_after_handler():
    led = _mk_ledger()
    fake = FakeTransport()
    m = _meter(led, Facilitator("https://f.example", fake))
    st, _ = _call(m, "/weather", {"X-Payment": _exact_header("ab" * 32)})
    assert st == 200
    urls = [u for u, _ in fake.calls]
    assert urls == ["https://f.example/verify", "https://f.example/settle"]
    kinds = [e["event_type"] for e in led.recent_events(10)]
    assert "settlement" in kinds
    settle = led.recent_events(10)[0]
    assert settle["event_type"] == "settlement"
    led.close()


def test_68_exact_rejected_by_facilitator_no_handler():
    led = _mk_ledger()
    fake = FakeTransport(verify_results=[{"ok": False, "error": "insufficient_funds"}])
    m = _meter(led, Facilitator("https://f.example", fake))
    st, body = _call(m, "/weather", {"X-Payment": _exact_header("ac" * 32)})
    assert st == 402 and body["error"] == "payment_rejected"
    # ret-bilgisi ledger'da, charge_receipt yok
    kinds = [e["event_type"] for e in led.recent_events(10)]
    assert "charge_receipt" not in kinds
    led.close()


def test_69_exact_facilitator_unknown_fail_closed():
    led = _mk_ledger()

    class DeadTransport:
        def post_json(self, url, payload):
            raise FacilitatorError("ağ yok")

    m = _meter(led, Facilitator("https://f.example", DeadTransport()))
    st, body = _call(m, "/weather", {"X-Payment": _exact_header("ad" * 32)})
    assert st == 402 and body["error"] == "facilitator_unknown"
    led.close()


def test_70_exact_without_facilitator_configured():
    led = _mk_ledger()
    m = _meter(led, facilitator=None)
    st, body = _call(m, "/weather", {"X-Payment": _exact_header("ae" * 32)})
    assert st == 402 and body["error"] == "exact_requires_facilitator"
    led.close()


def test_71_settle_failure_recorded_not_silent():
    led = _mk_ledger()
    fake = FakeTransport(settle_fail_first=1)
    m = _meter(led, Facilitator("https://f.example", fake))
    st, _ = _call(m, "/weather", {"X-Payment": _exact_header("af" * 32)})
    assert st == 200  # handler başarılı; ama settle düşüşü kayda geçmeli
    settles = [e for e in led.recent_events(10) if e["event_type"] == "settlement"]
    assert settles and settles[0]["amount"] == 0.0  # settle_failed olayı
    led.close()


def test_72_integer_quota_float_trap_closed():
    """0.10×3 float'ta 0.30000000000000004 üretir → eski float-kararı hatalı 402
    verebilirdi; minor-unit kararı 0.30 kotasını tam doldurmayı kabul eder."""
    led = _mk_ledger()
    m = _meter(led, quota=0.30, secret="v02")  # 3 × 0.10 tam sığmalı; pay() aynı secret'la imzalıyor
    import hashlib
    import hmac as _hmac

    SECRET = "v02"

    def pay(nonce, amount="0.10", path="/weather"):
        mac = _hmac.new(SECRET.encode(), f"f1|{nonce}|{amount}|{path}".encode(),
                        hashlib.sha256).hexdigest()
        return {"X-Payment": f"pugio0 f1:{nonce}:{amount}:{mac}"}

    codes = []
    for i in range(3):
        st, _ = _call(m, "/weather", pay(f"ft{i}"))
        codes.append(st)
    assert codes == [200, 200, 200]
    led.close()


def test_73_minor_unit_constant_matches_usdc():
    assert MINOR == 1_000_000
    assert int(round(0.05 * MINOR)) == 50_000
