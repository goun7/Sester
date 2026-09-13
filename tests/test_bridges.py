"""SESTER bridges testleri — K1 Tamga-çıpası + K2 Veridict-claim'leri."""

from __future__ import annotations

import hashlib
import json

import pytest

from sester.bridges import (BRIDGE_VERSION, tamga_anchor, tamga_anchor_json,
                            veridict_claims, veridict_claims_json, verify_tamga_anchor)
from sester.evidence import produce_bundle
from sester.ledger import Ledger


@pytest.fixture()
def led(tmp_path):
    l = Ledger(tmp_path / "br.sqlite3", secret="br-secret")
    l.append("charge_receipt", "a1", "/weather", 0.05, payload={"nonce": "n1"})
    l.append("charge_receipt", "a1", "/weather", 0.05, payload={"nonce": "n2"})
    l.append("permission_decision", "a1", "/weather", 0.0,
             payload={"decision": "deny", "rule_id": "quota_exceeded"})
    l.append("permission_decision", "a1", "/weather", 0.0,
             payload={"decision": "deny", "rule_id": "replay"})
    l.append("charge_receipt", "a2", "/weather", 0.10, payload={"nonce": "m1"})
    yield l
    l.close()


# ---------- K1 · Tamga çıpası ----------

def test_55_tamga_anchor_fields_and_deterministic_id(led):
    b = produce_bundle(led, agent_id="a1")
    a1 = tamga_anchor(b, agent_label="f1-telemetri")
    a2 = tamga_anchor(produce_bundle(led, agent_id="a1"), agent_label="f1-telemetri")
    assert a1["type"] == "external_anchor" and a1["source"] == "sikke"
    assert a1["anchor_id"] == a2["anchor_id"]  # deterministik (generated hariç alanlar)
    assert len(a1["anchor_id"]) == 32
    # id bağları: sha256(head|merkle|count)[:32]
    expect = hashlib.sha256(
        f"{b['head']}|{b['merkle_root']}|{b['event_count']}".encode()).hexdigest()[:32]
    assert a1["anchor_id"] == expect


def test_56_tamga_anchor_json_is_one_deterministic_line(led):
    b = produce_bundle(led, agent_id="a1")
    j1 = tamga_anchor_json(b, agent_label="x")
    j2 = tamga_anchor_json(b, agent_label="x")
    assert j1 == j2
    assert "\n" not in j1  # JSONL tek-satır


def test_57_tamga_anchor_verifies_and_detects_tamper(led):
    b = produce_bundle(led, agent_id="a1")
    a = tamga_anchor(b)
    ok, msg = verify_tamga_anchor(a)
    assert ok, msg
    a["event_count"] += 1  # olay-sayısı şişirildi
    ok, msg = verify_tamga_anchor(a)
    assert not ok and "kopuk" in msg


def test_58_tamga_anchor_rejects_wrong_source():
    ok, msg = verify_tamga_anchor({"type": "external_anchor", "source": "baskasi",
                                   "head": "0", "merkle_root": "0", "event_count": 0,
                                   "anchor_id": "0"})
    assert not ok


def test_59_anchor_segments_are_agent_isolated(led):
    a1 = tamga_anchor(produce_bundle(led, agent_id="a1"))
    a2 = tamga_anchor(produce_bundle(led, agent_id="a2"))
    assert a1["anchor_id"] != a2["anchor_id"]


# ---------- K2 · Veridict claim'leri ----------

def test_60_veridict_claims_count_events(led):
    b = produce_bundle(led, agent_id="a1")
    c = veridict_claims(b, task_id="s1-dogfood")
    summaries = [x["summary"] for x in c["claims"]]
    assert any("1 aşım-engeli" in s for s in summaries)   # quota_exceeded × 1
    assert any("1 tekrar-nonce reddi" in s for s in summaries)  # replay × 1
    assert c["source"] == "sikke"


def test_61_veridict_claim_id_rule():
    """Veridict kuralı: sha256(task_id|summary|verifiability)[:16]."""
    empty_bundle = {"head": "h", "merkle_root": "m", "event_count": 0, "events": []}
    cl = veridict_claims(empty_bundle, task_id="t1")["claims"][0]
    expect = hashlib.sha256(f"t1|{cl['summary']}|reproducible".encode()).hexdigest()[:16]
    assert cl["claim_id"] == expect
    assert cl["verifiability"] == "reproducible"


def test_62_veridict_claims_carry_evidence_pointers(led):
    b = produce_bundle(led, agent_id="a2")
    c = veridict_claims(b)["claims"]
    for x in c:
        ev = x["evidence"]
        assert ev["kind"] == "pugio_evidence_bundle"
        assert ev["head"] == b["head"] and ev["merkle_root"] == b["merkle_root"]


def test_63_claims_json_roundtrip(led):
    b = produce_bundle(led, agent_id="a1")
    parsed = json.loads(veridict_claims_json(b))
    assert parsed["bridge_version"] == BRIDGE_VERSION
    assert len(parsed["claims"]) == 3
