"""PUGIO evidence testleri — 81-kanıt-köprüsü: üret + harici-doğrula + inkâr-saldırısı."""

from __future__ import annotations

import json

import pytest

from pugio.evidence import GENESIS, bundle_json, produce_bundle, proof_hash, verify_bundle
from pugio.ledger import Ledger


@pytest.fixture()
def led(tmp_path):
    l = Ledger(tmp_path / "ev.sqlite3", secret="ev-secret")
    l.append("charge_receipt", "a1", "/weather", 0.05, payload={"nonce": "n1"})
    l.append("charge_receipt", "a1", "/weather", 0.05, payload={"nonce": "n2"})
    l.append("permission_decision", "a1", "/weather", 0.0,
             payload={"decision": "deny", "rule_id": "quota_exceeded"})
    l.append("charge_receipt", "a2", "/weather", 0.10, payload={"nonce": "m1"})
    yield l
    l.close()


def test_48_bundle_produces_and_verifies(led):
    b = produce_bundle(led, agent_id="a1")
    assert b["event_count"] == 3
    ok, msg = verify_bundle(b)
    assert ok, msg
    assert b["events"][0]["prev_proof"] == GENESIS


def test_49_bundle_is_externally_verifiable_with_plain_sha256(led):
    """Alıcı-simülasyonu: kütüphanesiz, pür hashlib ile doğrulama."""
    b = produce_bundle(led, agent_id="a2")
    raw = json.loads(bundle_json(b))
    import hashlib
    prev = GENESIS
    for ev in raw["events"]:
        canonical = "|".join([
            f"{ev['ts']:.6f}", ev["event_type"], ev["agent_id"], ev["host"],
            f"{ev['amount']:.6f}", ev["payload"], prev,
        ])
        h = hashlib.sha256(canonical.encode()).hexdigest()
        assert h == ev["proof"]
        prev = h
    assert raw["head"] == prev


def test_50_tampered_amount_detected(led):
    b = produce_bundle(led, agent_id="a1")
    b["events"][1]["amount"] = 0.01  # işlem-inkârı: tutarı küçült
    ok, msg = verify_bundle(b)
    assert not ok and "proof-uyuşmazlığı" in msg


def test_51_dropped_event_breaks_link(led):
    b = produce_bundle(led, agent_id="a1")
    b["events"].pop(1)  # orta olay silindi
    ok, msg = verify_bundle(b)
    assert not ok and ("seq-atlaması" in msg or "zincir-kopması" in msg)


def test_52_wrong_merkle_root_detected(led):
    b = produce_bundle(led, agent_id="a1")
    b["merkle_root"] = "f" * 64
    ok, msg = verify_bundle(b)
    assert not ok and "merkle" in msg


def test_53_agent_filter_isolates_segments(led):
    b1 = produce_bundle(led, agent_id="a1")
    b2 = produce_bundle(led, agent_id="a2")
    assert b1["event_count"] == 3 and b2["event_count"] == 1
    assert b1["head"] != b2["head"]
    assert verify_bundle(b1)[0] and verify_bundle(b2)[0]


def test_54_empty_segment_verifies_with_genesis_head(led):
    b = produce_bundle(led, agent_id="yok-boyle-ajan")
    assert b["event_count"] == 0 and b["head"] == GENESIS
    assert verify_bundle(b)[0]
