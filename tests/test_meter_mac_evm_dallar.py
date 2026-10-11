"""sester.middleware.SesterMeter._mac + _parse_evm dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — StubLedger + demo-anahtar ile imza-uretimi
(GERCEK network / node YOK — eth_account yerel personal_sign).
"""
import hashlib
import hmac

import pytest
from eth_account import Account

from sester.middleware import PaymentErr, SesterMeter
from sester.schemes import sign_exact_sester

SK = "0x" + "d3" * 32
AGENT = Account.from_key(SK).address


class StubLedger:
    secret = b"test-secret"


@pytest.fixture
def meter():
    return SesterMeter(None, StubLedger(), price=0.05, daily_quota=1.0)


# == _mac ========================================================================================

class TestMac:
    def test_formula(self, meter):
        """ORTAM: hmac-sha256(secret, 'agent|nonce|amount|resource').hexdigest()."""
        assert meter._mac("a", "n", "0.05", "/w") == hmac.new(
            b"test-secret", b"a|n|0.05|/w", hashlib.sha256).hexdigest()

    def test_returns_64_char_hex(self, meter):
        out = meter._mac("a", "n", "0.05", "/w")
        assert len(out) == 64
        int(out, 16)

    def test_returns_str(self, meter):
        assert isinstance(meter._mac("a", "n", "0.05", "/w"), str)

    def test_lowercase_hex(self, meter):
        assert meter._mac("a", "n", "0.05", "/w") == \
            meter._mac("a", "n", "0.05", "/w").lower()

    @pytest.mark.parametrize("agent,nonce,amount,resource", [
        ("a", "n", "0.05", "/w"), ("görev-1", "n", "0,25", "/ü"),
        ("a", "", "0.05", "/w"), ("", "n", "0.05", "/w"),
        ("a", "n", "", "/w"), ("a", "n", "0.05", ""),
    ])
    def test_variants(self, meter, agent, nonce, amount, resource):
        expected = hmac.new(
            b"test-secret", f"{agent}|{nonce}|{amount}|{resource}".encode(),
            hashlib.sha256).hexdigest()
        assert meter._mac(agent, nonce, amount, resource) == expected

    def test_empty_all(self, meter):
        assert meter._mac("", "", "", "") == \
            hmac.new(b"test-secret", b"|||", hashlib.sha256).hexdigest()

    def test_different_secret_differs(self):
        """ORTAM: secret imzanin parçasi — baska-secret baska-imza."""
        m1 = SesterMeter(None, type("L", (), {"secret": b"one"})(),
                         price=0.05, daily_quota=1.0)
        m2 = SesterMeter(None, type("L", (), {"secret": b"two"})(),
                         price=0.05, daily_quota=1.0)
        assert m1._mac("a", "n", "0.05", "/w") != m2._mac("a", "n", "0.05", "/w")

    def test_deterministic(self, meter):
        assert meter._mac("a", "n", "0.05", "/w") == meter._mac("a", "n", "0.05", "/w")

    def test_arg_order_matters(self, meter):
        assert meter._mac("a", "n", "0.05", "/w") != meter._mac("/w", "a", "n", "0.05")

    @pytest.mark.parametrize("changed", ["agent", "nonce", "amount", "resource"])
    def test_each_field_changes_mac(self, meter, changed):
        base = meter._mac("a", "n", "0.05", "/w")
        vals = {"agent": "b", "nonce": "m", "amount": "0.06", "resource": "/x"}
        args = ["a", "n", "0.05", "/w"]
        args[["agent", "nonce", "amount", "resource"].index(changed)] = vals[changed]
        assert meter._mac(*args) != base

    def test_pipe_in_data_is_ambiguous(self, meter):
        """ORTAM-OGRENDI: '|' ayraç oldugu icin verideki '|' konumu belirsizdir
        — 'a|b','n' ile 'a','b|n' AYNI imzayi uretir (positional-split collision)."""
        a = meter._mac("a|b", "n", "0.05", "/w")
        b = meter._mac("a", "b|n", "0.05", "/w")
        assert a == b

    def test_unicode(self, meter):
        msg = "görev|n|0,05|/ü".encode()
        assert meter._mac("görev", "n", "0,05", "/ü") == \
            hmac.new(b"test-secret", msg, hashlib.sha256).hexdigest()

    def test_implements_envelope_contract(self, meter):
        """ORTAM: _parse_hmac ile ayni-formula — geri-uyum sözleşmesi."""
        mac = meter._mac("agent-1", "n1", "0.05", "/r")
        token = f"pugio0 agent-1:n1:0.05:{mac}"
        assert meter._parse_hmac(token, "/r")["agent"] == "agent-1"

    def test_long_fields(self, meter):
        agent = "a" * 200
        assert meter._mac(agent, "n", "0.05", "/w") == hmac.new(
            b"test-secret", f"{agent}|n|0.05|/w".encode(),
            hashlib.sha256).hexdigest()


# == _parse_evm ==================================================================================

class TestParseEvm:
    def _hdr(self, agent=AGENT, nonce="nonce-1", amount="0.05", resource="/weather"):
        return sign_exact_sester(SK, agent, nonce, amount, resource)

    def test_valid_returns_dict(self, meter):
        r = meter._parse_evm(self._hdr(), "/weather")
        assert isinstance(r, dict)

    def test_fields(self, meter):
        r = meter._parse_evm(self._hdr(), "/weather")
        assert r["agent"] == AGENT.lower()
        assert r["nonce"] == "nonce-1"
        assert r["amount"] == "0.05"

    def test_scheme_is_evm_constant(self, meter):
        """ORTAM: scheme = SesterMeter.EVM_SCHEME ('exact-sester')."""
        assert meter._parse_evm(self._hdr(), "/weather")["scheme"] == \
            SesterMeter.EVM_SCHEME

    @pytest.mark.parametrize("nonce", ["n1", "görev-n", "x" * 40, "😀"])
    def test_nonce_variants(self, meter, nonce):
        r = meter._parse_evm(self._hdr(nonce=nonce), "/weather")
        assert r["nonce"] == nonce

    @pytest.mark.parametrize("amount", ["0.05", "0.25", "1.00", "0.000001"])
    def test_amount_variants(self, meter, amount):
        r = meter._parse_evm(self._hdr(amount=amount), "/weather")
        assert r["amount"] == amount

    @pytest.mark.parametrize("resource", ["/weather", "/", "/yol/uzun", "/p?x=1"])
    def test_resource_variants(self, meter, resource):
        r = meter._parse_evm(self._hdr(resource=resource), resource)
        assert r["agent"] == AGENT.lower()

    def test_agent_is_checksum_lower(self, meter):
        """ORTAM: imzalayan-adres lowercase doner."""
        r = meter._parse_evm(self._hdr(), "/weather")
        assert r["agent"] == AGENT.lower()
        assert r["agent"] == r["agent"].lower()

    def test_wrong_resource_raises(self, meter):
        """ORTAM: resource imzanin parçasi — baska-resource RED."""
        with pytest.raises(PaymentErr) as ei:
            meter._parse_evm(self._hdr(), "/other")
        assert "EVM dozu reddedildi" in str(ei.value)

    @pytest.mark.parametrize("header,desc", [
        ("", "empty"),
        ("Sester-EVM garbage", "garbage"),
        ("x402 something", "wrong-prefix"),
        ("Sester-EVM", "no-token"),
    ])
    def test_malformed_raises(self, meter, header, desc):
        """ORTAM: PaymentError -> PaymentErr('EVM dozu reddedildi: ...')."""
        with pytest.raises(PaymentErr):
            meter._parse_evm(header, "/w")

    def test_bad_base64_raises(self, meter):
        import base64
        bad = "Sester-EVM " + base64.urlsafe_b64encode(b"{broken").decode().rstrip("=")
        with pytest.raises(PaymentErr) as ei:
            meter._parse_evm(bad, "/w")
        assert "base64/JSON" in str(ei.value)

    def test_tampered_signature_raises(self, meter):
        hdr = self._hdr()
        bad = hdr[:-4] + ("0" if hdr[-4] != "0" else "1") + hdr[-3:]
        with pytest.raises(PaymentErr):
            meter._parse_evm(bad, "/weather")

    def test_tampered_agent_raises(self, meter):
        """ORTAM: zarf icindeki agent-alani degistirilirse imza bozulur -> RED."""
        import base64
        import json
        hdr = self._hdr()
        prefix, tok = hdr.split(" ", 1)
        payload = json.loads(base64.urlsafe_b64decode(tok + "=" * (-len(tok) % 4)))
        payload["agent"] = "0x" + "99" * 20
        new_tok = base64.urlsafe_b64encode(
            json.dumps(payload).encode()).decode().rstrip("=")
        with pytest.raises(PaymentErr):
            meter._parse_evm(f"{prefix} {new_tok}", "/weather")

    def test_other_valid_signer_accepted(self, meter):
        """ORTAM: baska-gecerli-anahtar+agent CIFTI KABUL (imza gecerliyse)."""
        other_sk = "0x" + "ab" * 32
        other_agent = Account.from_key(other_sk).address
        hdr = sign_exact_sester(other_sk, other_agent, "n", "0.05", "/weather")
        r = meter._parse_evm(hdr, "/weather")
        assert r["agent"] == other_agent.lower()

    def test_exception_type_is_payment_err(self, meter):
        """ORTAM: PaymentError -> PaymentErr dönüsümü (fail-closed 402, 500 DEGIL)."""
        with pytest.raises(PaymentErr):
            meter._parse_evm("Sester-EVM !!", "/w")

    def test_uses_verify_exact_sester(self, meter):
        """ORTAM: schemes.verify_exact_sester ile çözümleme (delayed-import)."""
        import inspect
        src = inspect.getsource(SesterMeter._parse_evm)
        assert "verify_exact_sester" in src
        assert "PaymentError" in src

    def test_amount_is_string(self, meter):
        """ORTAM: amount string olarak doner (minor-int DEGIL — EVM decimal)."""
        r = meter._parse_evm(self._hdr(), "/weather")
        assert isinstance(r["amount"], str)

    def test_nonce_is_string(self, meter):
        assert isinstance(meter._parse_evm(self._hdr(), "/weather")["nonce"], str)
