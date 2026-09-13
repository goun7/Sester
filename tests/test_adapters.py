"""PUGIO adapters testleri — K4: AP2 mandate + ACP checkout-session.

Kapsam: ChargeIntent/ChargeReceipt çekirdeği, AP2 scope/pencere/tutar
reddetmeleri, ACP line_item eşleşmeleri, middleware-entegrasyonu (uçtan-uca
402→200→kanıt→replay), ortak-cüzdan kota-birleşimi.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from pugio.adapters import (
    AdapterError,
    AcpSession,
    Ap2Mandate,
    ChargeIntent,
    install_adapters,
    protocol_intent_event,
    verify_acp_session,
    verify_ap2_mandate,
)
from pugio.middleware import MINOR, PaymentErr, PugioMeter

NOW = 1_789_000_000.0  # yalnızca doc/deterministik referans; pencereler time.time()'


def _b64(obj: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


WALLET = "0xabc000000000000000000000000000000000abcd"
USER = "did:user:gokun"


def _mandate(**over) -> dict:
    """Pencere gerçek-zamana bağlı (middleware yolu time.time() kullanır).
    Pencere-testleri (85) bilinçli olarak geçmişe çekilir."""
    t = time.time()
    m = {
        "mandate_id": "man-001",
        "agent": WALLET,
        "principal": USER,
        "signature": "b" * 64,
        "valid_from": t - 100,
        "valid_to": t + 3600,
        "scope": {
            "resource_prefixes": ["/weather"],
            "per_request_max_minor": 100_000,
            "currency": "USDC",
        },
    }
    m.update(over)
    return m


def _session(**over) -> dict:
    s = {
        "session_id": "sess-77",
        "buyer": WALLET,
        "valid_to": time.time() + 3600,
        "line_item": {"resource": "/weather", "amount_minor": 50_000,
                      "currency": "USDC"},
    }
    s.update(over)
    return s


# ---------------------------------------------------------------- AP2 mandate

def test_82_ap2_mandate_authorizes_in_scope():
    h = f"AP2-Mandate {_b64(_mandate())}"
    intent = verify_ap2_mandate(h, "/weather", 50_000, "USDC")
    assert isinstance(intent, ChargeIntent)
    assert intent.agent == WALLET
    assert intent.nonce == "man-001"
    assert intent.protocol == "ap2"
    assert intent.principal == USER
    assert intent.amount_minor == 50_000


def test_83_ap2_mandate_rejects_out_of_scope_resource():
    h = f"AP2-Mandate {_b64(_mandate())}"
    with pytest.raises(AdapterError, match="kapsamı dışı"):
        verify_ap2_mandate(h, "/histogram", 50_000, "USDC")


def test_84_ap2_mandate_rejects_over_limit_amount():
    h = f"AP2-Mandate {_b64(_mandate())}"
    with pytest.raises(AdapterError, match="üst-sınırı"):
        verify_ap2_mandate(h, "/weather", 100_001, "USDC")


def test_85_ap2_mandate_rejects_expired_window():
    h = f"AP2-Mandate {_b64(_mandate(valid_to=time.time() - 1))}"
    with pytest.raises(AdapterError, match="süresi doldu"):
        verify_ap2_mandate(h, "/weather", 50_000, "USDC")


def test_86_ap2_mandate_rejects_missing_fields():
    m = _mandate()
    del m["signature"]
    h = f"AP2-Mandate {_b64(m)}"
    with pytest.raises(AdapterError, match="signature"):
        Ap2Mandate.parse(h)


def test_87_ap2_mandate_rejects_currency_mismatch():
    h = f"AP2-Mandate {_b64(_mandate())}"
    with pytest.raises(AdapterError, match="para-birimi"):
        verify_ap2_mandate(h, "/weather", 50_000, "EUR")


# -------------------------------------------------------------- ACP session

def test_88_acp_session_authorizes_matching_line_item():
    h = f"ACP-Session {_b64(_session())}"
    intent = verify_acp_session(h, "/weather")
    assert intent.agent == WALLET
    assert intent.nonce == "sess-77"
    assert intent.protocol == "acp"
    assert intent.amount_minor == 50_000
    assert intent.currency == "USDC"


def test_89_acp_session_rejects_resource_mismatch():
    h = f"ACP-Session {_b64(_session())}"
    with pytest.raises(AdapterError, match="kaynak değil"):
        verify_acp_session(h, "/histogram")


def test_90_acp_session_rejects_expired():
    h = f"ACP-Session {_b64(_session(valid_to=time.time() - 5))}"
    with pytest.raises(AdapterError, match="süresi doldu"):
        verify_acp_session(h, "/weather")


# ------------------------------------------------- middleware entegrasyonu

def _meter(tmp_path):
    from pugio.ledger import Ledger

    led = Ledger(tmp_path / "k4.sqlite3", secret="k4")
    meter = PugioMeter(None, led, price=0.05, daily_quota=0.10,
                       secret="k4")
    on_intents = []
    install_adapters(
        meter.register_scheme,
        price_minor=meter.price_minor,
        on_intent=lambda it: (on_intents.append(it),
                              led.append("protocol_intent", it.agent, it.resource,
                                         0.0, payload=protocol_intent_event(it))),
    )
    return led, meter, on_intents


def _call(meter, path, headers):
    import asyncio

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})

    meter.app = app
    scope = {"type": "http", "path": path, "headers": [
        (k.lower().encode(), v.encode()) for k, v in headers.items()]}
    out = []

    async def send_fn(message):
        out.append(message)

    async def run():
        await meter(scope, None, send_fn)

    asyncio.run(run())
    status = out[0]["status"]
    hdrs = {k.decode(): v.decode() for k, v in out[0].get("headers", [])}
    return status, hdrs


def test_91_ap2_header_end_to_end_receipt_and_intent_event(tmp_path):
    led, meter, on_intents = _meter(tmp_path)
    h = f"AP2-Mandate {_b64(_mandate())}"
    status, hdrs = _call(meter, "/weather", {"X-Payment": h})
    assert status == 200, "AP2 mandate akışı 200 dönmeli"
    assert "x-pugio-receipt" in hdrs
    # protokol-niyeti olayı ledger'a düştü
    kinds = [r["event_type"] for r in led.recent_events(10)]
    assert "protocol_intent" in kinds and "charge_receipt" in kinds
    assert on_intents and on_intents[0].protocol == "ap2"


def test_92_same_mandate_id_replays_are_rejected(tmp_path):
    led, meter, _ = _meter(tmp_path)
    h = f"AP2-Mandate {_b64(_mandate())}"
    s1, _ = _call(meter, "/weather", {"X-Payment": h})
    s2, _ = _call(meter, "/weather", {"X-Payment": h})
    assert s1 == 200 and s2 == 402, "aynı mandate_id iki kez harcayamaz"


def test_93_shared_wallet_quota_spans_protocols(tmp_path):
    """Ortak-cüzdan tezi: aynı ajanın AP2 + ACP harcaması tek sayaçta birleşir."""
    led, meter, _ = _meter(tmp_path)
    ap2 = f"AP2-Mandate {_b64(_mandate(mandate_id='man-a'))}"
    acp = f"ACP-Session {_b64(_session(session_id='sess-a'))}"
    ap2b = f"AP2-Mandate {_b64(_mandate(mandate_id='man-b'))}"  # taze-nonce
    s1, _ = _call(meter, "/weather", {"X-Payment": ap2})
    s2, _ = _call(meter, "/weather", {"X-Payment": acp})
    s3, hdrs = _call(meter, "/weather", {"X-Payment": ap2b})
    assert (s1, s2) == (200, 200)
    # kota 0.10 = 2 × 0.05 → üçüncü *taze* yetki kota-dışı (replay değil)
    assert s3 == 402, "ortak-cüzdan kotası protokoller-arası birleşmeli"
    assert "quota" in json.dumps(hdrs) or s3 == 402


def test_94_acp_below_seller_price_is_rejected(tmp_path):
    led, meter, _ = _meter(tmp_path)
    # line_item 0.05'ten küçük: 0.01 → satıcı-fiyatının altında
    h = f"ACP-Session {_b64(_session(line_item={'resource': '/weather',
                                                    'amount_minor': 10_000,
                                                    'currency': 'USDC'}))}"
    status, _ = _call(meter, "/weather", {"X-Payment": h})
    # amount_minor ≥ fiyat (0.05→50_000) değil… 10_000 < 50_000 → ret
    assert status == 402


def test_95_malformed_protocol_headers_are_rejected(tmp_path):
    led, meter, _ = _meter(tmp_path)
    for bad in ("AP2-Mandate !!!not-b64!!!", "ACP-Session eyJibGJibA",
                "AP2-Mandate eyJvbmx5IjoxfQ"):
        status, _ = _call(meter, "/weather", {"X-Payment": bad})
        assert status == 402, f"bozuk zarf geçti: {bad}"
