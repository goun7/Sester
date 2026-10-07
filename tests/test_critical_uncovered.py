"""Derin- kapsam testleri: AST taramasıyla bulunan, tests/ içinde adıyla
hiç referans verilmemiş EN KRİTİK kalan fonksiyonlar (2026-10-07).

Kapsanan test-dışı fonksiyonlar (mevcut testlerde ad geçmiyordu):
  * sester/settlement.py      — _rol64, _keccak_f, _pad_right32,
                                _abi_uint, _abi_address, _abi_string
                                (on-chain ödeme-calldata'sının tuğlaları)
  * sester/receipt.py         — receipt_canonical, _proof_canonical,
                                verify_cosign (ödeme-kanıtı bütünlüğü)
  * sester/policy.py          — Policy._validate_rule (fail-closed DSL kapısı)
  * sester/ledger.py          — Ledger.insert_nonce / export_nonces
                                (replay-penceresi kalıcılığı)
  * sester/facilitator_svc/service.py — record_transaction, _tx_count,
                                _settled_minor_for, _refunded_minor_for
                                (ücret-matematiği + iade-tavanı)

Tüm testler saf fonksiyonların kendi mantığını sınar; dış çağrı yoktur.
Mevcut testlerin/kodun hiçbirine dokunulmaz — yalnızca bu dosya eklendi.
"""
from __future__ import annotations

import hashlib

import pytest

from sester.evidence import proof_hash
from sester.facilitator_svc.service import FacilitatorService
from sester.ledger import Ledger
from sester.policy import ALLOW, DENY, ESCALATE, Policy, PolicyCorruptError
from sester.receipt import (
    RECEIPT_FIELDS,
    RECEIPT_PROOF_FIELDS,
    ReceiptError,
    _proof_canonical,
    cosign_receipt,
    issue_receipt,
    proof_of,
    receipt_canonical,
    verify_cosign,
)
from sester.settlement import (
    SETTLE_ABI_SIGNATURE,
    _SETTLE_SELECTOR,
    SettlementError,
    _abi_address,
    _abi_string,
    _abi_uint,
    _keccak_f,
    _pad_right32,
    _rol64,
    build_settle_calldata,
    keccak256,
)

SECRET = "test-node-secret-çok-gizli"


# --------------------------------------------------------------- settlement.ABI

class TestRol64:
    def test_bit_shift_within_u64(self):
        assert _rol64(1, 1) == 2
        assert _rol64(1, 3) == 8
        assert _rol64(0, 7) == 0

    def test_full_rotation_is_identity(self):
        # 64-bit tam-döngü: x >> (64-64) == x >> 0 → düşük-bit taşmaz
        assert _rol64(1, 64) == 1
        assert _rol64(0x123456789ABCDEF0, 64) == 0x123456789ABCDEF0

    def test_high_bit_wraps_to_low(self):
        assert _rol64(1 << 63, 1) == 1
        assert _rol64(0xDEADBEEF, 32) == ((0xDEADBEEF << 32) | (0xDEADBEEF >> 32)) & 0xFFFFFFFFFFFFFFFF

    def test_stays_inside_u64_mask(self):
        assert _rol64(0xFFFFFFFFFFFFFFFF, 1) == 0xFFFFFFFFFFFFFFFF


class TestKeccakF:
    def test_empty_message_known_digest(self):
        # Ethereum keccak256(b"") — bilinen-sabit-doğruluk-çapası
        # (standart-dışı implementasyon asla bu digest'i veremez)
        assert keccak256(b"").hex() == (
            "c5d2460186f7233c927e7db2dcc703c0e500b653"
            "ca82273b7bfad8045d85a470")

    def test_in_place_mutation_returns_none(self):
        state = [0] * 25
        ret = _keccak_f(state)
        assert ret is None
        # theta/rho/pi/chi/iota'dan-sonra sıfır-olmayan durum çıkar
        assert any(v != 0 for v in state)

    def test_keccak_not_sha3_padding(self):
        # SHA3-256(b"")'nin digest'i bu DEĞİLDİR (keccak pad 0x01..0x80)
        assert keccak256(b"").hex() != hashlib.sha3_256(b"").hexdigest()

    def test_distinct_inputs_distinct_digests(self):
        assert keccak256(b"a") != keccak256(b"b")
        assert len(keccak256(b"sester")) == 32

    def test_settle_selector_matches_signature(self):
        # fonksiyon-selektörü = keccak256(imza)[:4] — calldata'nın ilk 4 byte'ı
        assert _SETTLE_SELECTOR == keccak256(SETTLE_ABI_SIGNATURE.encode())[:4]
        calldata = build_settle_calldata(
            agent="0x" + "ab" * 20, total_minor=1_500_000,
            currency="USDC", evidence_root="0x" + "cd" * 32, count=3)
        assert calldata.startswith("0x" + _SETTLE_SELECTOR.hex())


class TestPadRight32:
    def test_empty_is_empty(self):
        assert _pad_right32(b"") == b""

    def test_pads_to_32(self):
        assert _pad_right32(b"abc") == b"abc" + b"\x00" * 29
        assert len(_pad_right32(b"x" * 1)) == 32

    def test_exact_block_unchanged(self):
        block = bytes(range(32))
        assert _pad_right32(block) == block

    def test_over_block_pads_to_next_multiple(self):
        assert len(_pad_right32(b"x" * 33)) == 64
        assert _pad_right32(b"x" * 33) == b"x" * 33 + b"\x00" * 31


class TestAbiUint:
    def test_zero(self):
        assert _abi_uint(0) == b"\x00" * 32

    def test_one(self):
        assert _abi_uint(1) == b"\x00" * 31 + b"\x01"

    def test_max_uint256(self):
        assert _abi_uint(2**256 - 1) == b"\xff" * 32

    @pytest.mark.parametrize("bad", [-1, -(2**256), 2**256, 2**256 + 1])
    def test_out_of_range_fail_closed(self, bad):
        with pytest.raises(SettlementError):
            _abi_uint(bad)


class TestAbiAddress:
    ADDR = "0x" + "ab" * 20

    def test_left_padded_to_32(self):
        assert _abi_address(self.ADDR) == b"\x00" * 12 + bytes.fromhex("ab" * 20)

    def test_case_and_prefix_insensitive(self):
        assert _abi_address(self.ADDR.upper()) == _abi_address(self.ADDR)
        assert _abi_address(self.ADDR.removeprefix("0x")) == _abi_address(self.ADDR)

    @pytest.mark.parametrize("bad", ["0x" + "ab" * 19, "0x" + "ab" * 21, "ab", ""])
    def test_bad_length_fail_closed(self, bad):
        with pytest.raises(SettlementError):
            _abi_address(bad)


class TestAbiString:
    def test_head_tail_encoding(self):
        enc = _abi_string("abc")
        assert enc == _abi_uint(3) + _pad_right32(b"abc")
        assert enc[:32] == _abi_uint(3)
        assert enc[32:35] == b"abc"

    def test_empty_string(self):
        # _pad_right32(b"") == b"" → yalnız uzunluk-head'i (32 byte)
        assert _abi_string("") == _abi_uint(0) == b"\x00" * 32

    def test_unicode_and_long(self):
        s = "çevre-ücret" * 10
        enc = _abi_string(s)
        assert enc[:32] == _abi_uint(len(s.encode()))
        assert enc[32:32 + len(s.encode())] == s.encode()
        assert len(enc) % 32 == 0


# ----------------------------------------------------------------- receipt.kanonik

def _event(**over):
    ev = {"seq": 7, "ts": 1234.5, "agent_id": "agent-x",
          "host": "api.example.com", "amount": "1.5",
          "amount_minor": 1_500_000, "payload": "hello", "prev_hash": "",
          "event_type": "charge_receipt"}
    ev.update(over)
    return ev


class TestReceiptCanonical:
    def test_field_order_and_float_format(self):
        rec = issue_receipt(_event(), node_id="node-1", node_secret=SECRET)
        canon = receipt_canonical(rec)
        # RECEIPT_FIELDS sırası donuktur; amount/ts %.6f ile biçimlenir
        assert canon.split("|")[0] == str(rec["receipt_version"])
        assert canon.split("|")[1] == "node-1"
        assert canon.split("|")[2] == "agent-x"
        assert "1.500000" in canon
        assert "1234.500000" in canon

    def test_missing_field_fail_closed(self):
        rec = issue_receipt(_event(), node_secret=SECRET)
        for f in RECEIPT_FIELDS:
            broken = dict(rec)
            del broken[f]
            with pytest.raises(ReceiptError):
                receipt_canonical(broken)

    def test_none_field_fail_closed(self):
        rec = issue_receipt(_event(), node_secret=SECRET)
        broken = dict(rec)
        broken["currency"] = None
        with pytest.raises(ReceiptError):
            receipt_canonical(broken)

    def test_hash_is_sha256_of_canonical(self):
        rec = issue_receipt(_event(), node_secret=SECRET)
        from sester.receipt import receipt_hash
        assert receipt_hash(rec) == hashlib.sha256(
            receipt_canonical(rec).encode()).hexdigest()


class TestProofCanonical:
    def test_proof_fields_order(self):
        rec = issue_receipt(_event(), node_secret=SECRET)
        expect = "|".join([
            f"{float(rec['ts']):.6f}", str(rec["event_type"]),
            str(rec["sub"]), str(rec["resource"]),
            f"{float(rec['amount']):.6f}", str(rec["payload"]),
            str(rec["prev_proof"]),
        ])
        assert _proof_canonical(rec) == expect

    def test_proof_of_matches_canonical(self):
        rec = issue_receipt(_event(), node_secret=SECRET)
        assert proof_of(rec) == hashlib.sha256(
            _proof_canonical(rec).encode()).hexdigest()

    def test_identical_to_evidence_proof_hash(self):
        # K0-uyumu: receipt.asıl-kanıt == evidence.proof_hash (birebir)
        ev = _event()
        rec = issue_receipt(ev, node_secret=SECRET)
        assert proof_of(rec) == proof_hash(ev, ev["prev_hash"] or "")

    def test_receipt_proof_fields_are_public_constant(self):
        assert RECEIPT_PROOF_FIELDS == (
            "ts", "event_type", "sub", "resource", "amount",
            "payload", "prev_proof")


class TestVerifyCosign:
    def test_valid_secret_bytes_and_str_equivalent(self):
        rec = issue_receipt(_event(), node_secret=SECRET)
        assert verify_cosign(rec, SECRET) is True
        assert verify_cosign(rec, SECRET.encode()) is True

    def test_wrong_secret_rejected(self):
        rec = issue_receipt(_event(), node_secret=SECRET)
        assert verify_cosign(rec, "başka-bir-secret") is False

    def test_empty_secret_rejected(self):
        rec = issue_receipt(_event(), node_secret=SECRET)
        assert verify_cosign(rec, "") is False
        assert verify_cosign(rec, b"") is False

    def test_missing_cosign_rejected(self):
        rec = issue_receipt(_event(), node_secret=SECRET)
        del rec["node_cosign"]
        assert verify_cosign(rec, SECRET) is False

    def test_tampered_any_receipt_field_invalidates(self):
        rec = issue_receipt(_event(), node_secret=SECRET)
        for f in ("iss", "sub", "resource", "amount", "amount_minor",
                  "currency", "ts", "seq", "payload", "prev_proof",
                  "chain_head", "node_key_id"):
            broken = dict(rec)
            broken[f] = "0" if isinstance(rec[f], str) else 999999
            assert verify_cosign(broken, SECRET) is False, f"değişiklik yakalanmadı: {f}"

    def test_cosign_changes_with_key_id(self):
        # cosign = HMAC(receipt_hash|node_key_id) → key-id değişirse bozulur
        rec = issue_receipt(_event(), node_secret=SECRET)
        assert verify_cosign(rec, SECRET) is True
        broken = dict(rec)
        broken["node_key_id"] = "other-key"
        assert verify_cosign(broken, SECRET) is False

    def test_no_secret_in_receipt_is_honest_empty(self):
        rec = issue_receipt(_event())  # node_secret verilmedi
        assert rec["node_cosign"] == ""
        assert verify_cosign(rec, SECRET) is False
        # ama secret'sız asıl-kanıt hâlâ sağlamdır
        assert proof_of(rec) == rec["proof"]

    def test_cosign_is_hex_mac(self):
        rec = issue_receipt(_event(), node_secret=SECRET)
        # hmac.new(sha256) → 64 küçük-hex karakter; tekrar-üretilebilir
        assert cosign_receipt(rec, SECRET) == rec["node_cosign"]
        assert len(rec["node_cosign"]) == 64
        assert all(c in "0123456789abcdef" for c in rec["node_cosign"])


# --------------------------------------------------------------- policy._validate_rule

class TestValidateRule:
    def _ok(self, **over):
        rule = {"id": "r1", "then": "allow", "when": {"host_in": ["a.com"]}}
        rule.update(over)
        return rule

    def test_valid_minimal_rule(self):
        assert Policy._validate_rule(0, self._ok()) is None

    def test_valid_all_when_keys(self):
        rule = self._ok(then="escalate",
                        when={"host_in": ["a.com", "b.com"],
                              "hour_between": ["09:00", "17:00"],
                              "amount_gt": "1.5",
                              "hour_in": ["10:00", "11:00"],
                              "agent_in": ["ag-1"]})
        assert Policy._validate_rule(1, rule) is None

    @pytest.mark.parametrize("then", ["Allow", "ALLOW", "block", "", None, 5])
    def test_invalid_verdict(self, then):
        with pytest.raises(PolicyCorruptError):
            Policy._validate_rule(0, {"id": "r1", "then": then, "when": {}})

    def test_verdict_deny_escalate_allowed(self):
        for v in (DENY, ESCALATE, ALLOW):
            assert Policy._validate_rule(0, {"id": "r1", "then": v, "when": {}}) is None

    def test_non_object_rule(self):
        with pytest.raises(PolicyCorruptError, match="nesne değil"):
            Policy._validate_rule(2, "nope")

    @pytest.mark.parametrize("rid", [None, "", 5])
    def test_missing_or_bad_id(self, rid):
        with pytest.raises(PolicyCorruptError, match="id eksik"):
            Policy._validate_rule(0, {"id": rid, "then": "allow"})

    def test_when_not_object(self):
        with pytest.raises(PolicyCorruptError, match="when nesne değil"):
            Policy._validate_rule(0, {"id": "r1", "then": "allow", "when": []})

    def test_host_in_not_list(self):
        with pytest.raises(PolicyCorruptError, match="host_in liste değil"):
            Policy._validate_rule(0, {"id": "r1", "then": "allow",
                                      "when": {"host_in": "a.com"}})

    @pytest.mark.parametrize("hb", [["09:00"], ["9:00", "17:00"], ["0900", "1700"],
                                     "09:00-17:00", [1, 2], ["aa:00", "17:00"]])
    def test_bad_hour_between(self, hb):
        with pytest.raises(PolicyCorruptError, match="hour_between"):
            Policy._validate_rule(0, {"id": "r1", "then": "allow",
                                      "when": {"hour_between": hb}})

    def test_good_hour_between(self):
        rule = self._ok(when={"hour_between": ["09:00", "17:00"]})
        assert Policy._validate_rule(0, rule) is None

    @pytest.mark.parametrize("amt", ["abc", None, [1]])
    def test_bad_amount_gt(self, amt):
        with pytest.raises(PolicyCorruptError, match="amount_gt sayı değil"):
            Policy._validate_rule(0, {"id": "r1", "then": "allow",
                                      "when": {"amount_gt": amt}})

    @pytest.mark.parametrize("hi", [[], ["0900"], "10:00", [1]])
    def test_bad_hour_in(self, hi):
        with pytest.raises(PolicyCorruptError, match="hour_in"):
            Policy._validate_rule(0, {"id": "r1", "then": "allow",
                                      "when": {"hour_in": hi}})

    @pytest.mark.parametrize("ai", [[], "ag-1", None])
    def test_bad_agent_in(self, ai):
        with pytest.raises(PolicyCorruptError, match="agent_in"):
            Policy._validate_rule(0, {"id": "r1", "then": "allow",
                                      "when": {"agent_in": ai}})

    def test_unknown_when_key_rejected(self):
        with pytest.raises(PolicyCorruptError, match="bilinmeyen-anahtar"):
            Policy._validate_rule(0, {"id": "r1", "then": "allow",
                                      "when": {"hostt_in": ["a.com"]}})

    def test_from_dict_rejects_bad_rule(self):
        raw = {"wallet_policy": {"id": "p1",
                                 "defaults": {"per_request_max": 1,
                                              "daily_max": 10},
                                 "rules": [{"id": "x", "then": "nope"}]}}
        with pytest.raises(PolicyCorruptError):
            Policy.from_dict(raw)


# --------------------------------------------------------------- ledger.nonce

class TestLedgerNonces:
    def _ledger(self, tmp_path):
        led = Ledger(str(tmp_path / "nonces.db"), secret=SECRET)
        return led

    def test_insert_and_export(self, tmp_path):
        led = self._ledger(tmp_path)
        try:
            led.insert_nonce("agent-a", "n1", 1.5)
            led.insert_nonce("agent-b", "n2", 2.5)
            out = led.export_nonces()
            assert out == [{"nonce_key": "agent-a|n1", "ts": 1.5},
                           {"nonce_key": "agent-b|n2", "ts": 2.5}]
        finally:
            led.close()

    def test_insert_is_idempotent_ignore(self, tmp_path):
        led = self._ledger(tmp_path)
        try:
            led.insert_nonce("agent-a", "n1", 1.5)
            led.insert_nonce("agent-a", "n1", 99.0)  # aynı anahtar → IGNORE
            rows = led.export_nonces()
            assert len(rows) == 1
            assert rows[0]["ts"] == 1.5
            assert led.nonce_count() == 1
        finally:
            led.close()

    def test_export_empty(self, tmp_path):
        led = self._ledger(tmp_path)
        try:
            assert led.export_nonces() == []
            assert led.nonce_count() == 0
        finally:
            led.close()

    def test_ordered_by_ts(self, tmp_path):
        led = self._ledger(tmp_path)
        try:
            led.insert_nonce("z", "late", 5.0)
            led.insert_nonce("a", "early", 1.0)
            keys = [r["nonce_key"] for r in led.export_nonces()]
            assert keys == ["a|early", "z|late"]
        finally:
            led.close()


# ------------------------------------------------------ facilitator_svc muhasebe

class TestFacilitatorAccounting:
    @pytest.fixture()
    def svc(self, tmp_path):
        led = Ledger(str(tmp_path / "svc.db"), secret=SECRET)
        yield FacilitatorService(led, secret=SECRET, free_transactions=2,
                                 percent_fee=0.01, flat_fee_minor=5000)

    def test_free_band_then_fees(self, svc):
        # free_transactions=2: ilk 2 işlem bedava
        assert svc.record_transaction("sat1", 1_000_000) == {
            "tx_index": 0, "charged_minor": 0, "free_band": True}
        assert svc.record_transaction("sat1", 1_000_000) == {
            "tx_index": 1, "charged_minor": 0, "free_band": True}
        # 3. işlem: %1 (10000) + flat (5000)
        r = svc.record_transaction("sat1", 1_000_000)
        assert r == {"tx_index": 2, "charged_minor": 15000, "free_band": False}

    def test_fee_math_rounding(self, svc):
        svc.record_transaction("sat1", 1_000_000)  # 0
        svc.record_transaction("sat1", 1_000_000)  # 1
        # 200 minor-birim %1 = 2 minor + 5000 flat
        assert svc.record_transaction("sat1", 200)["charged_minor"] == 5002

    def test_sellers_isolated(self, svc):
        assert svc.record_transaction("satA", 1_000_000)["tx_index"] == 0
        assert svc.record_transaction("satB", 1_000_000)["tx_index"] == 0
        assert svc._tx_count("satA") == 1
        assert svc._tx_count("satB") == 1

    def test_tx_count_excludes_refund_credits(self, svc):
        svc.record_transaction("sat1", 1_000_000)
        svc.record_transaction("sat1", 1_000_000)
        assert svc._tx_count("sat1") == 2
        # iade-kredi satırı sayılmaz (payload.refund_of)
        svc._proof("metering", "sat1", "",
                   {"tx_index": 2, "amount_minor": -1_000_000,
                    "charged_minor": 0, "free_band": True, "refund_of": "n1"})
        assert svc._tx_count("sat1") == 2

    def test_settled_minor_for(self, svc):
        svc._proof("settle", "sat1", "res",
                   {"nonce": "n1", "decision": "allow", "amount_minor": 7_000_000})
        assert svc._settled_minor_for("sat1", "n1") == 7_000_000

    def test_settled_minor_for_unknown_nonce_is_none(self, svc):
        assert svc._settled_minor_for("sat1", "yok") is None

    def test_settled_minor_for_ignores_non_allow(self, svc):
        svc._proof("settle", "sat1", "res",
                   {"nonce": "n2", "decision": "rejected", "amount_minor": 1_000})
        assert svc._settled_minor_for("sat1", "n2") is None

    def test_refunded_minor_for_accumulates(self, svc):
        svc.ledger.append("refund", "sat1", "res", 1.0, amount_minor=400_000,
                          payload={"nonce": "n1"})
        svc.ledger.append("refund", "sat1", "res", 0.5, amount_minor=200_000,
                          payload={"nonce": "n1"})
        svc.ledger.append("refund", "sat1", "res", 0.25, amount_minor=100_000,
                          payload={"nonce": "n9"})
        assert svc._refunded_minor_for("sat1", "n1") == 600_000
        assert svc._refunded_minor_for("sat1", "n9") == 100_000
        assert svc._refunded_minor_for("sat1", "none") == 0

    def _pay(self, seller, nonce, resource, amount_s="1.000000"):
        # pugio0-HMAC şeması: 'pugio0 <agent>:<nonce>:<amount>:<mac>'
        import hmac as _hmac
        msg = f"{seller}|{nonce}|{amount_s}|{resource}".encode()
        mac = _hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()
        return f"pugio0 {seller}:{nonce}:{amount_s}:{mac}"

    def test_refund_enforces_settlement_cap(self, svc):
        # 1_000_000 settle edildi; kısmi iadeler birikerek tavanı aşamaz
        svc._proof("settle", "sat1", "res",
                   {"nonce": "n1", "decision": "allow", "amount_minor": 1_000_000})
        assert svc.refund(self._pay("sat1", "n1", "res"), "res", 600_000).status == "ok"
        assert svc.refund(self._pay("sat1", "n1", "res"), "res", 500_000).status == "rejected"
        assert svc._refunded_minor_for("sat1", "n1") == 600_000

    def test_refund_without_settlement_denied(self, svc):
        d = svc.refund(self._pay("sat1", "n1", "res"), "res", 100)
        assert d.status == "rejected"
        assert d.reason == "refund_without_settlement"
