"""sester.facilitator_svc.service.FacilitatorService._parse / _tx_count /
_settled_minor_for / _refunded_minor_for / _metrics_text dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — Ledger(':memory:') + SESTER_FACILITATOR_SECRET env
(gercek DB / network / subprocess YOK).
"""
import json
import os

import pytest

from sester.facilitator_svc.service import FacilitatorService
from sester.ledger import Ledger


@pytest.fixture
def svc():
    """Kural-4: memory-ledger + env-secret (gercek-DB YOK)."""
    os.environ["SESTER_FACILITATOR_SECRET"] = "dal-test-secret"
    lg = Ledger(":memory:", secret="led-secret")
    return FacilitatorService(lg)


@pytest.fixture
def ledger(svc):
    return svc.ledger


# == _parse ======================================================================================

class TestParse:
    def test_unknown_prefix_returns_none_empty(self, svc):
        assert svc._parse("unknown xxx", "/r") == (None, {})

    @pytest.mark.parametrize("payment", [
        "", "   ", "noprefix", "nope arg1 arg2", "12345",
    ])
    def test_no_known_prefix_returns_none(self, svc, payment):
        assert svc._parse(payment, "/r") == (None, {})

    def test_valid_pugio0_token(self, svc):
        import hashlib
        import hmac
        mac = hmac.new(svc._meter.secret, b"a|n|0.05|/r", hashlib.sha256).hexdigest()
        seller, parsed = svc._parse(f"pugio0 a:n:0.05:{mac}", "/r")
        assert seller == "a"
        assert parsed == {"agent": "a", "nonce": "n", "amount": "0.05",
                          "scheme": "pugio0"}

    def test_seller_field_is_agent(self, svc):
        import hashlib
        import hmac
        mac = hmac.new(svc._meter.secret, "görev-1|n|0.05|/r".encode(),
                       hashlib.sha256).hexdigest()
        seller, parsed = svc._parse(f"pugio0 görev-1:n:0.05:{mac}", "/r")
        assert seller == "görev-1"
        assert seller == parsed["agent"]

    def test_seller_returned_as_str(self, svc):
        import hashlib
        import hmac
        mac = hmac.new(svc._meter.secret, b"a|n|0.05|/r", hashlib.sha256).hexdigest()
        seller, _ = svc._parse(f"pugio0 a:n:0.05:{mac}", "/r")
        assert isinstance(seller, str)

    def test_bad_mac_returns_none(self, svc):
        assert svc._parse("pugio0 a:n:0.05:deadbeef", "/r") == (None, {})

    @pytest.mark.parametrize("bad", [
        "pugio0 a:n:0.05",
        "pugio0 a:n:0.05:x:y",
        "pugio0 :n:0.05:" + "a" * 64,
        "pugio0 a::0.05:" + "a" * 64,
    ])
    def test_malformed_returns_none(self, svc, bad):
        """ORTAM: PaymentErr yakalanir -> (None, {})."""
        assert svc._parse(bad, "/r") == (None, {})

    def test_wrong_resource_returns_none(self, svc):
        import hashlib
        import hmac
        mac = hmac.new(svc._meter.secret, b"a|n|0.05|/r", hashlib.sha256).hexdigest()
        assert svc._parse(f"pugio0 a:n:0.05:{mac}", "/other") == (None, {})

    def test_whitespace_stripped(self, svc):
        import hashlib
        import hmac
        mac = hmac.new(svc._meter.secret, b"a|n|0.05|/r", hashlib.sha256).hexdigest()
        seller, _ = svc._parse(f"  pugio0 a:n:0.05:{mac}  ", "/r")
        assert seller == "a"

    def test_exception_swallowed(self, svc):
        """ORTAM: try/except PaymentErr — hata YAYILMAZ (None dalar)."""
        result = svc._parse("pugio0 a:n:0.05:bad", "/r")
        assert result == (None, {})

    def test_prefix_case_sensitive(self, svc):
        """ORTAM: 'PUGIO0' buyuk-harf -> register-edilmemis -> (None, {})."""
        assert svc._parse("PUGIO0 a:n:0.05:x", "/r") == (None, {})

    def test_prefix_is_first_token(self, svc):
        """ORTAM: split(' ',1)[0] — ilk-boslugun-onu on-ek."""
        import hashlib
        import hmac
        mac = hmac.new(svc._meter.secret, b"a|n|0.05|/r", hashlib.sha256).hexdigest()
        seller, _ = svc._parse(f"pugio0 a:n:0.05:{mac}", "/r")
        assert seller == "a"

    def test_uses_meter_scheme_registry(self, svc):
        """ORTAM: self._meter._schemes — SesterMeter'in kayitli parser-lari."""
        assert "pugio0" in svc._meter._schemes
        assert "Sester-EVM" in svc._meter._schemes


# == _tx_count ===================================================================================

class TestTxCount:
    def test_empty_ledger_returns_0(self, svc):
        assert svc._tx_count("s1") == 0

    def test_returns_int(self, svc):
        assert isinstance(svc._tx_count("s1"), int)

    def test_counts_metering(self, ledger, svc):
        ledger.append("facilitator_metering", "s1", "/r", payload={"k": "v"})
        assert svc._tx_count("s1") == 1

    def test_multiple_metering(self, ledger, svc):
        for _ in range(5):
            ledger.append("facilitator_metering", "s1", "/r", payload={})
        assert svc._tx_count("s1") == 5

    def test_refund_of_excluded(self, ledger, svc):
        """ORTAM: payload.refund_of VARSA sayilmaz (free-band erken-kapanmasin)."""
        ledger.append("facilitator_metering", "s1", "/r", payload={})
        ledger.append("facilitator_metering", "s1", "/r", payload={"refund_of": "x"})
        assert svc._tx_count("s1") == 1

    def test_empty_refund_of_excluded(self, ledger, svc):
        """ORTAM: 'in p' kontrolu — bos-string DE excluded (falsy DEGIL in-check)."""
        ledger.append("facilitator_metering", "s1", "/r", payload={"refund_of": ""})
        assert svc._tx_count("s1") == 0

    def test_refund_of_none_excluded(self, ledger, svc):
        ledger.append("facilitator_metering", "s1", "/r", payload={"refund_of": None})
        assert svc._tx_count("s1") == 0

    def test_case_sensitive_key(self, ledger, svc):
        """ORTAM: 'REFUND_OF' != 'refund_of' — case-sensitive anahtar."""
        ledger.append("facilitator_metering", "s1", "/r", payload={"REFUND_OF": "x"})
        assert svc._tx_count("s1") == 1

    @pytest.mark.parametrize("event_type", [
        "facilitator_verify", "facilitator_settle", "facilitator_refund",
        "facilitator_batch", "charge_receipt", "refund",
    ])
    def test_other_event_types_excluded(self, ledger, svc, event_type):
        ledger.append(event_type, "s1", "/r", payload={}, amount=0.01)
        assert svc._tx_count("s1") == 0

    def test_sellers_isolated(self, ledger, svc):
        ledger.append("facilitator_metering", "s1", "/r", payload={})
        ledger.append("facilitator_metering", "s1", "/r", payload={})
        ledger.append("facilitator_metering", "s2", "/r", payload={})
        assert svc._tx_count("s1") == 2
        assert svc._tx_count("s2") == 1

    def test_unknown_seller_returns_0(self, ledger, svc):
        ledger.append("facilitator_metering", "s1", "/r", payload={})
        assert svc._tx_count("nobody") == 0

    def test_null_payload_counted(self, ledger, svc):
        """ORTAM-OGRENDI: payload=None -> 'or "{}"' yedegi DICT verir -> sayilir."""
        ledger.append("facilitator_metering", "s1", "/r", payload=None)
        assert svc._tx_count("s1") == 1

    def test_missing_payload_key_counted(self, ledger, svc):
        ledger.append("facilitator_metering", "s1", "/r", payload={})
        assert svc._tx_count("s1") == 1


# == _settled_minor_for ==========================================================================

class TestSettledMinorFor:
    def test_no_settle_returns_none(self, svc):
        assert svc._settled_minor_for("s1", "n1") is None

    def test_returns_int_when_found(self, ledger, svc):
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "n1", "decision": "allow", "amount_minor": 500})
        r = svc._settled_minor_for("s1", "n1")
        assert r == 500
        assert isinstance(r, int)

    @pytest.mark.parametrize("amt,expected", [
        (0, 0), (1, 1), (500, 500), (1_000_000, 1_000_000),
        ("700", 700), ("0", 0),
    ])
    def test_amount_values(self, ledger, svc, amt, expected):
        """ORTAM: int(p.get('amount_minor', 0)) — string de int'e coercion."""
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "n1", "decision": "allow", "amount_minor": amt})
        assert svc._settled_minor_for("s1", "n1") == expected

    def test_missing_amount_defaults_0(self, ledger, svc):
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "n1", "decision": "allow"})
        assert svc._settled_minor_for("s1", "n1") == 0

    def test_deny_decision_returns_none(self, ledger, svc):
        """ORTAM: decision!='allow' -> None (fail-closed)."""
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "n1", "decision": "deny", "amount_minor": 999})
        assert svc._settled_minor_for("s1", "n1") is None

    @pytest.mark.parametrize("decision", ["Deny", "ALLOW", "", "rejected"])
    def test_decision_case_sensitive(self, ledger, svc, decision):
        """ORTAM: == 'allow' case-sensitive — buyuk-harf RED."""
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "n1", "decision": decision, "amount_minor": 5})
        assert svc._settled_minor_for("s1", "n1") is None

    def test_wrong_nonce_returns_none(self, ledger, svc):
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "n1", "decision": "allow", "amount_minor": 5})
        assert svc._settled_minor_for("s1", "other") is None

    def test_missing_nonce_in_payload_skipped(self, ledger, svc):
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"decision": "allow", "amount_minor": 5})
        assert svc._settled_minor_for("s1", "n1") is None

    def test_first_match_wins(self, ledger, svc):
        """ORTAM: dongu return — ILK allow-eslesmesi doner (sonra aramaz)."""
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "n1", "decision": "allow", "amount_minor": 500})
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "n1", "decision": "allow", "amount_minor": 9999})
        assert svc._settled_minor_for("s1", "n1") == 500

    def test_sellers_isolated(self, ledger, svc):
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "n1", "decision": "allow", "amount_minor": 500})
        ledger.append("facilitator_settle", "s2", "/r",
                      payload={"nonce": "n1", "decision": "allow", "amount_minor": 1})
        assert svc._settled_minor_for("s1", "n1") == 500
        assert svc._settled_minor_for("s2", "n1") == 1

    def test_unknown_seller_returns_none(self, ledger, svc):
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "n1", "decision": "allow", "amount_minor": 5})
        assert svc._settled_minor_for("nobody", "n1") is None

    def test_non_settle_events_ignored(self, ledger, svc):
        ledger.append("facilitator_metering", "s1", "/r",
                      payload={"nonce": "n1", "decision": "allow", "amount_minor": 5})
        assert svc._settled_minor_for("s1", "n1") is None

    def test_allow_after_deny_finds_allow(self, ledger, svc):
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "n1", "decision": "deny", "amount_minor": 5})
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "n1", "decision": "allow", "amount_minor": 7})
        assert svc._settled_minor_for("s1", "n1") == 7


# == _refunded_minor_for =========================================================================

class TestRefundedMinorFor:
    def test_no_refunds_returns_0(self, svc):
        assert svc._refunded_minor_for("s1", "nr") == 0

    def test_returns_int(self, svc):
        assert isinstance(svc._refunded_minor_for("s1", "nr"), int)

    @pytest.mark.parametrize("amount,expected", [
        (0.0001, 100), (0.0002, 200), (0.000001, 1), (1.0, 1_000_000),
    ])
    def test_single_refund(self, ledger, svc, amount, expected):
        """ORTAM: int(r.get('amount_minor') or 0) — LEDGER minor'a cevirir."""
        ledger.append("refund", "s1", "/r", payload={"nonce": "nr"}, amount=amount)
        assert svc._refunded_minor_for("s1", "nr") == expected

    def test_multiple_refunds_summed(self, ledger, svc):
        ledger.append("refund", "s1", "/r", payload={"nonce": "nr"}, amount=0.0001)
        ledger.append("refund", "s1", "/r", payload={"nonce": "nr"}, amount=0.0002)
        assert svc._refunded_minor_for("s1", "nr") == 300

    def test_sellers_isolated(self, ledger, svc):
        ledger.append("refund", "s1", "/r", payload={"nonce": "nr"}, amount=0.0001)
        ledger.append("refund", "s2", "/r", payload={"nonce": "nr"}, amount=1.0)
        assert svc._refunded_minor_for("s1", "nr") == 100
        assert svc._refunded_minor_for("s2", "nr") == 1_000_000

    def test_nonce_filter(self, ledger, svc):
        ledger.append("refund", "s1", "/r", payload={"nonce": "nr"}, amount=0.0001)
        ledger.append("refund", "s1", "/r", payload={"nonce": "other"}, amount=0.0002)
        assert svc._refunded_minor_for("s1", "nr") == 100
        assert svc._refunded_minor_for("s1", "other") == 200

    def test_missing_nonce_skipped(self, ledger, svc):
        ledger.append("refund", "s1", "/r", payload={}, amount=0.0001)
        assert svc._refunded_minor_for("s1", "nr") == 0

    def test_unknown_seller_returns_0(self, ledger, svc):
        ledger.append("refund", "s1", "/r", payload={"nonce": "nr"}, amount=0.0001)
        assert svc._refunded_minor_for("nobody", "nr") == 0

    def test_non_refund_events_ignored(self, ledger, svc):
        ledger.append("facilitator_settle", "s1", "/r",
                      payload={"nonce": "nr"}, amount=0.0001)
        assert svc._refunded_minor_for("s1", "nr") == 0

    def test_null_payload_skipped(self, ledger, svc):
        """ORTAM-ANATOMI: payload=None -> 'or {}' yedegi -> dict -> nonce None."""
        ledger.append("refund", "s1", "/r", payload=None, amount=0.0001)
        assert svc._refunded_minor_for("s1", "nr") == 0

    def test_zero_amount_refund(self, ledger, svc):
        """ORTAM: amount_minor=0 -> 'or 0' yedegi -> 0 (None DEGIL)."""
        ledger.append("refund", "s1", "/r", payload={"nonce": "nr"}, amount=0.0)
        assert svc._refunded_minor_for("s1", "nr") == 0


# == _metrics_text ===============================================================================

class TestMetricsText:
    def test_returns_str(self, svc):
        assert isinstance(svc._metrics_text(), str)

    def test_ends_with_newline(self, svc):
        assert svc._metrics_text().endswith("\n")

    def test_prometheus_format(self, svc):
        text = svc._metrics_text()
        assert "# TYPE sester_facilitator_verify_ok counter" in text
        assert "sester_facilitator_verify_ok 0" in text

    def test_all_metric_counters_present(self, svc):
        text = svc._metrics_text()
        for k in svc.metrics:
            assert f"sester_facilitator_{k}" in text
            assert f"# TYPE sester_facilitator_{k} counter" in text

    def test_chain_valid_gauge(self, svc):
        text = svc._metrics_text()
        assert "# TYPE sester_facilitator_chain_valid gauge" in text
        assert "sester_facilitator_chain_valid" in text

    def test_chain_valid_on_empty_ledger(self, svc):
        """ORTAM: verify_chain() True -> gauge 1 (empty chain valid)."""
        assert "sester_facilitator_chain_valid 1" in svc._metrics_text()

    def test_metrics_reflect_state(self, svc, ledger):
        svc.metrics["verify_ok"] = 5
        svc.metrics["settled"] = 3
        text = svc._metrics_text()
        assert "sester_facilitator_verify_ok 5" in text
        assert "sester_facilitator_settled 3" in text

    def test_all_lines_have_metric_name(self, svc):
        for line in svc._metrics_text().splitlines():
            if line.startswith("sester_"):
                assert line.split()[0].startswith("sester_facilitator_")

    def test_type_line_before_value_line(self, svc):
        lines = svc._metrics_text().splitlines()
        # TYPE line index < value line index for the same metric
        type_idx = next(i for i, ln in enumerate(lines) if "TYPE" in ln)
        val_idx = next(i for i, ln in enumerate(lines)
                       if ln.startswith("sester_facilitator_"))
        assert type_idx < val_idx
