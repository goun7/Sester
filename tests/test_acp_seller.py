"""SESTER ACP satıcı-tarafı testleri — issue_acp_session + imza-politikası (v0.3.1).

Kapsam: üretici→alıcı çemberi (imzalı/imzasız), gövde-bağı (line_item-kazıma +
geçerli-imza → ret), require_signature üretim-bayrağı (middleware-dahil),
pencere/TTL, demo-üretim-endpoint'i (dogfood).
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
    AcpSession,
    install_adapters,
    issue_acp_session,
    verify_acp_session,
)
from sester.ledger import Ledger
from sester.middleware import SesterMeter

WALLET = "0xacs000000000000000000000000000000000000"
SELLER = b"acp-seller-secret"


def test_146_issue_and_verify_unsigned_roundtrip():
    h = issue_acp_session(session_id="s-1", buyer=WALLET, resource="/weather",
                          amount_minor=50_000)
    intent = verify_acp_session(h, "/weather")
    assert intent.agent == WALLET and intent.nonce == "s-1"
    assert intent.protocol == "acp" and intent.amount_minor == 50_000


def test_147_issue_and_verify_signed_roundtrip():
    h = issue_acp_session(session_id="s-2", buyer=WALLET, resource="/weather",
                          amount_minor=50_000, key=SELLER, kid="seller-1")
    intent = verify_acp_session(h, "/weather",
                                resolve_key=lambda kid, alg: SELLER)
    assert intent.nonce == "s-2"
    # parse→verify ayrıntısı: imza alanı dışındaki her alan mühürlü
    s = AcpSession.parse(h)
    assert s.signature


def test_148_scraped_line_item_with_valid_signature_rejected():
    """Kazıma: imza A-tutarına ait; gövde B-tutarı — gövde-bağı ret eder."""
    h_a = issue_acp_session(session_id="s-3", buyer=WALLET, resource="/weather",
                            amount_minor=50_000, key=SELLER, kid="seller-1")
    obj = json.loads(base64.urlsafe_b64decode(
        h_a.split(" ", 1)[1] + "=" * (-len(h_a.split(" ", 1)[1]) % 4)))
    sig = obj["signature"]
    evil = {k: v for k, v in obj.items() if k != "signature"}
    evil["line_item"]["amount_minor"] = 1  # kazı: 0.000001'ye düşür
    evil["signature"] = sig  # A'nın geçerli imzası
    raw = base64.urlsafe_b64encode(json.dumps(evil, sort_keys=True).encode()
                                   ).decode().rstrip("=")
    with pytest.raises(AdapterError, match="uyuşmuyor"):
        verify_acp_session(f"ACP-Session {raw}", "/weather",
                           resolve_key=lambda kid, alg: SELLER)


def test_149_wrong_seller_key_rejected():
    h = issue_acp_session(session_id="s-4", buyer=WALLET, resource="/weather",
                          amount_minor=50_000, key=SELLER)
    with pytest.raises(AdapterError, match="uyuşmuyor"):
        verify_acp_session(h, "/weather",
                           resolve_key=lambda kid, alg: b"attacker")


def test_150_ttl_window_enforced():
    h = issue_acp_session(session_id="s-5", buyer=WALLET, resource="/weather",
                          amount_minor=50_000, ttl_seconds=60, valid_from=time.time() - 120)
    with pytest.raises(AdapterError, match="süresi doldu"):
        verify_acp_session(h, "/weather")


def test_151_require_signature_flag_rejects_unsigned():
    h = issue_acp_session(session_id="s-6", buyer=WALLET, resource="/weather",
                          amount_minor=50_000)  # imzasız
    with pytest.raises(SignatureRequiredError):
        verify_acp_session(h, "/weather", require_signature=True)
    # imzalı zarf aynı bayrakla geçer
    h2 = issue_acp_session(session_id="s-7", buyer=WALLET, resource="/weather",
                           amount_minor=50_000, key=SELLER)
    intent = verify_acp_session(h2, "/weather",
                                resolve_key=lambda kid, alg: SELLER,
                                require_signature=True)
    assert intent.nonce == "s-7"


def test_152_middleware_require_acp_signature_end_to_end(tmp_path):
    led = Ledger(tmp_path / "acs.sqlite3", secret="acs")
    meter = SesterMeter(None, led, price=0.05, daily_quota=25.0, secret="acs")
    install_adapters(meter.register_scheme, price_minor=meter.price_minor,
                     key_resolver=lambda kid, alg: SELLER,
                     require_acp_signature=True)

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

    # imzasız (eski-usül) → production-bayrağıyla 402
    unsigned = issue_acp_session(session_id="s-8", buyer=WALLET,
                                 resource="/weather", amount_minor=50_000)
    assert asyncio.run(call(unsigned)) == 402
    # satıcı-ucundan imzalı → 200
    signed = issue_acp_session(session_id="s-9", buyer=WALLET,
                               resource="/weather", amount_minor=50_000,
                               key=SELLER, kid="seller-1")
    assert asyncio.run(call(signed)) == 200
