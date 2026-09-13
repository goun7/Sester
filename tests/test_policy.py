"""PUGIO policy testleri — KURAL_DSL_V0 §4 vektör-seti (fail-closed odaklı)."""

from __future__ import annotations

import datetime as _dt
import json

import pytest

from pugio.policy import ALLOW, DENY, ESCALATE, DenyAll, Policy, PolicyCorruptError

VALID = {
    "wallet_policy": {
        "id": "wpol-test",
        "owner": "did:agent:test",
        "wallet": "evm:0xTEST",
        "defaults": {
            "currency": "USDC",
            "per_request_max": 0.5,
            "daily_max": 25.0,
            "timezone": "Europe/Istanbul",
        },
        "rules": [
            {"id": "allow-day", "when": {"host_in": ["/weather"],
                                          "hour_between": ["08:00", "22:00"]},
             "then": "allow"},
            {"id": "escalate-large", "when": {"amount_gt": 5.0}, "then": "escalate"},
            {"id": "deny-rest", "when": {"host_in": []}, "then": "deny"},
        ],
        "audit": {"ledger": "tamga://t/a", "on_violation": "block+log"},
    }
}


def write_policy(tmp_path, raw):
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(raw) if isinstance(raw, dict) else raw, encoding="utf-8")
    return p


def at(hour, minute=0):
    return _dt.datetime(2026, 9, 12, hour, minute)


def pol():
    return Policy.from_dict(VALID)


# ---------- 1–8: karar-semantiği ----------

def test_01_allow_inside_window():
    d = pol().evaluate(0.05, "/weather", now=at(10))
    assert (d.verdict, d.rule_id) == (ALLOW, "allow-day")


def test_02_deny_outside_hour_window():
    d = pol().evaluate(0.05, "/weather", now=at(23))
    assert (d.verdict, d.rule_id) == (DENY, "deny-rest")


def test_03_unknown_host_caught_by_catchall_deny():
    d = pol().evaluate(0.05, "/unknown", now=at(10))
    assert (d.verdict, d.rule_id) == (DENY, "deny-rest")


def test_04_escalate_large_amount():
    d = pol().evaluate(6.0, "/big", now=at(10))
    assert (d.verdict, d.rule_id) == (ESCALATE, "escalate-large")


def test_05_default_deny_when_no_rule_matches():
    v = json.loads(json.dumps(VALID))
    v["wallet_policy"]["rules"] = [
        {"id": "allow-day", "when": {"host_in": ["/weather"],
                                     "hour_between": ["08:00", "22:00"]},
         "then": "allow"},
    ]
    d = Policy.from_dict(v).evaluate(0.05, "/other", now=at(10))
    assert (d.verdict, d.rule_id) == (DENY, "default-deny")


def test_06_overnight_window_inside():
    v = json.loads(json.dumps(VALID))
    v["wallet_policy"]["rules"] = [
        {"id": "night", "when": {"host_in": ["/batch"], "hour_between": ["22:00", "08:00"]},
         "then": "allow"},
    ]
    p = Policy.from_dict(v)
    assert p.evaluate(0.1, "/batch", now=at(23, 30)).verdict == ALLOW
    assert p.evaluate(0.1, "/batch", now=at(3, 15)).verdict == ALLOW


def test_07_overnight_window_outside():
    v = json.loads(json.dumps(VALID))
    v["wallet_policy"]["rules"] = [
        {"id": "night", "when": {"host_in": ["/batch"], "hour_between": ["22:00", "08:00"]},
         "then": "allow"},
    ]
    d = Policy.from_dict(v).evaluate(0.1, "/batch", now=at(12))
    assert d.verdict == DENY


def test_08_first_match_wins_order_semantics():
    v = json.loads(json.dumps(VALID))
    v["wallet_policy"]["rules"] = [
        {"id": "catchall-allow", "when": {"host_in": []}, "then": "allow"},
        {"id": "deny-all-after", "when": {"host_in": []}, "then": "deny"},
    ]
    d = Policy.from_dict(v).evaluate(0.1, "/anything", now=at(10))
    assert (d.verdict, d.rule_id) == (ALLOW, "catchall-allow")


# ---------- 9–16: fail-closed yükleme ----------

def test_09_missing_file_raises():
    with pytest.raises(PolicyCorruptError):
        Policy.load("/yok/bole/bir/dosya.json")


def test_10_corrupt_json_raises():
    with pytest.raises(PolicyCorruptError):
        Policy.from_dict("{bozuk json")


def test_11_missing_wallet_policy_key_raises():
    with pytest.raises(PolicyCorruptError):
        Policy.from_dict({"baskasi": {}})


def test_12_missing_limits_raise():
    v = json.loads(json.dumps(VALID))
    del v["wallet_policy"]["defaults"]["daily_max"]
    with pytest.raises(PolicyCorruptError):
        Policy.from_dict(v)


def test_13_negative_limits_raise():
    v = json.loads(json.dumps(VALID))
    v["wallet_policy"]["defaults"]["per_request_max"] = -1
    with pytest.raises(PolicyCorruptError):
        Policy.from_dict(v)


def test_14_daily_lt_per_request_raises():
    v = json.loads(json.dumps(VALID))
    v["wallet_policy"]["defaults"]["daily_max"] = 0.1
    with pytest.raises(PolicyCorruptError):
        Policy.from_dict(v)


def test_15_invalid_verdict_raises():
    v = json.loads(json.dumps(VALID))
    v["wallet_policy"]["rules"][0]["then"] = "belki"
    with pytest.raises(PolicyCorruptError):
        Policy.from_dict(v)


def test_16_bad_hour_between_raises():
    v = json.loads(json.dumps(VALID))
    v["wallet_policy"]["rules"][0]["when"]["hour_between"] = ["sabah", "aksam"]
    with pytest.raises(PolicyCorruptError):
        Policy.from_dict(v)


# ---------- 17–22: DenyAll + disk + şema-kenarları ----------

def test_17_deny_all_blocks_everything():
    d = DenyAll().evaluate(0.01, "/weather", now=at(10))
    assert d.verdict == DENY and d.rule_id == "fail-closed"
    assert DenyAll().per_request_max == 0.0


def test_18_load_roundtrip_from_disk(tmp_path):
    p = Policy.load(write_policy(tmp_path, VALID))
    assert p.policy_id == "wpol-test"
    assert p.per_request_max == 0.5


def test_19_rules_not_list_raises():
    v = json.loads(json.dumps(VALID))
    v["wallet_policy"]["rules"] = {"id": "x"}
    with pytest.raises(PolicyCorruptError):
        Policy.from_dict(v)


def test_20_rule_missing_id_raises():
    v = json.loads(json.dumps(VALID))
    del v["wallet_policy"]["rules"][0]["id"]
    with pytest.raises(PolicyCorruptError):
        Policy.from_dict(v)


def test_21_when_not_dict_raises():
    v = json.loads(json.dumps(VALID))
    v["wallet_policy"]["rules"][0]["when"] = "/weather"
    with pytest.raises(PolicyCorruptError):
        Policy.from_dict(v)


def test_22_bad_amount_gt_raises():
    v = json.loads(json.dumps(VALID))
    v["wallet_policy"]["rules"][1]["when"]["amount_gt"] = "cok"
    with pytest.raises(PolicyCorruptError):
        Policy.from_dict(v)
