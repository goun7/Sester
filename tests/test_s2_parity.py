"""S2 parite-kilidi (IS_PLANI §7 senaryo-2): aynı işlem pugio0 + AP2 + ACP
yollarından geçer → aynı ChargeReceipt çekirdeği, tek ortak-sayaç.

scripts/s2_protocol_parity.py'nin suite-içi karşılığı (deterministik,
tmp-ledger, CI-uyumlu)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac as hmac_mod
import json
import time

import pytest

from pugio.adapters import install_adapters
from pugio.ledger import Ledger
from pugio.middleware import MINOR, PugioMeter

SECRET = "s2-lock"
PRICE = 0.05
WALLET = "0xs200000000000000000000000000000000000000"
RES = "/weather"


def _header(protocol: str, nonce: str) -> str:
    amount_s = f"{PRICE:.2f}"
    if protocol == "pugio0":
        mac = hmac_mod.new(SECRET.encode(),
                           f"{WALLET}|{nonce}|{amount_s}|{RES}".encode(),
                           hashlib.sha256).hexdigest()
        return f"pugio0 {WALLET}:{nonce}:{amount_s}:{mac}"
    if protocol == "ap2":
        obj = {"mandate_id": nonce, "agent": WALLET, "principal": "u",
               "signature": "b" * 64, "valid_from": time.time() - 10,
               "valid_to": time.time() + 600,
               "scope": {"resource_prefixes": [RES],
                         "per_request_max_minor": 100_000, "currency": "USDC"}}
    else:  # acp
        obj = {"session_id": nonce, "buyer": WALLET,
               "valid_to": time.time() + 600,
               "line_item": {"resource": RES,
                             "amount_minor": int(PRICE * MINOR),
                             "currency": "USDC"}}
    raw = base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    prefix = "AP2-Mandate" if protocol == "ap2" else "ACP-Session"
    return f"{prefix} {raw}"


def test_107_same_transaction_across_three_protocols_same_receipt_core(tmp_path):
    led = Ledger(tmp_path / "s2.sqlite3", secret=SECRET)
    meter = PugioMeter(None, led, price=PRICE, daily_quota=25.0, secret=SECRET)
    install_adapters(meter.register_scheme, price_minor=meter.price_minor)

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})

    meter.app = app

    async def call(payment):
        out = []
        scope = {"type": "http", "path": RES,
                 "headers": [(b"x-payment", payment.encode())]}

        async def s(m):
            out.append(m)

        await meter(scope, None, s)
        return out[0]["status"], {
            k.decode().lower(): v.decode() for k, v in out[0].get("headers", [])}

    flows = [("pugio0", "n-x402"), ("ap2", "man-s2"), ("acp", "sess-s2")]
    statuses, receipts = [], []
    for proto, nonce in flows:
        st, hdrs = asyncio.run(call(_header(proto, nonce)))
        statuses.append(st)
        receipts.append((hdrs.get("x-pugio-receipt"), hdrs.get("x-pugio-amount")))

    assert statuses == [200, 200, 200]
    # aynı çekirdek: aynı tutar-başlığı, farklı kanıt-hash (imza-nonce farklı)
    assert {amt for _, amt in receipts} == {f"{PRICE:.6f}"}
    assert len({rec for rec, _ in receipts}) == 3

    # çekirdek-parite: ledger'da üç charge_receipt, tek (ajan, host, tutar)
    rows = [r for r in led.recent_events(20) if r["event_type"] == "charge_receipt"]
    assert len(rows) == 3
    assert {(r["agent_id"], r["host"], round(r["amount"], 6)) for r in rows} \
        == {(WALLET, RES, PRICE)}

    # ortak-cüzdan tek-sayaç: 3 × fiyat
    assert abs(led.spent_today(WALLET) - 3 * PRICE) < 1e-9
    assert led.verify_chain()
