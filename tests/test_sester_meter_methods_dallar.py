"""sester.middleware.SesterMeter._header / _parse_hmac / _burst_allow / _challenge
dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — StubLedger + ASGI send stub + time.monotonic monkeypatch
(GERCEK ASGI server / network YOK).
"""
import base64
import hashlib
import hmac
import json
import time

import pytest

from sester.middleware import PaymentErr, SesterMeter


class StubLedger:
    """Ledger-stubu — secret bytes (gercek DB YOK)."""

    secret = b"test-secret"


def make_meter(**over):
    kw = dict(app=None, ledger=StubLedger(), price=0.05, daily_quota=1.0)
    kw.update(over)
    return SesterMeter(**kw)


def mac_for(meter, agent, nonce, amount, resource):
    return hmac.new(meter.secret,
                    f"{agent}|{nonce}|{amount}|{resource}".encode(),
                    hashlib.sha256).hexdigest()


# == _header =====================================================================================

class TestHeader:
    def test_returns_value(self):
        scope = {"headers": [(b"x-payment", b"pugio0 tok")]}
        assert SesterMeter._header(scope, "X-Payment") == "pugio0 tok"

    def test_case_insensitive_lookup(self):
        """ORTAM: header-anahtari LOWERCASE-normalize edilir."""
        scope = {"headers": [(b"x-agent", b"ag")]}
        assert SesterMeter._header(scope, "X-Agent") == "ag"
        assert SesterMeter._header(scope, "x-agent") == "ag"
        assert SesterMeter._header(scope, "X-AGENT") == "ag"

    def test_missing_header_returns_none(self):
        assert SesterMeter._header({"headers": []}, "X-Nope") is None

    def test_no_headers_key_returns_none(self):
        """ORTAM: scope.get('headers', []) — anahtar YOKSA None."""
        assert SesterMeter._header({}, "X") is None

    def test_empty_headers_list_returns_none(self):
        assert SesterMeter._header({"headers": []}, "X") is None

    def test_duplicate_first_wins(self):
        """ORTAM-OGRENDI: ayni-anahtardan birden-fazla varsa ILK doner
        (dongude ilk-eslesmede return)."""
        scope = {"headers": [(b"a", b"1"), (b"a", b"2"), (b"a", b"3")]}
        assert SesterMeter._header(scope, "A") == "1"

    def test_returns_str(self):
        assert isinstance(SesterMeter._header({"headers": [(b"a", b"v")]}, "A"), str)

    def test_latin1_decoding(self):
        """ORTAM: v.decode('latin-1') — byte'lar latin-1 ile cozulur."""
        raw = "ügi".encode("latin-1")
        assert SesterMeter._header({"headers": [(b"a", raw)]}, "A") == "ügi"

    def test_latin1_mangles_utf8_bytes(self):
        """ORTAM-OGRENDI: utf-8 encode'lanmis turkce byte'lar latin-1'de
        BOZULUR ('ü' -> 'Ã¼') — decoder latin-1 (utf-8 DEGIL), quirk dokumante."""
        raw = "ü".encode("utf-8")
        assert SesterMeter._header({"headers": [(b"a", raw)]}, "A") == "Ã¼"
        assert SesterMeter._header({"headers": [(b"a", raw)]}, "A") != "ü"

    def test_high_bytes_latin1_not_utf8(self):
        """ORTAM: 0x80+ byte'lar latin-1'de farkli-karakter (utf8 hata veriridi)."""
        raw = b"\xff\xfe"
        assert SesterMeter._header({"headers": [(b"a", raw)]}, "A") == "ÿþ"

    def test_non_bytes_value_raises(self):
        """ORTAM: deger bytes DEGILSE AttributeError YAYILIR (str.decode YOK)."""
        with pytest.raises(AttributeError):
            SesterMeter._header({"headers": [(b"a", "str")]}, "A")

    def test_empty_value_returns_empty_str(self):
        assert SesterMeter._header({"headers": [(b"a", b"")]}, "A") == ""

    def test_static_method_no_self(self):
        """ORTAM: @staticmethod — instance'siz cagrilabilir."""
        assert SesterMeter._header({"headers": [(b"a", b"v")]}, "a") == "v"

    @pytest.mark.parametrize("name", ["X-Payment", "x-payment", "X-PAYMENT"])
    def test_name_case_variants(self, name):
        scope = {"headers": [(b"x-payment", b"v")]}
        assert SesterMeter._header(scope, name) == "v"

    @pytest.mark.parametrize("val", [b"pugio0 a:b:c:d", b"  spaced  ",
                                     "türkçe".encode("latin-1"), b"\x00\x01"])
    def test_various_values(self, val):
        assert SesterMeter._header({"headers": [(b"a", val)]}, "A") == val.decode("latin-1")

    def test_multiple_headers_scan(self):
        scope = {"headers": [(b"a", b"1"), (b"b", b"2"), (b"c", b"3")]}
        assert SesterMeter._header(scope, "B") == "2"
        assert SesterMeter._header(scope, "C") == "3"


# == _parse_hmac =================================================================================

class TestParseHmac:
    def test_valid_token_returns_dict(self):
        m = make_meter()
        tok = f"pugio0 agent1:n1:0.05:{mac_for(m, 'agent1', 'n1', '0.05', '/w')}"
        r = m._parse_hmac(tok, "/w")
        assert r == {"agent": "agent1", "nonce": "n1", "amount": "0.05",
                     "scheme": "pugio0"}

    def test_scheme_is_version_constant(self):
        m = make_meter()
        tok = f"pugio0 a:n:0.05:{mac_for(m, 'a', 'n', '0.05', '/w')}"
        assert m._parse_hmac(tok, "/w")["scheme"] == SesterMeter.VERSION

    @pytest.mark.parametrize("agent,nonce,amount", [
        ("ag", "n1", "0.05"), ("görev-1", "nonce-ü", "0,25"),
        ("emoji", "😀", "1.00"), ("a" * 40, "n", "0.000001"),
    ])
    def test_formula_variants(self, agent, nonce, amount):
        """ORTAM: hmac-sha256(secret, 'agent|nonce|amount|resource')."""
        m = make_meter()
        tok = f"pugio0 {agent}:{nonce}:{amount}:{mac_for(m, agent, nonce, amount, '/p')}"
        r = m._parse_hmac(tok, "/p")
        assert r["agent"] == agent and r["nonce"] == nonce and r["amount"] == amount

    def test_uppercase_mac_accepted(self):
        """ORTAM-OGRENDI: mac.lower() karsilastirilir — BUYUK-harf hex KABUL."""
        m = make_meter()
        mac = mac_for(m, "a", "n", "0.05", "/w").upper()
        assert m._parse_hmac(f"pugio0 a:n:0.05:{mac}", "/w")["agent"] == "a"

    def test_whitespace_stripped(self):
        """ORTAM: header.strip() — leading/trailing bosluk temizlenir."""
        m = make_meter()
        tok = f"  pugio0 a:n:0.05:{mac_for(m, 'a', 'n', '0.05', '/w')}  "
        assert m._parse_hmac(tok, "/w")["agent"] == "a"

    @pytest.mark.parametrize("tok_desc,token", [
        ("3-alan", "pugio0 a:n:0.05"),
        ("5-alan", "pugio0 a:n:0.05:x:y"),
        ("2-alan", "pugio0 a:n"),
        ("bos", "pugio0 "),
    ])
    def test_wrong_field_count_raises(self, tok_desc, token):
        """ORTAM: len(parts)!=4 -> PaymentErr('doz-formatı bozuk')."""
        m = make_meter()
        with pytest.raises(PaymentErr) as ei:
            m._parse_hmac(token, "/w")
        assert "doz-formatı" in str(ei.value)

    @pytest.mark.parametrize("desc,mac", [
        ("bos-agent", ""),
        ("short-mac", "abc"),
        ("63-char", "a" * 63),
        ("65-char", "a" * 65),
    ])
    def test_bad_agent_or_mac_raises(self, desc, mac):
        """ORTAM: not agent / not nonce / len(mac)!=64 -> 'doz-alanları bozuk'."""
        m = make_meter()
        tok = f"pugio0 a:n:0.05:{mac}"
        with pytest.raises(PaymentErr) as ei:
            m._parse_hmac(tok, "/w")
        assert "doz-alanları" in str(ei.value)

    def test_empty_agent_raises(self):
        m = make_meter()
        tok = f"pugio0 :n:0.05:{mac_for(m, '', 'n', '0.05', '/w')}"
        with pytest.raises(PaymentErr) as ei:
            m._parse_hmac(tok, "/w")
        assert "doz-alanları" in str(ei.value)

    def test_empty_nonce_raises(self):
        m = make_meter()
        tok = f"pugio0 a::0.05:{mac_for(m, 'a', '', '0.05', '/w')}"
        with pytest.raises(PaymentErr) as ei:
            m._parse_hmac(tok, "/w")
        assert "doz-alanları" in str(ei.value)

    def test_wrong_resource_hmac_mismatch(self):
        """ORTAM: resource imzanin parçasi — baska-resource RED ('HMAC uyuşmuyor')."""
        m = make_meter()
        tok = f"pugio0 a:n:0.05:{mac_for(m, 'a', 'n', '0.05', '/other')}"
        with pytest.raises(PaymentErr) as ei:
            m._parse_hmac(tok, "/w")
        assert "HMAC uyuşmuyor" in str(ei.value)

    def test_tampered_mac_raises(self):
        m = make_meter()
        mac = mac_for(m, "a", "n", "0.05", "/w")
        bad = ("0" if mac[0] != "0" else "1") + mac[1:]
        with pytest.raises(PaymentErr):
            m._parse_hmac(f"pugio0 a:n:0.05:{bad}", "/w")

    def test_wrong_secret_in_meter_raises(self):
        """ORTAM: baska-secret ile uretilmis imza RED."""
        m1 = make_meter()
        m2 = make_meter(secret="other-secret")
        tok = f"pugio0 a:n:0.05:{mac_for(m2, 'a', 'n', '0.05', '/w')}"
        with pytest.raises(PaymentErr):
            m1._parse_hmac(tok, "/w")

    def test_amount_not_validated(self):
        """ORTAM-OGRENDI: amount HAM gecer — fiyat-kontrolu _parse_hmac'da YOK
        (mac dogru oldugu surece herhangi amount kabul)."""
        m = make_meter()
        tok = f"pugio0 a:n:99.99:{mac_for(m, 'a', 'n', '99.99', '/w')}"
        assert m._parse_hmac(tok, "/w")["amount"] == "99.99"

    def test_amount_comma_decimal(self):
        m = make_meter()
        tok = f"pugio0 a:n:0,5:{mac_for(m, 'a', 'n', '0,5', '/w')}"
        assert m._parse_hmac(tok, "/w")["amount"] == "0,5"

    def test_wrong_prefix_raises(self):
        """ORTAM: 'pugio0 ' on-ek kesilir; baska-on-ek parts-i kaydirir."""
        m = make_meter()
        with pytest.raises(PaymentErr):
            m._parse_hmac(f"other a:n:0.05:{'x' * 64}", "/w")

    def test_resource_with_query_string(self):
        m = make_meter()
        res = "/weather?sehir=istanbul"
        tok = f"pugio0 a:n:0.05:{mac_for(m, 'a', 'n', '0.05', res)}"
        assert m._parse_hmac(tok, res)["agent"] == "a"

    def test_query_string_resource_mismatch_raises(self):
        """ORTAM: query-string imzanin parcasi — baska-query RED."""
        m = make_meter()
        res = "/weather?sehir=istanbul"
        tok = f"pugio0 a:n:0.05:{mac_for(m, 'a', 'n', '0.05', res)}"
        with pytest.raises(PaymentErr):
            m._parse_hmac(tok, "/weather?sehir=ankara")

    def test_constant_time_comparison(self):
        """ORTAM: hmac.compare_digest kullanilir (zamanlama-saldiri korumasi)."""
        import inspect
        assert "compare_digest" in inspect.getsource(SesterMeter._parse_hmac)


# == _burst_allow ================================================================================

class TestBurstAllow:
    def test_first_request_allowed(self):
        m = make_meter()
        assert m._burst_allow("ag1") is True

    def test_returns_bool(self):
        m = make_meter()
        assert isinstance(m._burst_allow("x"), bool)

    def test_default_capacity_20(self):
        """ORTAM: burst_capacity=20 default — 20 istek allowed, 21. RED."""
        m = make_meter()
        results = [m._burst_allow("ag") for _ in range(20)]
        assert all(results)
        assert m._burst_allow("ag") is False

    def test_21st_denied(self):
        m = make_meter()
        for _ in range(20):
            m._burst_allow("ag")
        assert m._burst_allow("ag") is False

    def test_bucket_created_after_deny(self):
        """ORTAM: RED'da bile bucket GUNCELLENIR (tokens, now)."""
        m = make_meter()
        for _ in range(20):
            m._burst_allow("ag")
        m._burst_allow("ag")
        assert "ag" in m._buckets
        tokens, ts = m._buckets["ag"]
        assert tokens < 1.0
        assert isinstance(ts, float)

    def test_agents_isolated(self):
        """ORTAM: her-ajan ayri-bucket — a tuketse b serbest."""
        m = make_meter()
        for _ in range(20):
            m._burst_allow("a")
        assert m._burst_allow("a") is False
        assert m._burst_allow("b") is True

    @pytest.mark.parametrize("cap", [1, 2, 5, 10, 100])
    def test_custom_capacity(self, cap):
        m = make_meter(burst_capacity=cap)
        assert all(m._burst_allow("ag") for _ in range(cap))
        assert m._burst_allow("ag") is False

    def test_refill_over_time(self):
        """ORTAM: (now-last)*refill tokens eklenir — 1 token icin 0.1s * 10/s."""
        m = make_meter(burst_capacity=1, burst_refill_per_sec=10.0)
        assert m._burst_allow("ag") is True
        assert m._burst_allow("ag") is False
        # simulate 0.2s passed -> +2 tokens (capped at capacity 1)
        tokens, last = m._buckets["ag"]
        m._buckets["ag"] = (tokens, last - 0.2)
        assert m._burst_allow("ag") is True

    def test_refill_capped_at_capacity(self):
        """ORTAM: min(capacity, tokens+refill) — capacity uzerine cikmaz."""
        m = make_meter(burst_capacity=5, burst_refill_per_sec=1000.0)
        m._burst_allow("ag")
        tokens, last = m._buckets["ag"]
        m._buckets["ag"] = (tokens, last - 100)
        m._burst_allow("ag")
        remaining, _ = m._buckets["ag"]
        assert remaining <= 5.0

    def test_tokens_decrement_by_one(self):
        """ORTAM: allowed -> tokens-1.0."""
        m = make_meter(burst_capacity=10)
        m._burst_allow("ag")
        tokens, _ = m._buckets["ag"]
        assert tokens == 9.0

    def test_monotonic_clock(self):
        """ORTAM: time.monotonic() kullanilir (wall-clock DEGIL)."""
        import inspect
        assert "monotonic" in inspect.getsource(SesterMeter._burst_allow)

    def test_bucket_not_polluted_by_other_agents(self):
        m = make_meter()
        m._burst_allow("a")
        assert "b" not in m._buckets

    def test_repeat_denies_stay_denied(self):
        m = make_meter(burst_capacity=1)
        m._burst_allow("ag")
        assert m._burst_allow("ag") is False
        assert m._burst_allow("ag") is False


# == _challenge ==================================================================================

class TestChallenge:
    @pytest.fixture
    def capture(self):
        msgs = []

        async def send(msg):
            msgs.append(msg)
        return msgs, send

    @pytest.mark.asyncio
    async def test_sends_two_messages(self, capture):
        msgs, send = capture
        m = make_meter()
        await m._challenge(send, {"headers": []}, "err")
        assert len(msgs) == 2
        assert msgs[0]["type"] == "http.response.start"
        assert msgs[1]["type"] == "http.response.body"

    @pytest.mark.asyncio
    async def test_status_is_402(self, capture):
        msgs, send = capture
        await make_meter()._challenge(send, {"headers": []}, "err")
        assert msgs[0]["status"] == 402

    @pytest.mark.asyncio
    async def test_body_is_json(self, capture):
        msgs, send = capture
        await make_meter()._challenge(send, {"headers": []}, "err")
        payload = json.loads(msgs[1]["body"])
        assert payload["error"] == "err"
        assert payload["x402Version"] == 1

    @pytest.mark.asyncio
    async def test_challenge_payload_accepts(self, capture):
        msgs, send = capture
        await make_meter()._challenge(send, {"headers": []}, "err")
        payload = json.loads(msgs[1]["body"])
        schemes = [a["scheme"] for a in payload["accepts"]]
        assert "exact-sester" in schemes
        assert "pugio0" in schemes
        assert "exact" in schemes

    @pytest.mark.asyncio
    async def test_payment_required_header(self, capture):
        """ORTAM: X-Payment-Required = urlsafe-b64json(challenge-payload)."""
        msgs, send = capture
        await make_meter()._challenge(send, {"headers": []}, "err")
        hdrs = dict(msgs[0]["headers"])
        assert b"x-payment-required" in hdrs
        b64 = hdrs[b"x-payment-required"].decode()
        dec = json.loads(base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)))
        assert dec["error"] == "err"

    @pytest.mark.asyncio
    async def test_resource_from_scope_path(self, capture):
        msgs, send = capture
        await make_meter()._challenge(send, {"path": "/weather"}, "err")
        payload = json.loads(msgs[1]["body"])
        assert all(a["resource"] == "/weather" for a in payload["accepts"])

    @pytest.mark.asyncio
    async def test_resource_empty_without_path(self, capture):
        msgs, send = capture
        await make_meter()._challenge(send, {}, "err")
        payload = json.loads(msgs[1]["body"])
        assert all(a["resource"] == "" for a in payload["accepts"])

    @pytest.mark.asyncio
    async def test_content_type_header(self, capture):
        msgs, send = capture
        await make_meter()._challenge(send, {}, "err")
        hdrs = dict(msgs[0]["headers"])
        assert hdrs[b"content-type"] == b"application/json; charset=utf-8"

    @pytest.mark.asyncio
    async def test_content_length_matches_body(self, capture):
        msgs, send = capture
        await make_meter()._challenge(send, {}, "err")
        hdrs = dict(msgs[0]["headers"])
        assert int(hdrs[b"content-length"]) == len(msgs[1]["body"])

    @pytest.mark.parametrize("err", ["hata", "quota aşıldı", "😀", "x" * 100])
    @pytest.mark.asyncio
    async def test_error_messages_propagated(self, capture, err):
        msgs, send = capture
        await make_meter()._challenge(send, {}, err)
        assert json.loads(msgs[1]["body"])["error"] == err

    @pytest.mark.asyncio
    async def test_turkce_body_not_escaped(self, capture):
        """ORTAM: json.dumps(ensure_ascii=False) — turkce RAW."""
        msgs, send = capture
        await make_meter()._challenge(send, {}, "aşıldı")
        body = msgs[1]["body"]
        assert "aşıldı" in body.decode("utf-8")

    @pytest.mark.asyncio
    async def test_custom_price_in_challenge(self, capture):
        msgs, send = capture
        await make_meter(price=0.25)._challenge(send, {}, "err")
        payload = json.loads(msgs[1]["body"])
        assert all(a["maxAmountRequired"] == "0.250000" for a in payload["accepts"])

    @pytest.mark.asyncio
    async def test_currency_in_challenge(self, capture):
        msgs, send = capture
        await make_meter(currency="USDC-x")._challenge(send, {}, "err")
        payload = json.loads(msgs[1]["body"])
        assert all(a["currency"] == "USDC-x" for a in payload["accepts"])

    @pytest.mark.asyncio
    async def test_payto_in_challenge(self, capture):
        msgs, send = capture
        await make_meter(pay_to="sester:seller-x")._challenge(send, {}, "err")
        payload = json.loads(msgs[1]["body"])
        assert all(a["payTo"] == "sester:seller-x" for a in payload["accepts"])

    @pytest.mark.asyncio
    async def test_send_order(self, capture):
        msgs, send = capture
        await make_meter()._challenge(send, {}, "err")
        assert msgs[0]["type"] == "http.response.start"
        assert msgs[1]["type"] == "http.response.body"
