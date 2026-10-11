"""sester.policy_signed.SignedPolicyVault._activate +
sester.demo_api._PolicyState._stat/_load/current dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — tmp_path politika-dosyalari + monkeypatch POLICY_PATH
(gercek dosya-sistemi disinda HICBIR sey degismez).
"""
import json
import os

import pytest

from sester.demo_api import _PolicyState
from sester.policy import Policy, PolicyCorruptError
from sester.policy_signed import SignedPolicyVault
import sester.demo_api as demo_api

GOOD = {"id": "p1", "defaults": {"per_request_max": 0.5, "daily_max": 25.0},
        "rules": []}


def make_vault(now=None):
    return SignedPolicyVault(resolve_key=lambda iss, kid: b"k", now=now)


# == SignedPolicyVault._activate =================================================================

class TestActivate:
    def test_sets_current_policy(self):
        v = make_vault()
        v._activate(GOOD, {"signed_at": 1.0, "signer": "s1"}, "initial",
                    immediate=True)
        assert isinstance(v.current, Policy)

    def test_sets_current_body(self):
        v = make_vault()
        v._activate(GOOD, {"signed_at": 1.0, "signer": "s1"}, "initial",
                    immediate=True)
        assert v.current_body == GOOD

    def test_appends_history_once(self):
        v = make_vault()
        v._activate(GOOD, {"signed_at": 1.0, "signer": "s1"}, "initial",
                    immediate=True)
        assert len(v.history) == 1

    def test_initial_state_empty(self):
        """ORTAM: fresh vault — current/body/history bos."""
        v = make_vault()
        assert v.current is None
        assert v.current_body is None
        assert v.history == []

    def test_history_entry_fields(self):
        v = make_vault()
        v._activate(GOOD, {"signed_at": 1.0, "signer": "s1"}, "initial",
                    immediate=True)
        h = v.history[0]
        assert set(h) >= {"at", "kind", "signed_at", "signer", "policy_id"}
        assert h["signed_at"] == 1.0
        assert h["signer"] == "s1"
        assert h["policy_id"] == "p1"

    def test_at_is_now(self):
        """ORTAM: at=self._now() — now-inject ile test."""
        v = make_vault(now=lambda: 999.0)
        v._activate(GOOD, {"signed_at": 1.0, "signer": "s"}, "k", immediate=True)
        assert v.history[0]["at"] == 999.0

    def test_default_now_is_time_time(self):
        import time
        v = make_vault()
        v._activate(GOOD, {"signed_at": 1.0, "signer": "s"}, "k", immediate=True)
        assert abs(v.history[0]["at"] - time.time()) < 5.0

    @pytest.mark.parametrize("kind", ["initial", "rotate", "hotfix", "x"])
    def test_kind_when_immediate(self, kind):
        """ORTAM: immediate=True -> kind birebir."""
        v = make_vault()
        v._activate(GOOD, {"signed_at": 1.0, "signer": "s"}, kind, immediate=True)
        assert v.history[0]["kind"] == kind

    @pytest.mark.parametrize("kind", ["initial", "rotate", "hotfix"])
    def test_kind_pending_when_not_immediate(self, kind):
        """ORTAM-OGRENDI: immediate=False -> kind HER ZAMAN 'pending'
        (kind-if-immediate-else-pending)."""
        v = make_vault()
        v._activate(GOOD, {"signed_at": 1.0, "signer": "s"}, kind, immediate=False)
        assert v.history[0]["kind"] == "pending"

    def test_current_replaced(self):
        v = make_vault()
        v._activate(GOOD, {"signed_at": 1.0, "signer": "s"}, "a", immediate=True)
        first = v.current
        v._activate({**GOOD, "id": "p2"}, {"signed_at": 2.0, "signer": "s2"},
                    "b", immediate=True)
        assert v.current is not first
        assert v.current_body["id"] == "p2"

    def test_history_accumulates(self):
        v = make_vault()
        for i in range(3):
            v._activate({**GOOD, "id": f"p{i}"}, {"signed_at": float(i)},
                        "k", immediate=True)
        assert [h["policy_id"] for h in v.history] == ["p0", "p1", "p2"]

    def test_env_missing_keys_give_none(self):
        """ORTAM: env.get('signed_at')/get('signer') — YOKSA None."""
        v = make_vault()
        v._activate(GOOD, {"other": 1}, "k", immediate=True)
        assert v.history[0]["signed_at"] is None
        assert v.history[0]["signer"] is None

    def test_body_missing_id_propagates(self):
        """ORTAM: Policy.from_dict 'id' ZORUNLU — PolicyCorruptError YAYILIR."""
        v = make_vault()
        bad = {"defaults": GOOD["defaults"], "rules": []}
        with pytest.raises(PolicyCorruptError):
            v._activate(bad, {"a": 1}, "k", immediate=True)

    def test_body_missing_defaults_propagates(self):
        v = make_vault()
        with pytest.raises(PolicyCorruptError):
            v._activate({"id": "x"}, {"a": 1}, "k", immediate=True)

    def test_body_not_dict_propagates(self):
        """ORTAM: from_dict({'wallet_policy': 'str'}) -> corrupt."""
        v = make_vault()
        with pytest.raises(PolicyCorruptError):
            v._activate("not-a-dict", {"a": 1}, "k", immediate=True)

    def test_no_side_effect_on_pending_fields(self):
        """ORTAM: _activate pending_body/pending_effective_at DOKUNMAZ
        (onlari ayri apply-pending yolu set-eder)."""
        v = make_vault()
        v._activate(GOOD, {"signed_at": 1.0, "signer": "s"}, "k", immediate=True)
        assert v.pending_body is None
        assert v.pending_effective_at is None
        assert v.pending_signed_at is None

    def test_multiple_activations_independent_history(self):
        v1 = make_vault()
        v2 = make_vault()
        v1._activate(GOOD, {"signed_at": 1.0, "signer": "s"}, "k", immediate=True)
        assert len(v2.history) == 0
        assert len(v1.history) == 1


# == _PolicyState._stat ==========================================================================

class TestStat:
    def test_returns_float_for_existing(self, tmp_path):
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": GOOD}), encoding="utf-8")
        demo_api.POLICY_PATH = p
        assert isinstance(_PolicyState._stat(), float)

    def test_missing_file_returns_none(self, tmp_path):
        demo_api.POLICY_PATH = tmp_path / "nope.json"
        assert _PolicyState._stat() is None

    def test_missing_dir_returns_none(self, tmp_path):
        demo_api.POLICY_PATH = tmp_path / "nodir" / "x.json"
        assert _PolicyState._stat() is None

    def test_enoent_returns_none(self, tmp_path):
        """ORTAM: OSError (ENOENT dahil) yakalanir -> None."""
        demo_api.POLICY_PATH = tmp_path / "nodir" / "deep" / "x.json"
        assert _PolicyState._stat() is None

    def test_mtime_changes_after_write(self, tmp_path):
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": GOOD}), encoding="utf-8")
        demo_api.POLICY_PATH = p
        a = _PolicyState._stat()
        os.utime(p, (1, 1))
        assert _PolicyState._stat() == 1.0
        assert a != 1.0

    def test_static_method(self):
        """ORTAM: @staticmethod — instance'siz cagrilabilir."""
        assert callable(_PolicyState._stat)


# == _PolicyState._load ==========================================================================

class TestLoad:
    def test_valid_policy_returns_policy(self, tmp_path):
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": GOOD}), encoding="utf-8")
        demo_api.POLICY_PATH = p
        assert isinstance(_PolicyState._load(), Policy)

    def test_missing_file_returns_denyall(self, tmp_path):
        """ORTAM: Policy.load -> PolicyCorruptError -> except -> DenyAll."""
        demo_api.POLICY_PATH = tmp_path / "nope.json"
        from sester.policy import DenyAll
        assert isinstance(_PolicyState._load(), DenyAll)

    def test_corrupt_json_returns_denyall(self, tmp_path):
        demo_api.POLICY_PATH = tmp_path / "pol.json"
        demo_api.POLICY_PATH.write_text("{ bu json degil ", encoding="utf-8")
        from sester.policy import DenyAll
        assert isinstance(_PolicyState._load(), DenyAll)

    def test_not_json_object_returns_denyall(self, tmp_path):
        """ORTAM: '[]' -> from_dict dict-degil -> DenyAll."""
        p = tmp_path / "pol.json"
        p.write_text("[]", encoding="utf-8")
        demo_api.POLICY_PATH = p
        from sester.policy import DenyAll
        assert isinstance(_PolicyState._load(), DenyAll)

    def test_missing_wallet_policy_key_returns_denyall(self, tmp_path):
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"other": GOOD}), encoding="utf-8")
        demo_api.POLICY_PATH = p
        from sester.policy import DenyAll
        assert isinstance(_PolicyState._load(), DenyAll)

    def test_missing_id_returns_denyall(self, tmp_path):
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": {"defaults": GOOD["defaults"]}}),
                     encoding="utf-8")
        demo_api.POLICY_PATH = p
        from sester.policy import DenyAll
        assert isinstance(_PolicyState._load(), DenyAll)

    def test_negative_limits_returns_denyall(self, tmp_path):
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": {
            "id": "x", "defaults": {"per_request_max": -1, "daily_max": 5}}}),
            encoding="utf-8")
        demo_api.POLICY_PATH = p
        from sester.policy import DenyAll
        assert isinstance(_PolicyState._load(), DenyAll)

    def test_static_method(self):
        assert callable(_PolicyState._load)


# == _PolicyState constructor / current =========================================================

class TestPolicyStateCurrent:
    def test_constructor_sets_mtime_and_engine(self, tmp_path):
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": GOOD}), encoding="utf-8")
        demo_api.POLICY_PATH = p
        st = _PolicyState()
        assert st.mtime is not None
        assert isinstance(st.engine, Policy)

    def test_constructor_missing_file(self, tmp_path):
        demo_api.POLICY_PATH = tmp_path / "nope.json"
        st = _PolicyState()
        assert st.mtime is None
        from sester.policy import DenyAll
        assert isinstance(st.engine, DenyAll)

    def test_current_returns_engine(self, tmp_path):
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": GOOD}), encoding="utf-8")
        demo_api.POLICY_PATH = p
        st = _PolicyState()
        assert st.current() is st.engine

    def test_current_no_change_same_object(self, tmp_path):
        """ORTAM: mtime ayniysa engine RETURN'lenir (yeniden-yukleme YOK)."""
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": GOOD}), encoding="utf-8")
        demo_api.POLICY_PATH = p
        st = _PolicyState()
        assert st.current() is st.current()

    def test_current_reloads_on_mtime_change(self, tmp_path):
        """ORTAM: mtime != self.mtime -> yeniden yukle + engine guncelle."""
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": GOOD}), encoding="utf-8")
        demo_api.POLICY_PATH = p
        st = _PolicyState()
        first = st.engine
        p.write_text(json.dumps({"wallet_policy": {**GOOD, "id": "p9"}}),
                     encoding="utf-8")
        os.utime(p, (1, 1))
        second = st.current()
        assert first is not second
        assert isinstance(second, Policy)

    def test_current_updates_mtime(self, tmp_path):
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": GOOD}), encoding="utf-8")
        demo_api.POLICY_PATH = p
        st = _PolicyState()
        os.utime(p, (5, 5))
        st.current()
        assert st.mtime == 5.0

    def test_current_falls_back_to_denyall_on_corruption(self, tmp_path):
        """ORTAM-ANATOMI: gecerliyken-sonra-bozulan dosya -> DenyAll (fail-closed)."""
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": GOOD}), encoding="utf-8")
        demo_api.POLICY_PATH = p
        st = _PolicyState()
        assert isinstance(st.engine, Policy)
        p.write_text("{ bozuk ", encoding="utf-8")
        os.utime(p, (9, 9))
        from sester.policy import DenyAll
        assert isinstance(st.current(), DenyAll)

    def test_current_stays_denyall_when_file_disappears(self, tmp_path):
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": GOOD}), encoding="utf-8")
        demo_api.POLICY_PATH = p
        st = _PolicyState()
        p.unlink()
        from sester.policy import DenyAll
        assert isinstance(st.current(), DenyAll)

    def test_current_deleted_then_restored(self, tmp_path):
        p = tmp_path / "pol.json"
        p.write_text(json.dumps({"wallet_policy": GOOD}), encoding="utf-8")
        demo_api.POLICY_PATH = p
        st = _PolicyState()
        p.unlink()
        from sester.policy import DenyAll
        assert isinstance(st.current(), DenyAll)
        p.write_text(json.dumps({"wallet_policy": GOOD}), encoding="utf-8")
        os.utime(p, (3, 3))
        assert isinstance(st.current(), Policy)
