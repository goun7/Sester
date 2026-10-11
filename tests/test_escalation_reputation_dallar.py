"""sester.escalation.EscalationQueue._expire / _decide +
sester.reputation.ReputationLedger._query dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — sqlite3 ':memory:' (escalation) + tmp_path file-db
(reputation — yeni connection acildigi icin ':memory:' OLMAMALI).
"""
import json
import sqlite3
import time

import pytest

from sester.escalation import APPROVED, DENIED, EscalationQueue, PENDING
from sester.ledger import Ledger
from sester.reputation import Reputation, ReputationLedger


@pytest.fixture
def q():
    return EscalationQueue(":memory:")


def park_one(queue, agent="ag", resource="/r", amount=0.05, rule_id="R1",
             reason="dal-test"):
    return queue.park(agent=agent, resource=resource, amount=amount,
                      rule_id=rule_id, reason=reason)


# == _expire =====================================================================================

class TestExpire:
    def test_no_pending_noop(self, q):
        q._expire()
        assert True  # hata-yok

    def test_returns_none(self, q):
        assert q._expire() is None

    def test_pending_not_expired_stays_pending(self, q):
        o = park_one(q)
        q._expire()
        status = dict(q._conn.execute(
            "SELECT status FROM escalations WHERE esc_id=?", (o["esc_id"],)
        ).fetchone())["status"]
        assert status == PENDING

    def test_expired_pending_marked_expired(self, q):
        o = park_one(q)
        q._conn.execute("UPDATE escalations SET expires_at=? WHERE esc_id=?",
                        (time.time() - 10, o["esc_id"]))
        q._conn.commit()
        q._expire()
        status = dict(q._conn.execute(
            "SELECT status FROM escalations WHERE esc_id=?", (o["esc_id"],)
        ).fetchone())["status"]
        assert status == "expired"

    def test_expire_only_pending(self, q):
        """ORTAM: WHERE status='pending' — approved/denied DOKUNULMAZ."""
        a = park_one(q)
        q._decide(a["esc_id"], True, "by", "n", None)
        q._conn.execute("UPDATE escalations SET expires_at=? WHERE esc_id=?",
                        (time.time() - 10, a["esc_id"]))
        q._conn.commit()
        q._expire()
        assert dict(q._conn.execute(
            "SELECT status FROM escalations WHERE esc_id=?", (a["esc_id"],)
        ).fetchone())["status"] == APPROVED

    def test_expire_only_old(self, q):
        """ORTAM: expires_at < now — gelecekteki-biletler KALIR."""
        old = park_one(q, agent="old")
        new = park_one(q, agent="new")
        q._conn.execute("UPDATE escalations SET expires_at=? WHERE esc_id=?",
                        (time.time() - 10, old["esc_id"]))
        q._conn.commit()
        q._expire()
        rows = {r["agent"]: r["status"] for r in q._conn.execute(
            "SELECT agent, status FROM escalations")}
        assert rows["old"] == "expired"
        assert rows["new"] == PENDING

    def test_expire_multiple(self, q):
        for i in range(5):
            park_one(q, agent=f"ag{i}")
        q._conn.execute("UPDATE escalations SET expires_at=?",
                        (time.time() - 10,))
        q._conn.commit()
        q._expire()
        n = q._conn.execute(
            "SELECT COUNT(*) FROM escalations WHERE status='expired'").fetchone()[0]
        assert n == 5

    def test_expire_idempotent(self, q):
        o = park_one(q)
        q._conn.execute("UPDATE escalations SET expires_at=? WHERE esc_id=?",
                        (time.time() - 10, o["esc_id"]))
        q._conn.commit()
        q._expire()
        q._expire()
        assert dict(q._conn.execute(
            "SELECT status FROM escalations WHERE esc_id=?", (o["esc_id"],)
        ).fetchone())["status"] == "expired"

    def test_decided_at_set_on_expire(self, q):
        """ORTAM: decided_at=now ile birlikte guncellenir."""
        o = park_one(q)
        q._conn.execute("UPDATE escalations SET expires_at=? WHERE esc_id=?",
                        (time.time() - 10, o["esc_id"]))
        q._conn.commit()
        q._expire()
        row = dict(q._conn.execute(
            "SELECT decided_at FROM escalations WHERE esc_id=?", (o["esc_id"],)
        ).fetchone())
        assert row["decided_at"] is not None


# == _decide =====================================================================================

class TestDecide:
    def test_approve_returns_row(self, q):
        o = park_one(q)
        out = q._decide(o["esc_id"], True, "oncall", "ok", None)
        assert out["esc_id"] == o["esc_id"]
        assert out["status"] == APPROVED

    def test_deny_returns_row(self, q):
        o = park_one(q)
        out = q._decide(o["esc_id"], False, "oncall", "no", None)
        assert out["status"] == DENIED

    def test_decided_by_and_note(self, q):
        o = park_one(q)
        out = q._decide(o["esc_id"], True, "operator-1", "not-1", None)
        assert out["decided_by"] == "operator-1"
        assert out["note"] == "not-1"

    @pytest.mark.parametrize("approve,status", [(True, "approved"), (False, "denied")])
    def test_status_mapping(self, q, approve, status):
        o = park_one(q)
        assert q._decide(o["esc_id"], approve, "b", "n", None)["status"] == status

    def test_returned_row_is_dict(self, q):
        o = park_one(q)
        assert isinstance(q._decide(o["esc_id"], True, "b", "n", None), dict)

    def test_returned_row_has_all_keys(self, q):
        o = park_one(q)
        out = q._decide(o["esc_id"], True, "b", "n", None)
        for k in ("esc_id", "agent", "resource", "status", "decided_by", "note"):
            assert k in out

    def test_missing_esc_id_raises_keyerror(self, q):
        """ORTAM: KeyError('bilet yok: ...') — fail-loud."""
        with pytest.raises(KeyError):
            q._decide("nope", True, "b", "n", None)

    def test_re_decide_raises_valueerror(self, q):
        """ORTAM: status != PENDING -> ValueError('bilet approved — karar verilemez')."""
        o = park_one(q)
        q._decide(o["esc_id"], True, "b", "n", None)
        with pytest.raises(ValueError):
            q._decide(o["esc_id"], False, "b", "n", None)

    def test_decide_after_deny_raises(self, q):
        o = park_one(q)
        q._decide(o["esc_id"], False, "b", "n", None)
        with pytest.raises(ValueError):
            q._decide(o["esc_id"], True, "b", "n", None)

    def test_decide_after_expire_raises(self, q):
        o = park_one(q)
        q._conn.execute("UPDATE escalations SET expires_at=? WHERE esc_id=?",
                        (time.time() - 10, o["esc_id"]))
        q._conn.commit()
        q._expire()
        with pytest.raises(ValueError):
            q._decide(o["esc_id"], True, "b", "n", None)

    def test_expire_runs_before_decide(self, q):
        """ORTAM: _decide once _expire cagirir — suresi-dolmus bilet RED."""
        o = park_one(q)
        q._conn.execute("UPDATE escalations SET expires_at=? WHERE esc_id=?",
                        (time.time() - 10, o["esc_id"]))
        q._conn.commit()
        with pytest.raises(ValueError):
            q._decide(o["esc_id"], True, "b", "n", None)

    def test_decided_at_set(self, q):
        o = park_one(q)
        out = q._decide(o["esc_id"], True, "b", "n", None)
        assert out["decided_at"] is not None

    def test_db_persisted_after_decide(self, q):
        o = park_one(q)
        q._decide(o["esc_id"], True, "b", "n", None)
        row = dict(q._conn.execute(
            "SELECT * FROM escalations WHERE esc_id=?", (o["esc_id"],)).fetchone())
        assert row["status"] == APPROVED
        assert row["decided_by"] == "b"

    def test_note_empty_string_ok(self, q):
        o = park_one(q)
        out = q._decide(o["esc_id"], True, "b", "", None)
        assert out["note"] == ""

    def test_no_oracle_ref(self):
        """ORTAM: ledger=None ise append YAPILMAZ (opsiyonel)."""
        q = EscalationQueue(":memory:", ledger=None)
        o = park_one(q)
        q._decide(o["esc_id"], True, "b", "n", None)
        assert True

    def test_ledger_receives_approved_event(self):
        """ORTAM: escalation_approved olayi + payload (esc_id/by/note)."""
        lg = Ledger(":memory:", secret="s")
        q = EscalationQueue(":memory:", ledger=lg)
        o = park_one(q, agent="ag9")
        q._decide(o["esc_id"], True, "by1", "note1", None)
        evs = [e for e in lg.export_events(agent_id="ag9")
               if e["event_type"] == "escalation_approved"]
        assert len(evs) == 1
        p = json.loads(evs[0]["payload"])
        assert p["esc_id"] == o["esc_id"]
        assert p["by"] == "by1"
        assert p["note"] == "note1"

    def test_ledger_receives_denied_event(self):
        lg = Ledger(":memory:", secret="s")
        q = EscalationQueue(":memory:", ledger=lg)
        o = park_one(q, agent="ag10")
        q._decide(o["esc_id"], False, "by2", "note2", None)
        evs = [e for e in lg.export_events(agent_id="ag10")
               if e["event_type"] == "escalation_denied"]
        assert len(evs) == 1

    def test_oracle_ref_included_when_given(self):
        """ORTAM: oracle_ref None DEGILSE payload'a eklenir (tarafsiz-kaynak)."""
        lg = Ledger(":memory:", secret="s")
        q = EscalationQueue(":memory:", ledger=lg)
        o = park_one(q, agent="ag11")
        q._decide(o["esc_id"], True, "by3", "n3", "oracle-ref-x")
        ev = [e for e in lg.export_events(agent_id="ag11")
              if e["event_type"] == "escalation_approved"][0]
        assert json.loads(ev["payload"])["oracle_ref"] == "oracle-ref-x"

    def test_oracle_ref_absent_when_none(self):
        lg = Ledger(":memory:", secret="s")
        q = EscalationQueue(":memory:", ledger=lg)
        o = park_one(q, agent="ag12")
        q._decide(o["esc_id"], True, "by4", "n4", None)
        ev = [e for e in lg.export_events(agent_id="ag12")
              if e["event_type"] == "escalation_approved"][0]
        assert "oracle_ref" not in json.loads(ev["payload"])

    def test_decide_under_lock(self, q):
        """ORTAM: with self._lock — thread-safe serilestirme."""
        import inspect
        assert "self._lock" in inspect.getsource(EscalationQueue._decide)


# == ReputationLedger._query =====================================================================

@pytest.fixture
def rep_db(tmp_path):
    """tmp_path file-db — Kural-4: ':memory:' OLMAMAZ (yeni connection)."""
    return ReputationLedger(str(tmp_path / "rep.db"))


def seed_events(db_path, rows):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE events (seq INTEGER, ts REAL, event_type TEXT,"
                     " agent_id TEXT, host TEXT, amount REAL, payload TEXT,"
                     " prev_hash TEXT, hash TEXT)")
        for i, (dec, agent, host, amt) in enumerate(rows):
            payload = json.dumps({"decision": dec}) if dec is not None else "{}"
            conn.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)",
                         (i, time.time(), "permission_decision", agent, host,
                          amt, payload, "p", "h"))
        conn.commit()
    finally:
        conn.close()


class TestQuery:
    def test_empty_db_returns_neutral(self, rep_db):
        r = rep_db._query("a1")
        assert r.agent == "a1"
        assert r.completed == 0 and r.denied == 0

    def test_returns_reputation(self, rep_db):
        assert isinstance(rep_db._query("x"), Reputation)

    def test_unknown_agent_neutral(self, rep_db):
        seed_events(rep_db._db_path, [("allow", "a1", "h1", 0.05)])
        r = rep_db._query("nobody")
        assert r.completed == 0 and r.total_spent == 0.0

    def test_counts_allow_and_deny(self, rep_db):
        seed_events(rep_db._db_path, [
            ("allow", "a1", "h1", 0.05), ("allow", "a1", "h2", 0.10),
            ("deny", "a1", "h1", 0.0),
        ])
        r = rep_db._query("a1")
        assert r.completed == 2
        assert r.denied == 1

    def test_total_spent_sums_amount(self, rep_db):
        seed_events(rep_db._db_path, [
            ("allow", "a1", "h1", 0.05), ("allow", "a1", "h2", 0.10),
        ])
        assert abs(rep_db._query("a1").total_spent - 0.15) < 1e-9

    def test_deny_amounts_also_summed(self, rep_db):
        """ORTAM: SUM(amount) — deny-satirlari DAHIL (kategori-filter YOK)."""
        seed_events(rep_db._db_path, [("deny", "a1", "h1", 2.0)])
        assert rep_db._query("a1").total_spent == 2.0

    def test_unique_resources_distinct_host(self, rep_db):
        """ORTAM: COUNT(DISTINCT host) — wash-trade direnci (#2833)."""
        seed_events(rep_db._db_path, [
            ("allow", "a1", "h1", 0.05), ("allow", "a1", "h1", 0.05),
            ("allow", "a1", "h2", 0.05),
        ])
        assert rep_db._query("a1").unique_resources == 2

    def test_agents_isolated(self, rep_db):
        seed_events(rep_db._db_path, [
            ("allow", "a1", "h1", 0.05), ("allow", "a2", "h9", 1.0),
        ])
        assert rep_db._query("a1").completed == 1
        assert rep_db._query("a2").completed == 1

    def test_other_event_types_excluded(self, rep_db):
        """ORTAM: WHERE event_type='permission_decision'."""
        conn = sqlite3.connect(rep_db._db_path)
        try:
            conn.execute("CREATE TABLE events (seq INTEGER, ts REAL, event_type TEXT,"
                         " agent_id TEXT, host TEXT, amount REAL, payload TEXT,"
                         " prev_hash TEXT, hash TEXT)")
            conn.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)",
                         (1, time.time(), "charge_receipt", "a1", "h1", 5.0,
                          "{}", "p", "h"))
            conn.commit()
        finally:
            conn.close()
        assert rep_db._query("a1").completed == 0

    def test_null_payload_neutral(self, rep_db):
        """ORTAM: json_extract(null) -> NULL -> ELSE 0."""
        seed_events(rep_db._db_path, [(None, "a1", "h1", 1.0)])
        r = rep_db._query("a1")
        assert r.completed == 0 and r.denied == 0

    def test_missing_decision_key_neutral(self, rep_db):
        """ORTAM: payload '{}' -> json_extract -> NULL."""
        conn = sqlite3.connect(rep_db._db_path)
        try:
            conn.execute("CREATE TABLE events (seq INTEGER, ts REAL, event_type TEXT,"
                         " agent_id TEXT, host TEXT, amount REAL, payload TEXT,"
                         " prev_hash TEXT, hash TEXT)")
            conn.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)",
                         (1, time.time(), "permission_decision", "a1", "h1", 1.0,
                          "{}", "p", "h"))
            conn.commit()
        finally:
            conn.close()
        assert rep_db._query("a1").completed == 0

    def test_case_sensitive_decision(self, rep_db):
        """ORTAM: ='allow' case-sensitive — 'Allow' sayilmaz."""
        seed_events(rep_db._db_path, [("Allow", "a1", "h1", 1.0)])
        assert rep_db._query("a1").completed == 0

    def test_missing_db_returns_neutral(self, tmp_path):
        """ORTAM: tablo-yok -> (sqlite3.Error, OSError) yakalanir -> nötr."""
        rl = ReputationLedger(str(tmp_path / "nope.db"))
        r = rl._query("x")
        assert r.completed == 0 and r.denied == 0

    def test_type_coercions(self, rep_db):
        seed_events(rep_db._db_path, [("allow", "a1", "h1", 0.05)])
        r = rep_db._query("a1")
        assert isinstance(r.completed, int)
        assert isinstance(r.denied, int)
        assert isinstance(r.total_spent, float)
        assert isinstance(r.unique_resources, int)

    def test_agent_field_set(self, rep_db):
        assert rep_db._query("my-agent").agent == "my-agent"

    def test_zero_rows_returns_neutral(self, rep_db):
        """ORTAM: fetchone() bos-tabloda None DEGIL — coalesce'li sutunlar 0."""
        seed_events(rep_db._db_path, [])
        r = rep_db._query("a1")
        assert r.completed == 0 and r.total_spent == 0.0
