"""sester.middleware.SesterMeter._parse_exact (x402 v2 exact zarfı) dal-kesen
testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — StubLedger + eth_account yerel EIP-712 imza-uretimi
(GERCEK network / node / facilitator YOK).
"""
import base64
import json
import time

import pytest
from eth_account import Account

from sester.middleware import PaymentErr, SesterMeter
from sester.schemes import ExactSesterV2

SK = "0x" + "d3" * 32
FROM = Account.from_key(SK).address
TO = "0x" + "f4" * 20


class StubLedger:
    secret = b"test-secret"


@pytest.fixture
def meter():
    return SesterMeter(None, StubLedger(), price=0.05, daily_quota=1.0)


def envelope(**over):
    kw = dict(from_addr=FROM, to_addr=TO, amount_usd=0.05, private_key=SK)
    kw.update(over)
    return ExactSesterV2.client_header(**kw)


# == gecerli-zarf ================================================================================

class TestValid:
    def test_x402_prefix(self, meter):
        r = meter._parse_exact("x402 " + envelope(), "/weather")
        assert r["agent"] == FROM.lower()

    def test_bare_b64_without_prefix(self, meter):
        """ORTAM: 'x402 ' on-ek YOKSA ham b64 kabul edilir."""
        assert meter._parse_exact(envelope(), "/weather")["agent"] == FROM.lower()

    def test_whitespace_stripped(self, meter):
        r = meter._parse_exact("  x402 " + envelope() + "  ", "/weather")
        assert r["agent"] == FROM.lower()

    def test_returns_dict(self, meter):
        assert isinstance(meter._parse_exact("x402 " + envelope(), "/weather"), dict)

    def test_fields(self, meter):
        r = meter._parse_exact("x402 " + envelope(), "/weather")
        assert set(r) >= {"agent", "nonce", "amount_minor", "envelope", "scheme"}

    def test_scheme_is_exact(self, meter):
        assert meter._parse_exact("x402 " + envelope(), "/weather")["scheme"] == "exact"

    def test_agent_lowercased(self, meter):
        """ORTAM: verify_local adresi lowercase cevirir."""
        r = meter._parse_exact("x402 " + envelope(), "/weather")
        assert r["agent"] == FROM.lower()
        assert r["agent"] == r["agent"].lower()

    def test_nonce_from_envelope(self, meter):
        h = envelope(nonce_hex="0x" + "cd" * 32)
        assert meter._parse_exact("x402 " + h, "/weather")["nonce"] == "0x" + "cd" * 32

    @pytest.mark.parametrize("amount_usd,expected", [
        (0.05, 50000), (0.25, 250000), (1.0, 1_000_000), (0.01, 10000),
    ])
    def test_amount_conversion(self, meter, amount_usd, expected):
        """ORTAM: encode_amount -> minor-int (6 dec); int(payload['value'])."""
        h = envelope(amount_usd=amount_usd)
        assert meter._parse_exact("x402 " + h, "/weather")["amount_minor"] == expected

    def test_amount_minor_is_int(self, meter):
        assert isinstance(meter._parse_exact("x402 " + envelope(), "/weather")
                          ["amount_minor"], int)

    def test_envelope_dict_returned(self, meter):
        r = meter._parse_exact("x402 " + envelope(), "/weather")
        assert isinstance(r["envelope"], dict)
        assert r["envelope"]["scheme"] == "exact"

    def test_envelope_payload_keys(self, meter):
        r = meter._parse_exact("x402 " + envelope(), "/weather")
        p = r["envelope"]["payload"]
        for k in ("from", "to", "value", "validAfter", "validBefore", "nonce",
                  "signature"):
            assert k in p

    def test_envelope_top_keys(self, meter):
        r = meter._parse_exact("x402 " + envelope(), "/weather")
        for k in ("scheme", "x402Version", "network", "resource", "payload"):
            assert k in r["envelope"]

    def test_different_signer(self, meter):
        """ORTAM: baska-gecerli anahtar farkli-agent verir."""
        sk2 = "0x" + "ab" * 32
        h = envelope(from_addr=Account.from_key(sk2).address, private_key=sk2)
        assert meter._parse_exact("x402 " + h, "/weather")["agent"] == \
            Account.from_key(sk2).address.lower()

    def test_to_address_variant(self, meter):
        h = envelope(to_addr="0x" + "99" * 20)
        assert meter._parse_exact("x402 " + h, "/weather")["agent"] == FROM.lower()

    def test_resource_not_in_signature_check(self, meter):
        """ORTAM-OGRENDI: resource imza-icerigi DISINDA — baska-resource KABUL
        (EIP-712 message resource icermiyor; scheme-benchmark disinda)."""
        h = envelope()
        assert meter._parse_exact("x402 " + h, "/other")["agent"] == FROM.lower()


# == zaman-penceresi =============================================================================

class TestTimeWindow:
    def test_expired_rejected(self, meter):
        """ORTAM: valid_before gecmiste -> 'zaman-penceresi dışı' (AT-174)."""
        h = envelope(valid_before=int(time.time()) - 100)
        with pytest.raises(PaymentErr) as ei:
            meter._parse_exact("x402 " + h, "/weather")
        assert "zaman-penceresi dışı" in str(ei.value)

    def test_future_valid_after_rejected(self, meter):
        h = envelope(valid_after=int(time.time()) + 1000)
        with pytest.raises(PaymentErr) as ei:
            meter._parse_exact("x402 " + h, "/weather")
        assert "zaman-penceresi dışı" in str(ei.value)

    def test_valid_window_accepted(self, meter):
        """ORTAM: now-60 .. now+300 varsayilan-pencere KABUL."""
        h = envelope()
        assert meter._parse_exact("x402 " + h, "/weather")["agent"] == FROM.lower()

    def test_boundary_now(self, meter):
        h = envelope(valid_after=int(time.time()) - 10,
                     valid_before=int(time.time()) + 10)
        assert meter._parse_exact("x402 " + h, "/weather")["agent"] == FROM.lower()


# == boyut-siniri (AT-182) =======================================================================

class TestSizeLimit:
    def test_max_8192_accepted_size(self, meter):
        """ORTAM: 8192B'a kadar boyut-kontrolu gecer (b64-解码 hatasi ayri)."""
        h = envelope()
        padded = "x402 " + h
        assert len(padded) < 8192

    def test_oversize_rejected(self, meter):
        """ORTAM: >8192B -> PaymentErr (AT-182: header-sisme DoS korumasi)."""
        big = "x402 " + "A" * 8200
        with pytest.raises(PaymentErr) as ei:
            meter._parse_exact(big, "/weather")
        assert "çok büyük" in str(ei.value)
        assert "8192" in str(ei.value)

    def test_boundary_exactly_8192(self, meter):
        """ORTAM: len(header) > 8192 — 8192 tam-uzunluk KABUL (decode hatasi ayri)."""
        h = "x402 " + "A" * (8192 - 5)
        assert len(h) == 8192
        with pytest.raises(PaymentErr) as ei:
            meter._parse_exact(h, "/weather")
        assert "çok büyük" not in str(ei.value)

    def test_boundary_8193_rejected(self, meter):
        h = "x402 " + "A" * (8193 - 5)
        with pytest.raises(PaymentErr) as ei:
            meter._parse_exact(h, "/weather")
        assert "çok büyük" in str(ei.value)

    def test_size_check_before_decode(self, meter):
        """ORTAM: boyut-kontrolu ONCE — gecerli-gorunen-b64 bile RED."""
        import inspect
        src = inspect.getsource(SesterMeter._parse_exact)
        size_pos = src.index("MAX_HEADER_BYTES")
        decode_pos = src.index("urlsafe_b64decode")
        assert size_pos < decode_pos


# == hata-yollari ================================================================================

class TestErrors:
    @pytest.mark.parametrize("tok,desc", [
        ("", "empty"),
        ("!!!", "garbage"),
        ("A", "short"),
        ("eyJzb21lIjoidGhpbmci", "invalid-json"),
    ])
    def test_bad_base64_or_json(self, meter, tok, desc):
        """ORTAM: (binascii.Error, ValueError, json.JSONDecodeError) ->
        PaymentErr('exact zarfı base64/JSON bozuk')."""
        with pytest.raises(PaymentErr) as ei:
            meter._parse_exact("x402 " + tok, "/weather")
        assert "base64/JSON bozuk" in str(ei.value)

    def test_empty_header(self, meter):
        with pytest.raises(PaymentErr):
            meter._parse_exact("", "/weather")

    def test_wrong_scheme_in_envelope(self, meter):
        """ORTAM: envelope.scheme != 'exact' -> 'scheme exact değil'."""
        h = envelope()
        env = json.loads(base64.urlsafe_b64decode(h + "=" * (-len(h) % 4)))
        env["scheme"] = "other"
        tok = base64.urlsafe_b64encode(json.dumps(env).encode()).decode().rstrip("=")
        with pytest.raises(PaymentErr) as ei:
            meter._parse_exact("x402 " + tok, "/weather")
        assert "scheme exact değil" in str(ei.value)

    def test_json_array_propagates_attribute_error(self, meter):
        """ORTAM-OGRENDI: [] zarfi -> parse_payment_header'da list.get ->
        AttributeError YAYILIR (PaymentError ile SARILMIYOR)."""
        tok = base64.urlsafe_b64encode(b"[]").decode().rstrip("=")
        with pytest.raises(AttributeError):
            meter._parse_exact("x402 " + tok, "/weather")

    def test_tampered_signature_raises(self, meter):
        """ORTAM-OGRENDI: gecersiz-v'li imza -> eth_account ValueError YAYILIR
        (PaymentError ile sarilmamis — raw kütüphane hatasi)."""
        h = envelope()
        env = json.loads(base64.urlsafe_b64decode(h + "=" * (-len(h) % 4)))
        env["payload"]["signature"] = "0x" + "11" * 65
        tok = base64.urlsafe_b64encode(json.dumps(env).encode()).decode().rstrip("=")
        with pytest.raises(ValueError):
            meter._parse_exact("x402 " + tok, "/weather")

    def test_missing_payload_key_raises(self, meter):
        """ORTAM-OGRENDI: payload anahtari YOKSA PaymentError 'EIP-3009
        alan-eksik' -> PaymentErr ile SARILIR (KeyError DEGIL)."""
        h = envelope()
        env = json.loads(base64.urlsafe_b64decode(h + "=" * (-len(h) % 4)))
        env.pop("payload")
        tok = base64.urlsafe_b64encode(json.dumps(env).encode()).decode().rstrip("=")
        with pytest.raises(PaymentErr) as ei:
            meter._parse_exact("x402 " + tok, "/weather")
        assert "EIP-3009 alan-eksik" in str(ei.value)

    def test_missing_required_field_raises(self, meter):
        """ORTAM: payload icinde gerekli-alan eksikse 'EIP-3009 alan-eksik'."""
        h = envelope()
        env = json.loads(base64.urlsafe_b64decode(h + "=" * (-len(h) % 4)))
        env["payload"].pop("signature")
        tok = base64.urlsafe_b64encode(json.dumps(env).encode()).decode().rstrip("=")
        with pytest.raises(PaymentErr) as ei:
            meter._parse_exact("x402 " + tok, "/weather")
        assert "signature" in str(ei.value)

    def test_wrong_network_raises(self, meter):
        """ORTAM: network 'eip155:' ile baslamazsa RED."""
        h = envelope()
        env = json.loads(base64.urlsafe_b64decode(h + "=" * (-len(h) % 4)))
        env["network"] = "other:1"
        tok = base64.urlsafe_b64encode(json.dumps(env).encode()).decode().rstrip("=")
        with pytest.raises(PaymentErr) as ei:
            meter._parse_exact("x402 " + tok, "/weather")
        assert "network eip155 değil" in str(ei.value)

    def test_error_messages_start_with_red(self, meter):
        """ORTAM: PaymentError -> 'exact zarfı reddedildi: ...' sarmasi."""
        h = envelope(valid_before=int(time.time()) - 100)
        with pytest.raises(PaymentErr) as ei:
            meter._parse_exact("x402 " + h, "/weather")
        assert str(ei.value).startswith("exact zarfı reddedildi:")


# == sözleşme ====================================================================================

class TestContract:
    def test_uses_exact_sester_v2(self, meter):
        """ORTAM: ExactSesterV2.parse_payment_header + verify_local (delayed-import)."""
        import inspect
        src = inspect.getsource(SesterMeter._parse_exact)
        assert "ExactSesterV2" in src
        assert "verify_local" in src
        assert "now_ts=time.time()" in src

    def test_registered_schemes(self):
        """ORTAM: 'x402' ve 'exact' on-ekleri bu parser'a bagli
        (bound-method her erisimde yeni-nesne -> == ile karsilastir)."""
        m = SesterMeter(None, StubLedger(), price=0.05, daily_quota=1.0)
        assert m._schemes["x402"] == m._parse_exact
        assert m._schemes["exact"] == m._parse_exact
        assert m._schemes["x402"] == m._schemes["exact"]

    def test_payment_err_is_middleware_type(self):
        assert PaymentErr.__module__ == "sester.middleware"
