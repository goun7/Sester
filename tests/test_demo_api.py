"""SESTER demo_api testleri — policy_guard + _PolicyState fail-closed.

Kapsanan modül: sester/demo_api.py (policy_guard, _PolicyState,
_agent_of, _amount_of).

Politika-DSL-v0 §4 canlı-semantiği: kural dosyası bozuksa → harcama
durmaz, tüm istekler reddedilir (DenyAll). Bu, ödeme katmanı için
fail-closed'tür: yanlış açık (fail-open) paradoks olarak maliyetlidır.
"""

from __future__ import annotations

import json
import os
import time
import unittest
from pathlib import Path
from unittest import mock

from sester import demo_api
from sester.demo_api import _PolicyState, _agent_of, _amount_of, policy_guard
from sester.ledger import Ledger
from sester.policy import DenyAll, Policy


class TestPolicyStateFailClosed(unittest.TestCase):
    """_PolicyState: bozuk/eksik politika → DenyAll (fail-closed)."""

    def test_missing_policy_yields_denyall(self):
        with mock.patch.object(demo_api, "POLICY_PATH",
                               Path("/nonexistent/policy.json")):
            st = _PolicyState()
            # bozuk/eksik politika → DenyAll (Policy degil, DenyAll)
            self.assertIsInstance(st.engine, DenyAll)

    def test_valid_policy_loads_policy(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"wallet_policy": {"id": "t1", "defaults": {"per_request_max": 1.0, "daily_max": 10.0}, "rules": []}}, f)
            path = Path(f.name)
        try:
            with mock.patch.object(demo_api, "POLICY_PATH", path):
                st = _PolicyState()
                self.assertIsInstance(st.engine, Policy)
        finally:
            path.unlink(missing_ok=True)

    def test_current_reloads_on_mtime_change(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"wallet_policy": {"id": "t1", "defaults": {"per_request_max": 1.0, "daily_max": 10.0}, "rules": []}}, f)
            path = Path(f.name)
        try:
            with mock.patch.object(demo_api, "POLICY_PATH", path):
                st = _PolicyState()
                first = st.current()
                self.assertIsInstance(first, Policy)
                # mtime degisince yeniden yuklenmeli
                time.sleep(0.01)
                with open(path, "w") as f2:
                    json.dump({"wallet_policy": {"id": "t2", "defaults": {"per_request_max": 2.0, "daily_max": 20.0}, "rules": []}}, f2)
                os.utime(path, None)
                second = st.current()
                self.assertIsNot(first, second)
                self.assertEqual(second.per_request_max, 2.0)
        finally:
            path.unlink(missing_ok=True)


class TestPolicyGuard(unittest.TestCase):
    """policy_guard: per_request_max kapısı + escalate istisnası."""

    def setUp(self):
        self.tmp_ledger = Ledger(":memory:", secret="x" * 40)
        p = mock.patch.object(demo_api, "ledger", self.tmp_ledger)
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp_ledger.close()

    def test_denyall_rejects_everything(self):
        """Politika yok → DenyAll → her istek reddedilir (fail-closed)."""
        with mock.patch.object(demo_api, "POLICY_PATH",
                               Path("/nonexistent/policy.json")):
            # policy_guard modul-level _policy_state kullanir; reset
            demo_api._policy_state = _PolicyState()
            verdict, rule = policy_guard("agent-a", "/svc", 0.01)
        self.assertEqual(verdict, "deny")
        self.assertIn("per_request_max", rule)

    def test_decision_recorded_to_ledger(self):
        """Her karar ledger'a yazılır — permission_decision (allow AND deny)."""
        with mock.patch.object(demo_api, "POLICY_PATH",
                               Path("/nonexistent/policy.json")):
            demo_api._policy_state = _PolicyState()
            policy_guard("agent-a", "/svc", 0.01)
        events = self.tmp_ledger.export_events()
        decisions = [e for e in events
                     if e.get("event_type") == "permission_decision"]
        self.assertEqual(len(decisions), 1)
        payload = json.loads(decisions[0]["payload"])
        self.assertEqual(payload["decision"], "deny")
        self.assertIn("rule_id", payload)


class TestAgentOf(unittest.TestCase):
    """_agent_of: ödeme-başlığından ajan-kimliği çıkarımı."""

    def test_empty_payment_returns_none(self):
        self.assertIsNone(_agent_of("", "/svc"))

    def test_unknown_scheme_returns_none(self):
        self.assertIsNone(_agent_of("bogus-scheme xyz", "/svc"))

    def test_exact_scheme_returns_none_unsupported(self):
        # _agent_of sadece Sester-EVM ve pugio0 destekler; exact yok
        self.assertIsNone(_agent_of("exact my-agent-token", "/svc"))

    def test_pugio0_scheme_uses_label_as_agent(self):
        # "pugio0 <label>:..." → label
        agent = _agent_of("pugio0 agent-a:extra", "/svc")
        self.assertEqual(agent, "agent-a")

    def test_pugio0_empty_label_returns_none(self):
        self.assertIsNone(_agent_of("pugio0 ", "/svc"))

    def test_agent_depends_on_resource_for_evm(self):
        """EVM imza kaynağa-bağlıdır — resource olmadan doğrulama imkânsız."""
        agent = _agent_of("Sester-EVM 0xabc", "")
        self.assertIsNone(agent)


class TestAmountOf(unittest.TestCase):
    """_amount_of: ödeme-başlığından tutar çıkarımı."""

    def test_empty_returns_none(self):
        self.assertIsNone(_amount_of(""))

    def test_unknown_scheme_returns_none(self):
        self.assertIsNone(_amount_of("bogus 123"))


if __name__ == "__main__":
    unittest.main()
