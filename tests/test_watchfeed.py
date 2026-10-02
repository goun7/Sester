"""SESTER watch-feed tests — K3 üreticisi + alıcı-tarafı doğrulama.

Kapsanan modül: sester/watchfeed.py (produce_watch_feed, watch_feed_jsonl,
verify_watch_feed). Bu modül x402 #2332'nin doğrudan uygulamasıdır:
kanıt-bundle'ı hash-chain'e gömülür ve alıcı tarafı pür sha256 ile
yeniden-hash eder. Her uyuşmazlık explicit RED (fail-loud).
"""

from __future__ import annotations

import copy
import json
import unittest

from sester.ledger import Ledger
from sester.watchfeed import (
    BRIDGE_VERSION,
    GENESIS,
    entry_sha,
    produce_watch_feed,
    verify_watch_feed,
    watch_feed_jsonl,
)

SECRET = "test-secret-0000000000000000000000000000000000000000"


def _bundle(led: Ledger) -> dict:
    """Ledger'dan K0-üslubu bir kanıt-bundle dict'i üret."""
    return {
        "head": "abc123head",
        "merkle_root": "deadbeef",
        "event_count": 2,
        "events": led.export_events(),
    }


def _perm_events(led: Ledger) -> None:
    led.append("permission_decision", agent_id="agent-a", host="svc-one",
               payload={"rule_id": "r1", "decision": "allow"})
    led.append("permission_decision", agent_id="agent-b", host="svc-two",
               payload={"rule_id": "r2", "decision": "deny"})


class TestEntrySha(unittest.TestCase):
    """entry_sha: K0 §6 bağ-formülü — alıcı tarafı birebiriyle uyuşur."""

    def test_genesis_first_entry(self):
        sha = entry_sha(GENESIS, 1, 1.5, "a", "h", "r1", "allow")
        self.assertEqual(len(sha), 64)

    def test_formula_is_pure_sha256_of_canonical_line(self):
        import hashlib
        expected = hashlib.sha256(
            f"{GENESIS}|1|1.500000|a|h|r1|allow".encode()
        ).hexdigest()
        self.assertEqual(entry_sha(GENESIS, 1, 1.5, "a", "h", "r1", "allow"),
                         expected)

    def test_different_decision_different_hash(self):
        allow = entry_sha(GENESIS, 1, 1.0, "a", "h", "r", "allow")
        deny = entry_sha(GENESIS, 1, 1.0, "a", "h", "r", "deny")
        self.assertNotEqual(allow, deny)

    def test_ts_fractional_digits_affect_hash(self):
        # ts 6 ondalık basamakla formatlanır — 1.5 ve 1.500000 aynı,
        # ama 1.500001 farklı olmalı
        a = entry_sha(GENESIS, 1, 1.5, "a", "h", "r", "allow")
        b = entry_sha(GENESIS, 1, 1.500001, "a", "h", "r", "allow")
        self.assertNotEqual(a, b)


class TestProduceWatchFeed(unittest.TestCase):
    """Üretici: manifest + watch_event* + close, deterministik."""

    def test_shape_manifest_events_close(self):
        led = Ledger(":memory:", secret=SECRET)
        _perm_events(led)
        lines = produce_watch_feed(_bundle(led), watcher_id="w1")
        self.assertEqual(lines[0]["type"], "watch_manifest")
        self.assertEqual(lines[-1]["type"], "watch_close")
        self.assertEqual([l["type"] for l in lines[1:-1]],
                         ["watch_event", "watch_event"])

    def test_manifest_fields(self):
        led = Ledger(":memory:", secret=SECRET)
        _perm_events(led)
        b = _bundle(led)
        lines = produce_watch_feed(b, watcher_id="w1")
        m = lines[0]
        self.assertEqual(m["bridge_version"], BRIDGE_VERSION)
        self.assertEqual(m["watcher_id"], "w1")
        self.assertEqual(m["bundle_head"], "abc123head")
        self.assertEqual(m["bundle_merkle_root"], "deadbeef")
        self.assertEqual(m["bundle_event_count"], 2)

    def test_only_permission_decisions_become_events(self):
        """permission_decision OLMAYAN olaylar watch-feed'e düşmez."""
        led = Ledger(":memory:", secret=SECRET)
        led.append("charge_receipt", agent_id="a", host="h",
                   amount=1.0, payload={"amount": "1"})
        _perm_events(led)
        lines = produce_watch_feed(_bundle(led), watcher_id="w1")
        events = [l for l in lines if l["type"] == "watch_event"]
        self.assertEqual(len(events), 2)

    def test_chain_starts_at_genesis_and_links(self):
        led = Ledger(":memory:", secret=SECRET)
        _perm_events(led)
        lines = produce_watch_feed(_bundle(led), watcher_id="w1")
        events = [l for l in lines if l["type"] == "watch_event"]
        self.assertEqual(events[0]["prev_entry_sha"], GENESIS)
        self.assertEqual(events[1]["prev_entry_sha"], events[0]["entry_sha"])
        # her entry_sha formülle birebir hesaplanabilir
        prev = GENESIS
        for i, e in enumerate(events, start=1):
            calc = entry_sha(prev, i, float(e["ts"]), e["agent"], e["host"],
                             e["rule_id"], e["decision"])
            self.assertEqual(calc, e["entry_sha"])
            prev = calc

    def test_close_carries_head_and_count(self):
        led = Ledger(":memory:", secret=SECRET)
        _perm_events(led)
        lines = produce_watch_feed(_bundle(led), watcher_id="w1")
        events = [l for l in lines if l["type"] == "watch_event"]
        close = lines[-1]
        self.assertEqual(close["entries"], 2)
        self.assertEqual(close["watch_head"], events[-1]["entry_sha"])

    def test_deterministic_two_runs_identical(self):
        led = Ledger(":memory:", secret=SECRET)
        _perm_events(led)
        b = _bundle(led)
        a1 = produce_watch_feed(b, watcher_id="w1")
        a2 = produce_watch_feed(b, watcher_id="w1")
        self.assertEqual(a1, a2)

    def test_zero_decisions_yields_manifest_plus_close_only(self):
        b = {"head": "h", "merkle_root": "m", "event_count": 0, "events": []}
        lines = produce_watch_feed(b, watcher_id="w1")
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["type"], "watch_manifest")
        self.assertEqual(lines[1]["type"], "watch_close")
        self.assertEqual(lines[1]["entries"], 0)
        self.assertEqual(lines[1]["watch_head"], GENESIS)

    def test_jsonl_roundtrip(self):
        led = Ledger(":memory:", secret=SECRET)
        _perm_events(led)
        text = watch_feed_jsonl(_bundle(led), watcher_id="w1")
        lines = [json.loads(l) for l in text.split("\n")]
        self.assertEqual(len(lines), 4)
        ok, _msg = verify_watch_feed(lines)
        self.assertTrue(ok)


class TestVerifyWatchFeed(unittest.TestCase):
    """Alıcı çekirdeği — pür sha256, her uyuşmazlık explicit RED."""

    def _lines(self, **kw):
        led = Ledger(":memory:", secret=SECRET)
        _perm_events(led)
        lines = produce_watch_feed(_bundle(led), watcher_id="w1")
        led.close()
        return lines

    def test_happy_path(self):
        ok, msg = verify_watch_feed(self._lines())
        self.assertTrue(ok)
        self.assertIn("SAĞLAM", msg)

    def test_empty_stream_rejected(self):
        ok, msg = verify_watch_feed([])
        self.assertFalse(ok)
        self.assertIn("boş", msg)

    def test_missing_manifest_rejected(self):
        lines = self._lines()[1:]
        ok, msg = verify_watch_feed(lines)
        self.assertFalse(ok)
        self.assertIn("manifest değil", msg)

    def test_wrong_bridge_version_rejected(self):
        lines = copy.deepcopy(self._lines())
        lines[0]["bridge_version"] = 999
        ok, msg = verify_watch_feed(lines)
        self.assertFalse(ok)
        self.assertIn("bridge_version", msg)

    def test_tampered_decision_rejected(self):
        """#2332 çekirdeği: veri-değişikliği entry_sha'yı bozar."""
        lines = copy.deepcopy(self._lines())
        ev = [l for l in lines if l["type"] == "watch_event"][0]
        ev["decision"] = "allow" if ev["decision"] == "deny" else "deny"
        ok, msg = verify_watch_feed(lines)
        self.assertFalse(ok)
        self.assertIn("entry_sha uyuşmazlığı", msg)

    def test_tampered_host_rejected(self):
        lines = copy.deepcopy(self._lines())
        ev = [l for l in lines if l["type"] == "watch_event"][0]
        ev["host"] = "evil.example"
        ok, msg = verify_watch_feed(lines)
        self.assertFalse(ok)
        self.assertIn("entry_sha uyuşmazlığı", msg)

    def test_broken_seq_rejected(self):
        lines = copy.deepcopy(self._lines())
        evs = [l for l in lines if l["type"] == "watch_event"]
        evs[1]["seq"] = 99
        ok, msg = verify_watch_feed(lines)
        self.assertFalse(ok)
        self.assertIn("seq süreksizliği", msg)

    def test_broken_prev_link_rejected(self):
        lines = copy.deepcopy(self._lines())
        evs = [l for l in lines if l["type"] == "watch_event"]
        evs[1]["prev_entry_sha"] = "f" * 64
        ok, msg = verify_watch_feed(lines)
        self.assertFalse(ok)
        self.assertIn("prev_entry_sha kopuk", msg)

    def test_missing_close_rejected(self):
        lines = self._lines()[:-1]
        ok, msg = verify_watch_feed(lines)
        self.assertFalse(ok)
        self.assertIn("watch_close yok", msg)

    def test_close_count_mismatch_rejected(self):
        lines = copy.deepcopy(self._lines())
        lines[-1]["entries"] = 99
        ok, msg = verify_watch_feed(lines)
        self.assertFalse(ok)
        self.assertIn("close.entries", msg)

    def test_close_head_mismatch_rejected(self):
        lines = copy.deepcopy(self._lines())
        lines[-1]["watch_head"] = "e" * 64
        ok, msg = verify_watch_feed(lines)
        self.assertFalse(ok)
        self.assertIn("watch_head", msg)

    def test_unknown_line_type_rejected(self):
        lines = self._lines()
        lines.insert(1, {"type": "watch_evil"})
        ok, msg = verify_watch_feed(lines)
        self.assertFalse(ok)
        self.assertIn("beklenmeyen satır-tipi", msg)


if __name__ == "__main__":
    unittest.main()
