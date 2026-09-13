"""SESTER schemes testleri — EIP-191 imzalı ajan-kimliği + EIP-3009 doz-şekli."""

from __future__ import annotations

import base64
import json

import pytest
from eth_account import Account

from sester.middleware import SesterMeter
from sester.schemes import (EIP712_AUTH_TYPES, ExactSesterV2, PaymentError,
                            sign_exact_sester, verify_exact_sester)

SK1 = "0x" + "11" * 32
SK2 = "0x" + "22" * 32
ADDR1 = Account.from_key(SK1).address.lower()


def header_for(sk=SK1, agent=None, nonce="n1", amount="0.05", resource="/weather"):
    return sign_exact_sester(sk, agent or Account.from_key(sk).address.lower(),
                            nonce, amount, resource)


# ---------- exact-sester ----------

def test_36_sign_verify_roundtrip():
    h = header_for()
    info = verify_exact_sester(h, "/weather")
    assert info["agent"] == ADDR1
    assert info["address"].lower() == ADDR1
    assert info["nonce"] == "n1"


def test_37_tampered_amount_rejected():
    h = header_for(nonce="tamper1")
    # gerçek zarfı çöz, tutarı değiştir, imzayı koru → doğrulama patlamalı
    raw = h[len("Sester-EVM "):]
    env = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    env["amount"] = "0.01"
    h2 = "Sester-EVM " + base64.urlsafe_b64encode(json.dumps(env).encode()).decode().rstrip("=")
    with pytest.raises(PaymentError):
        verify_exact_sester(h2, "/weather")


def test_38_wrong_agent_field_rejected():
    # üretici-tarafı (v0.4): agent-alanı imzalayan-adrese uymuyorsa zarf ÜRETİLMEZ
    with pytest.raises(PaymentError, match="uyuşmuyor"):
        header_for(sk=SK1, agent=Account.from_key(SK2).address.lower())
    # alıcı-tarafı kanıt: geçerli zarfın agent-alanı kazınırsa doğrulama reddeder
    h = header_for(sk=SK1)
    raw = h[len("Sester-EVM "):]
    env = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    env["agent"] = Account.from_key(SK2).address.lower()
    h2 = "Sester-EVM " + base64.urlsafe_b64encode(json.dumps(env).encode()).decode().rstrip("=")
    with pytest.raises(PaymentError, match="uyuşmuyor"):
        verify_exact_sester(h2, "/weather")


def test_39_cross_key_signature_rejected():
    # imza SK2'den, agent ADDR1: üretici-anında patlar (v0.4)
    with pytest.raises(PaymentError):
        header_for(sk=SK2, agent=ADDR1)
    # alıcı-tarafı kanıt: SK2'nin geçerli zarfının agent'ı ADDR1'e kazınır
    h = header_for(sk=SK2)
    raw = h[len("Sester-EVM "):]
    env = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    env["agent"] = ADDR1
    h2 = "Sester-EVM " + base64.urlsafe_b64encode(json.dumps(env).encode()).decode().rstrip("=")
    with pytest.raises(PaymentError):
        verify_exact_sester(h2, "/weather")


def test_40_wrong_resource_rejected():
    h = header_for(nonce="res1")
    with pytest.raises(PaymentError):
        verify_exact_sester(h, "/other")


def test_41_malformed_envelopes_rejected():
    with pytest.raises(PaymentError):
        verify_exact_sester("pugio0 xyz", "/weather")           # şema-önekli değil
    with pytest.raises(PaymentError):
        verify_exact_sester("Sester-EVM !!!not-base64!!!", "/weather")
    raw = base64.urlsafe_b64encode(json.dumps({"scheme": "baska"}).encode()).decode()
    with pytest.raises(PaymentError):
        verify_exact_sester("Sester-EVM " + raw, "/weather")


def test_42_evm_payment_passes_middleware_with_wallet_agent():
    led = _Ledger()
    m = SesterMeter(_dummy_app(), led, price=0.05, daily_quota=25.0)
    from tests.test_ledger import call

    h = header_for(nonce="mw1")
    status, hdrs, _ = call(m, "/weather", {"X-Payment": h})
    assert status == 200
    assert "x-sester-receipt" in hdrs
    ev = led.recent_events(5)[0]
    assert ev["agent_id"] == ADDR1      # ajan-kimliği = cüzdan-adresi
    assert ev["event_type"] == "charge_receipt"


def test_43_evm_replay_denied():
    led = _Ledger()
    m = SesterMeter(_dummy_app(), led, price=0.05, daily_quota=25.0)
    from tests.test_ledger import call

    h = header_for(nonce="mw2")
    s1, _, _ = call(m, "/weather", {"X-Payment": h})
    s2, _, body = call(m, "/weather", {"X-Payment": h})
    assert s1 == 200 and s2 == 402
    assert json.loads(body)["error"] == "replay_detected"


# ---------- EIP-3009 doz-şekli ----------

def test_44_amount_encoding_minor_units():
    assert ExactSesterV2.encode_amount(0.05) == "50000"
    assert ExactSesterV2.encode_amount(1.0) == "1000000"


def test_45_exact_envelope_fields_validated():
    good = ExactSesterV2.client_header(from_addr=ADDR1, to_addr="0x" + "33" * 20,
                                      amount_usd=0.05, private_key=SK1)
    env = ExactSesterV2.parse_payment_header(good)
    assert env["scheme"] == "exact" and env["network"].startswith("eip155:")
    assert env["payload"]["value"] == "50000"
    # EIP-712 yerel-dogrulama: from == recovered
    assert ExactSesterV2.verify_local(env).lower() == ADDR1


def test_46_exact_envelope_missing_field_rejected():
    good = ExactSesterV2.client_header(from_addr=ADDR1, to_addr="0x" + "33" * 20,
                                      amount_usd=0.05, private_key=SK1)
    env = json.loads(base64.urlsafe_b64decode(good + "=" * (-len(good) % 4)))
    del env["payload"]["validBefore"]
    bad = base64.urlsafe_b64encode(json.dumps(env).encode()).decode().rstrip("=")
    with pytest.raises(PaymentError, match="alan-eksik"):
        ExactSesterV2.parse_payment_header(bad)


def test_47_exact_envelope_expired_window_rejected():
    import time
    now = int(time.time())
    good = ExactSesterV2.client_header(from_addr=ADDR1, to_addr="0x" + "33" * 20,
                                      amount_usd=0.05, private_key=SK1,
                                      valid_after=now - 600, valid_before=now - 300)
    with pytest.raises(PaymentError, match="zaman"):
        ExactSesterV2.parse_payment_header(good, now_ts=now)


# ---------- yardımcılar ----------

class _Ledger:
    """Mini-ledger (geçici-dosyasız): schemes-testleri için yeterli yüzey."""

    def __init__(self):
        import tempfile, os
        from sester.ledger import Ledger

        fd, path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self._led = Ledger(path, secret="t")
        self.path = path

    def append(self, *a, **kw):
        return self._led.append(*a, **kw)

    @property
    def recent_events(self):
        return self._led.recent_events

    def spent_today(self, agent):
        return self._led.spent_today(agent)

    def spent_today_minor(self, agent):
        return self._led.spent_today_minor(agent)

    def claim_nonce(self, agent, nonce):
        return self._led.claim_nonce(agent, nonce)

    @property
    def conn(self):
        return self._led.conn


def _dummy_app():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": b'{"ok":true}'})
    return app
