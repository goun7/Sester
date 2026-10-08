"""pugio_watch_receiver.verify_feed zincir doğrulama testleri (scan10, LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Dış çağrı YOK: saf JSONL zincir doğrulama.
"""
import json
import sys

import pytest

sys.path.insert(0, "bridge_receivers")

from pugio_watch_receiver import BRIDGE_VERSION, GENESIS, _sha, verify_feed


def _evt(prev, seq, agent="a1", host="h1", rule="r1", decision="ALLOW"):
    entry_sha = _sha(f"{prev}|{seq}|2026-10-08|{agent}|{host}|{rule}|{decision}")
    return {
        "type": "watch_event",
        "bridge_version": BRIDGE_VERSION,
        "seq": seq,
        "ts": "2026-10-08",
        "agent": agent,
        "host": host,
        "rule_id": rule,
        "decision": decision,
        "prev_entry_sha": prev,
        "entry_sha": entry_sha,
    }


def _manifest():
    return {
        "type": "watch_manifest",
        "bridge_version": BRIDGE_VERSION,
        "source": "sikke",
    }


def _close(entries, head):
    return {
        "type": "watch_close",
        "bridge_version": BRIDGE_VERSION,
        "entries": entries,
        "watch_head": head,
    }


def _lines(*objs):
    return [json.dumps(o) for o in objs]


# -- geçerli zincir ----------------------------------------------------------------------

def test_valid_single_event_chain():
    e = _evt(GENESIS, 1)
    lines = _lines(_manifest(), e, _close(1, e["entry_sha"]))
    ok, msg = verify_feed(lines)
    assert ok, msg
    assert "akış-SAĞLAM" in msg


def test_valid_three_event_chain():
    e1 = _evt(GENESIS, 1)
    e2 = _evt(e1["entry_sha"], 2)
    e3 = _evt(e2["entry_sha"], 3)
    lines = _lines(_manifest(), e1, e2, e3, _close(3, e3["entry_sha"]))
    ok, msg = verify_feed(lines)
    assert ok, msg
    assert "3 olay" in msg


def test_empty_lines_skipped():
    e = _evt(GENESIS, 1)
    lines = ["", json.dumps(_manifest()), "  ", json.dumps(e),
             "\t", json.dumps(_close(1, e["entry_sha"]))]
    ok, msg = verify_feed(lines)
    assert ok, msg


# -- manifest yollari -----------------------------------------------------------------------

def test_missing_manifest_rejected():
    e = _evt(GENESIS, 1)
    ok, msg = verify_feed(_lines(e, _close(1, e["entry_sha"])))
    assert not ok
    assert "manifest'siz olay" in msg or "manifest/close eksik" in msg


def test_second_manifest_rejected():
    e = _evt(GENESIS, 1)
    lines = _lines(_manifest(), e, _manifest(), _close(1, e["entry_sha"]))
    ok, msg = verify_feed(lines)
    assert not ok
    assert "ikinci manifest" in msg


def test_wrong_source_rejected():
    m = _manifest()
    m["source"] = "baska"
    e = _evt(GENESIS, 1)
    ok, msg = verify_feed(_lines(m, e, _close(1, e["entry_sha"])))
    assert not ok
    assert "DONUK değeriyle uyuşmuyor" in msg


def test_wrong_bridge_version_rejected():
    e = _evt(GENESIS, 1)
    lines = _lines(_manifest(), e, _close(1, e["entry_sha"]))
    bad = list(lines)
    bad[0] = json.dumps({**_manifest(), "bridge_version": 99})
    ok, msg = verify_feed(bad)
    assert not ok
    assert "bridge_version uyuşmuyor" in msg


# -- zincir kopukluk ------------------------------------------------------------------------

def test_broken_prev_hash_rejected():
    e1 = _evt(GENESIS, 1)
    e2 = _evt(e1["entry_sha"], 2)
    # e2'nin prev'ini boz
    e2["prev_entry_sha"] = "f" * 64
    ok, msg = verify_feed(_lines(_manifest(), e1, e2,
                                 _close(2, e2["entry_sha"])))
    assert not ok
    assert "zincir bağı kopuk" in msg


def test_tampered_entry_sha_rejected():
    e1 = _evt(GENESIS, 1)
    e2 = _evt(e1["entry_sha"], 2)
    e2["entry_sha"] = "a" * 64  # sahte hash
    ok, msg = verify_feed(_lines(_manifest(), e1, e2,
                                 _close(2, e2["entry_sha"])))
    assert not ok
    assert "zincir bağı kopuk" in msg


def test_tampered_agent_breaks_chain():
    e1 = _evt(GENESIS, 1)
    e1["agent"] = "diger"  # sha artık uymaz
    ok, msg = verify_feed(_lines(_manifest(), e1, _close(1, e1["entry_sha"])))
    assert not ok
    assert "zincir bağı kopuk" in msg


def test_tampered_decision_breaks_chain():
    e1 = _evt(GENESIS, 1, decision="ALLOW")
    e1["decision"] = "DENY"  # sha artık uymaz
    ok, msg = verify_feed(_lines(_manifest(), e1, _close(1, e1["entry_sha"])))
    assert not ok
    assert "zincir bağı kopuk" in msg


# -- close yollari ----------------------------------------------------------------------------

def test_close_count_mismatch_rejected():
    e1 = _evt(GENESIS, 1)
    ok, msg = verify_feed(_lines(_manifest(), e1, _close(99, e1["entry_sha"])))
    assert not ok
    assert "≠ olay-sayısı" in msg


def test_close_head_mismatch_rejected():
    e1 = _evt(GENESIS, 1)
    ok, msg = verify_feed(_lines(_manifest(), e1, _close(1, "b" * 64)))
    assert not ok
    assert "watch_head uyuşmuyor" in msg


def test_second_close_rejected():
    e1 = _evt(GENESIS, 1)
    c = _close(1, e1["entry_sha"])
    ok, msg = verify_feed(_lines(_manifest(), e1, c, c))
    assert not ok
    assert "ikinci close" in msg


def test_event_after_close_rejected():
    e1 = _evt(GENESIS, 1)
    e2 = _evt(e1["entry_sha"], 2)
    c = _close(1, e1["entry_sha"])
    ok, msg = verify_feed(_lines(_manifest(), e1, c, e2))
    assert not ok
    assert "close'tan sonra olay" in msg


def test_missing_close_rejected():
    e1 = _evt(GENESIS, 1)
    ok, msg = verify_feed(_lines(_manifest(), e1))
    assert not ok
    assert "manifest/close eksik" in msg


def test_empty_feed_rejected():
    ok, msg = verify_feed([])
    assert not ok
    assert "eksik" in msg


# -- format hatalari ----------------------------------------------------------------------------

def test_malformed_json_rejected():
    ok, msg = verify_feed(["{bukan json"])
    assert not ok
    assert "JSON bozuk" in msg


def test_unknown_type_rejected():
    ok, msg = verify_feed(_lines({"type": "bilinear", "bridge_version": BRIDGE_VERSION}))
    assert not ok
    assert "bilinmeyen tip" in msg


# -- sha yardimcisi ------------------------------------------------------------------------------

def test_sha_deterministic():
    assert _sha("test") == _sha("test")


def test_sha_differs_on_input():
    assert _sha("a") != _sha("b")


def test_genesis_is_64_zeros():
    assert GENESIS == "0" * 64
    assert len(GENESIS) == 64
