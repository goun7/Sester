"""sester.adapters._a2a (A2A x402 Extension) dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — install_adapters ile kaydedilen parser STUB register
ile yakalanir; GERCEK network / agent / server YOK.
"""
import base64
import hashlib
import json

import pytest

from sester.adapters import ChargeIntent, install_adapters
from sester.middleware import PaymentErr


def b64u(obj):
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


@pytest.fixture
def a2a():
    """ORTAM: _a2a install_adapters icinde tanimli closure — register ile yakala."""
    schemes = {}
    install_adapters(schemes.__setitem__, price_minor=5000,
                     on_intent=lambda i: None)
    return schemes["x402-payment"]


@pytest.fixture
def a2a_captured():
    """on_intent callback'i ile ChargeIntent yakala."""
    captured = []
    schemes = {}
    install_adapters(schemes.__setitem__, price_minor=5000,
                     on_intent=captured.append)
    return schemes["x402-payment"], captured


def valid_env(**over):
    env = {"buyer": "did:buyer:1", "seller": "did:seller:1", "intentId": "int-1",
           "paymentRequirements": [{"resource": "/w", "amount": 5000,
                                    "currency": "USDC"}]}
    env.update(over)
    return env


# == gecerli-zarf ================================================================================

class TestValid:
    def test_returns_dict(self, a2a):
        assert isinstance(a2a("x402-payment " + b64u(valid_env()), "/w"), dict)

    def test_fields(self, a2a):
        r = a2a("x402-payment " + b64u(valid_env()), "/w")
        assert r["agent"] == "did:buyer:1"
        assert r["nonce"] == "int-1"
        assert r["amount_minor"] == 5000
        assert r["scheme"] == "a2a-x402"

    def test_intent_is_charge_intent(self, a2a):
        assert isinstance(a2a("x402-payment " + b64u(valid_env()), "/w")["intent"],
                          ChargeIntent)

    def test_intent_fields(self, a2a):
        it = a2a("x402-payment " + b64u(valid_env()), "/w")["intent"]
        assert it.protocol == "A2A-x402"
        assert it.nonce == "int-1"
        assert it.agent == "did:buyer:1"
        assert it.principal == "did:seller:1"
        assert it.currency == "USDC"
        assert it.resource == "/w"

    def test_registered_under_prefix(self):
        """ORTAM: register_scheme('x402-payment', _a2a) — on-ek bu isimle."""
        schemes = {}
        install_adapters(schemes.__setitem__, price_minor=5000)
        assert "x402-payment" in schemes

    def test_on_intent_called(self, a2a_captured):
        a2a, captured = a2a_captured
        a2a("x402-payment " + b64u(valid_env()), "/w")
        assert len(captured) == 1
        assert isinstance(captured[0], ChargeIntent)

    def test_on_intent_none_ok(self):
        """ORTAM: on_intent None ise callback-atlamasi."""
        schemes = {}
        install_adapters(schemes.__setitem__, price_minor=5000, on_intent=None)
        r = schemes["x402-payment"]("x402-payment " + b64u(valid_env()), "/w")
        assert r["agent"] == "did:buyer:1"

    def test_whitespace_stripped(self, a2a):
        r = a2a("  x402-payment " + b64u(valid_env()) + "  ", "/w")
        assert r["agent"] == "did:buyer:1"


# == nonce-önceliği ==============================================================================

class TestNoncePrecedence:
    def test_intent_id_wins(self, a2a):
        env = valid_env(intentId="II", taskId="TT")
        assert a2a("x402-payment " + b64u(env), "/w")["nonce"] == "II"

    def test_task_id_when_no_intent_id(self, a2a):
        env = {**valid_env(), "intentId": None, "taskId": "TT"}
        env.pop("intentId")
        assert a2a("x402-payment " + b64u(env), "/w")["nonce"] == "TT"

    def test_deterministic_fallback(self, a2a):
        """ORTAM: sha256(f'{buyer}:{first.resource}')[:32] fallback
        (buyer YOKSA '' — 'from' DEGIL)."""
        env = {"buyer": "bob", "to": "sel",
               "paymentRequirements": [{"resource": "/d", "amount": 7}]}
        expected = hashlib.sha256(b"bob:/d").hexdigest()[:32]
        assert a2a("x402-payment " + b64u(env), "/d")["nonce"] == expected

    def test_fallback_empty_buyer_when_missing(self, a2a):
        """ORTAM: buyer YOKSA fallback '' ile hesaplanir ('from' KULLANILMAZ)."""
        env = {"from": "bob",
               "paymentRequirements": [{"resource": "/d", "amount": 7}]}
        expected = hashlib.sha256(b":/d").hexdigest()[:32]
        assert a2a("x402-payment " + b64u(env), "/d")["nonce"] == expected

    def test_fallback_missing_resource_in_req(self, a2a):
        """ORTAM: first.resource YOKSA '' — sha256('buyer:')[:32]."""
        env = {"buyer": "bob", "intentId": None,
               "paymentRequirements": [{"amount": 7}]}
        expected = hashlib.sha256(b"bob:").hexdigest()[:32]
        assert a2a("x402-payment " + b64u(env), "/d")["nonce"] == expected

    def test_fallback_deterministic_repeat(self, a2a):
        env = {"from": "bob", "paymentRequirements": [{"resource": "/d", "amount": 7}]}
        hdr = "x402-payment " + b64u(env)
        assert a2a(hdr, "/d")["nonce"] == a2a(hdr, "/d")["nonce"]

    def test_fallback_uses_buyer_not_from(self, a2a):
        """ORTAM: fallback sha256(f'{buyer}:{resource}') — 'from' DIKKATE ALINMAZ."""
        env = {"buyer": "zzz", "from": "bob",
               "paymentRequirements": [{"resource": "/d", "amount": 7}]}
        expected = hashlib.sha256(b"zzz:/d").hexdigest()[:32]
        assert a2a("x402-payment " + b64u(env), "/d")["nonce"] == expected

    def test_fallback_ignores_from_entirely(self, a2a):
        """ORTAM-OGRENDI: 'from' fallback'te HIC kullanilmaz — buyer=''/from='bob'
        ayni-imza (buyer-bos-kisim ayni)."""
        env = {"from": "bob",
               "paymentRequirements": [{"resource": "/d", "amount": 7}]}
        expected = hashlib.sha256(b":/d").hexdigest()[:32]
        assert a2a("x402-payment " + b64u(env), "/d")["nonce"] == expected

    def test_nonce_is_str(self, a2a):
        assert isinstance(a2a("x402-payment " + b64u(valid_env()), "/w")["nonce"], str)


# == payment-requirements ========================================================================

class TestRequirements:
    def test_accepts_key_also_supported(self, a2a):
        """ORTAM: paymentRequirements YOKSA accepts kullanilir."""
        env = {"buyer": "b", "intentId": "i",
               "accepts": [{"resource": "/a", "amount": 3, "currency": "EUR"}]}
        r = a2a("x402-payment " + b64u(env), "/a")
        assert r["amount_minor"] == 3
        assert r["intent"].currency == "EUR"

    def test_first_requirement_wins(self, a2a):
        env = {"buyer": "b", "intentId": "i",
               "accepts": [{"amount": 9}, {"amount": 8}]}
        assert a2a("x402-payment " + b64u(env), "/a")["amount_minor"] == 9

    def test_missing_requirements_raises(self, a2a):
        with pytest.raises(PaymentErr) as ei:
            a2a("x402-payment " + b64u({"buyer": "x"}), "/w")
        assert "paymentRequirements eksik" in str(ei.value)

    def test_empty_requirements_raises(self, a2a):
        with pytest.raises(PaymentErr):
            a2a("x402-payment " + b64u({"paymentRequirements": []}), "/w")

    def test_default_amount_0(self, a2a):
        """ORTAM: first.get('amount', 0) — YOKSA 0."""
        env = {"buyer": "b", "intentId": "i",
               "paymentRequirements": [{"resource": "/x", "currency": "USDC"}]}
        assert a2a("x402-payment " + b64u(env), "/x")["amount_minor"] == 0

    def test_default_currency_usdc(self, a2a):
        env = {"buyer": "b", "intentId": "i",
               "paymentRequirements": [{"resource": "/x", "amount": 1}]}
        assert a2a("x402-payment " + b64u(env), "/x")["intent"].currency == "USDC"

    def test_resource_falls_back_to_arg(self, a2a):
        """ORTAM: first.resource YOKSA resource-argümani kullanilir."""
        env = {"buyer": "b", "intentId": "i", "paymentRequirements": [{"amount": 1}]}
        assert a2a("x402-payment " + b64u(env), "/fallback")["intent"].resource == "/fallback"

    def test_amount_is_int(self, a2a):
        assert isinstance(a2a("x402-payment " + b64u(valid_env()), "/w")["amount_minor"],
                          int)


# == agent/principal =============================================================================

class TestAgentPrincipal:
    def test_no_buyer_empty_agent(self, a2a):
        """ORTAM: buyer/from YOKSA '' (fail-loud DEGIL — bos-etiket)."""
        env = {"paymentRequirements": [{"resource": "/y", "amount": 1}]}
        assert a2a("x402-payment " + b64u(env), "/y")["agent"] == ""

    def test_from_key_as_agent(self, a2a):
        """ORTAM: buyer YOKSA from kullanilir."""
        env = {"from": "from-buyer",
               "paymentRequirements": [{"resource": "/y", "amount": 1}]}
        assert a2a("x402-payment " + b64u(env), "/y")["agent"] == "from-buyer"

    def test_buyer_wins_over_from(self, a2a):
        env = {"buyer": "B", "from": "F",
               "paymentRequirements": [{"resource": "/y", "amount": 1}]}
        assert a2a("x402-payment " + b64u(env), "/y")["agent"] == "B"

    def test_seller_as_principal(self, a2a):
        env = {"buyer": "b", "seller": "S",
               "paymentRequirements": [{"resource": "/y", "amount": 1}]}
        assert a2a("x402-payment " + b64u(env), "/y")["intent"].principal == "S"

    def test_to_key_as_principal(self, a2a):
        env = {"buyer": "b", "to": "T",
               "paymentRequirements": [{"resource": "/y", "amount": 1}]}
        assert a2a("x402-payment " + b64u(env), "/y")["intent"].principal == "T"

    def test_no_seller_empty_principal(self, a2a):
        env = {"buyer": "b", "paymentRequirements": [{"resource": "/y", "amount": 1}]}
        assert a2a("x402-payment " + b64u(env), "/y")["intent"].principal == ""

    def test_agent_is_str(self, a2a):
        assert isinstance(a2a("x402-payment " + b64u(valid_env()), "/w")["agent"], str)


# == hata-yollari ================================================================================

class TestErrors:
    @pytest.mark.parametrize("header,desc", [
        ("", "empty"),
        ("other " + b64u(valid_env()), "wrong-prefix"),
        ("x402-paymentX " + b64u(valid_env()), "no-space"),
        ("x402-payment", "no-token"),
        ("x402-payment ", "empty-token"),
    ])
    def test_bad_prefix_raises(self, a2a, header, desc):
        """ORTAM: startswith('x402-payment ') DEGILSE AdapterError->PaymentErr."""
        with pytest.raises(PaymentErr) as ei:
            a2a(header, "/w")
        assert "A2A x402 reddedildi" in str(ei.value)

    @pytest.mark.parametrize("tok", ["!!!!", "a", "==="])
    def test_bad_base64_raises(self, a2a, tok):
        with pytest.raises(PaymentErr) as ei:
            a2a("x402-payment " + tok, "/w")
        assert "base64/JSON bozuk" in str(ei.value)

    def test_bad_json_raises(self, a2a):
        bad = base64.urlsafe_b64encode(b"{not json").decode().rstrip("=")
        with pytest.raises(PaymentErr):
            a2a("x402-payment " + bad, "/w")

    def test_json_array_raises(self, a2a):
        """ORTAM: [] -> payload.get dict-metodu YOK -> AttributeError YAYILIR."""
        bad = base64.urlsafe_b64encode(b"[]").decode().rstrip("=")
        with pytest.raises(AttributeError):
            a2a("x402-payment " + bad, "/w")

    def test_adapter_error_wrapped_in_payment_err(self, a2a):
        """ORTAM: her AdapterError 'A2A x402 reddedildi:' ile sarilir."""
        with pytest.raises(PaymentErr) as ei:
            a2a("x402-payment " + b64u({"buyer": "x"}), "/w")
        assert str(ei.value).startswith("A2A x402 reddedildi:")

    def test_protocol_constant(self, a2a):
        """ORTAM: ChargeIntent.protocol = 'A2A-x402' (sabit kablo-alani)."""
        assert a2a("x402-payment " + b64u(valid_env()), "/w")["intent"].protocol == \
            "A2A-x402"
