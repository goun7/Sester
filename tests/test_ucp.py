"""SESTER UCP testleri — web-monetization adaptörü (SPEC_FARK v3 → v0.4.0 kod).

Kapsam: üretici→alıcı çemberi (imzalı/imzasız), gövde-bağı (line_item-kazıma +
geçerli-imza → ret), merchant-bağı (manifest-teşhir sahteliği), pencere/TTL,
require_signature üretim-bayrağı (middleware-dahil), üç-protokol-tek-sayaç.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time

import pytest

from sester.adapters import (
    AdapterError,
    SignatureRequiredError,
    UcpCheckout,
    install_adapters,
    issue_ucp_checkout,
    verify_ucp_checkout,
)
from sester.ledger import Ledger
from sester.middleware import SesterMeter

WALLET = "0xucp00000000000000000000000000000000000"
MERCHANT = b"ucp-merchant-secret"
MERCHANT_ID = "sester-demo-merchant"


def _decode(header: str) -> dict:
    raw = header.split(" ", 1)[1]
    return json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))


def test_159_issue_and_verify_unsigned_roundtrip():
    h = issue_ucp_checkout(intent_id="u-1", buyer=WALLET, merchant=MERCHANT_ID,
                           resource="/weather", amount_minor=50_000)
    intent = verify_ucp_checkout(h, "/weather")
    assert intent.agent == WALLET and intent.nonce == "u-1"
    assert intent.protocol == "ucp" and intent.amount_minor == 50_000


def test_160_issue_and_verify_signed_roundtrip():
    h = issue_ucp_checkout(intent_id="u-2", buyer=WALLET, merchant=MERCHANT_ID,
                           resource="/weather", amount_minor=50_000,
                           key=MERCHANT, kid="merchant-1")
    intent = verify_ucp_checkout(h, "/weather",
                                 resolve_key=lambda kid, alg: MERCHANT)
    assert intent.nonce == "u-2"
    u = UcpCheckout.parse(h)
    assert u.signature and u.merchant == MERCHANT_ID


def test_161_scraped_line_item_with_valid_signature_rejected():
    """Kazıma: imza 50.000'e ait; gövde 1'e düşürülmüş — gövde-bağı ret eder."""
    h = issue_ucp_checkout(intent_id="u-3", buyer=WALLET, merchant=MERCHANT_ID,
                           resource="/weather", amount_minor=50_000,
                           key=MERCHANT, kid="merchant-1")
    obj = _decode(h)
    evil = {k: v for k, v in obj.items() if k != "signature"}
    evil["line_item"]["amount_minor"] = 1
    evil["signature"] = obj["signature"]
    raw = base64.urlsafe_b64encode(json.dumps(evil, sort_keys=True).encode()
                                   ).decode().rstrip("=")
    with pytest.raises(AdapterError, match="uyuşmuyor"):
        verify_ucp_checkout(f"UCP-Checkout {raw}", "/weather",
                            resolve_key=lambda kid, alg: MERCHANT)


def test_162_merchant_binding_rejects_spoofed_merchant():
    """Manifest-bağı: zarf başka satıcı adına mühürlüyse expected_merchant ret eder."""
    h = issue_ucp_checkout(intent_id="u-4", buyer=WALLET, merchant="evil-shop",
                           resource="/weather", amount_minor=50_000)
    with pytest.raises(AdapterError, match="merchant"):
        verify_ucp_checkout(h, "/weather", expected_merchant=MERCHANT_ID)
    # aynı zarf doğru merchant-bağıyla geçer
    intent = verify_ucp_checkout(h, "/weather", expected_merchant="evil-shop")
    assert intent.nonce == "u-4"


def test_163_ttl_window_enforced():
    h = issue_ucp_checkout(intent_id="u-5", buyer=WALLET, merchant=MERCHANT_ID,
                           resource="/weather", amount_minor=50_000,
                           ttl_seconds=60, valid_from=time.time() - 120)
    with pytest.raises(AdapterError, match="süresi doldu"):
        verify_ucp_checkout(h, "/weather")


def test_164_require_signature_flag_rejects_unsigned():
    h = issue_ucp_checkout(intent_id="u-6", buyer=WALLET, merchant=MERCHANT_ID,
                           resource="/weather", amount_minor=50_000)  # imzasız
    with pytest.raises(SignatureRequiredError):
        verify_ucp_checkout(h, "/weather", require_signature=True)
    # imzalı zarf aynı bayrakla geçer
    h2 = issue_ucp_checkout(intent_id="u-7", buyer=WALLET, merchant=MERCHANT_ID,
                            resource="/weather", amount_minor=50_000,
                            key=MERCHANT)
    intent = verify_ucp_checkout(h2, "/weather",
                                 resolve_key=lambda kid, alg: MERCHANT,
                                 require_signature=True)
    assert intent.nonce == "u-7"


def _meter_app(tmp_path, **kw):
    led = Ledger(tmp_path / "ucp.sqlite3", secret="ucp")
    meter = SesterMeter(None, led, price=0.05, daily_quota=25.0, secret="ucp")
    install_adapters(meter.register_scheme, price_minor=meter.price_minor,
                     key_resolver=lambda kid, alg: MERCHANT,
                     require_ucp_signature=True,
                     ucp_merchant=MERCHANT_ID, **kw)

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})

    async def call(payment):
        meter.app = app
        out = []
        scope = {"type": "http", "path": "/weather",
                 "headers": [(b"x-payment", payment.encode())]}

        async def s(m):
            out.append(m)

        await meter(scope, None, s)
        return out[0]["status"]

    return call


def test_165_middleware_require_ucp_signature_end_to_end(tmp_path):
    call = _meter_app(tmp_path)
    # imzasız → production-bayrağıyla 402
    unsigned = issue_ucp_checkout(intent_id="u-8", buyer=WALLET,
                                  merchant=MERCHANT_ID, resource="/weather",
                                  amount_minor=50_000)
    assert asyncio.run(call(unsigned)) == 402
    # satıcı-ucundan imzalı → 200
    signed = issue_ucp_checkout(intent_id="u-9", buyer=WALLET,
                                merchant=MERCHANT_ID, resource="/weather",
                                amount_minor=50_000, key=MERCHANT,
                                kid="merchant-1")
    assert asyncio.run(call(signed)) == 200
    # başka satıcı adına imzalı → merchant-bağıyla 402
    evil = issue_ucp_checkout(intent_id="u-10", buyer=WALLET,
                              merchant="evil-shop", resource="/weather",
                              amount_minor=50_000, key=MERCHANT,
                              kid="merchant-1")
    assert asyncio.run(call(evil)) == 402


def test_166_shared_counter_across_intents(tmp_path):
    """Tek wallet = tek günlük-kota — niyet-id/scheme fark etmeksizin (K0 çekirdek).
    Kota 0.11, fiyat 0.05: iki niyet geçer, üçüncüsü fail-closed ret olur."""
    led = Ledger(tmp_path / "share.sqlite3", secret="share")
    meter = SesterMeter(None, led, price=0.05, daily_quota=0.11, secret="share")
    install_adapters(meter.register_scheme, price_minor=meter.price_minor,
                     key_resolver=lambda kid, alg: MERCHANT,
                     ucp_merchant=MERCHANT_ID)

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})

    async def call(payment):
        meter.app = app
        out = []
        scope = {"type": "http", "path": "/weather",
                 "headers": [(b"x-payment", payment.encode())]}

        async def s(m):
            out.append(m)

        await meter(scope, None, s)
        return out[0]["status"]

    u1 = issue_ucp_checkout(intent_id="share-1", buyer=WALLET,
                            merchant=MERCHANT_ID, resource="/weather",
                            amount_minor=50_000)
    assert asyncio.run(call(u1)) == 200            # 0.05 harcandı
    u2 = issue_ucp_checkout(intent_id="share-2", buyer=WALLET,
                            merchant=MERCHANT_ID, resource="/weather",
                            amount_minor=50_000)
    assert asyncio.run(call(u2)) == 200            # 0.10 — hâlâ 0.11'in altında
    u3 = issue_ucp_checkout(intent_id="share-3", buyer=WALLET,
                            merchant=MERCHANT_ID, resource="/weather",
                            amount_minor=50_000)
    assert asyncio.run(call(u3)) == 402            # kota doldu — ortak sayaç
