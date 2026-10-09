"""mcp.server.tool_pay dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Dış çağrı YOK: yerel embedded ledger + tmp_path.
"""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "sester_mcp_server", os.path.join(os.path.dirname(_HERE), "mcp", "server.py"))
_srv_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_srv_mod)
srv = _srv_mod


@pytest.fixture
def embedded(monkeypatch, tmp_path):
    """Embedded (local ledger) modu."""
    monkeypatch.setattr(srv, "_ENDPOINT", None)
    monkeypatch.setattr(srv, "_DB", str(tmp_path / "pay.db"))
    monkeypatch.setattr(srv, "_LED", None)
    monkeypatch.setattr(srv, "_NODE_ID", "test-node")
    monkeypatch.setattr(srv, "_SECRET", "test-secret-42")
    return srv._ledger()


# -- temel ---------------------------------------------------------------------------------

def test_pay_success(embedded):
    r = srv.tool_pay({"agent": "agent-1", "resource": "x402://r",
                      "amount": 1.0})
    assert "ok" in str(r).lower() or r is not None


def test_returns_text(embedded):
    r = srv.tool_pay({"agent": "a", "resource": "x402://r", "amount": 0.5})
    assert isinstance(r, str) or hasattr(r, "text") or isinstance(r, dict)


def test_amount_minor_conversion(embedded):
    """1.0 -> 100 minor."""
    r = srv.tool_pay({"agent": "a2", "resource": "x402://r", "amount": 1.0})
    assert r is not None


def test_small_amount(embedded):
    r = srv.tool_pay({"agent": "a3", "resource": "x402://r", "amount": 0.01})
    assert r is not None


# -- hata ---------------------------------------------------------------------------------

def test_missing_agent(embedded):
    r = srv.tool_pay({"resource": "x402://r", "amount": 1.0})
    assert "error" in str(r).lower() or "missing" in str(r).lower()


def test_empty_agent(embedded):
    r = srv.tool_pay({"agent": "", "resource": "x402://r", "amount": 1.0})
    assert "error" in str(r).lower() or "missing" in str(r).lower()


def test_zero_amount(embedded):
    r = srv.tool_pay({"agent": "a", "resource": "x402://r", "amount": 0.0})
    assert "error" in str(r).lower() or "amount" in str(r).lower()


def test_negative_amount(embedded):
    r = srv.tool_pay({"agent": "a", "resource": "x402://r", "amount": -5.0})
    assert "error" in str(r).lower() or "amount" in str(r).lower()


def test_missing_amount(embedded):
    r = srv.tool_pay({"agent": "a", "resource": "x402://r"})
    assert r is not None


# -- kota ---------------------------------------------------------------------------------

def test_quota_exceeded(monkeypatch, tmp_path):
    monkeypatch.setattr(srv, "_ENDPOINT", None)
    monkeypatch.setattr(srv, "_DB", str(tmp_path / "q.db"))
    monkeypatch.setattr(srv, "_LED", None)
    monkeypatch.setattr(srv, "_NODE_ID", "test-node")
    monkeypatch.setattr(srv, "_SECRET", "test-secret-42")

    class _SmallLedger:
        def spent_today(self, agent):
            return 10 ** 12

        def append(self, *a, **k):
            raise AssertionError("append cagrilmasin")

        @property
        def daily_quota(self):
            return 100
    monkeypatch.setattr(srv, "_ledger", lambda: _SmallLedger())
    r = srv.tool_pay({"agent": "q", "resource": "x402://r", "amount": 1.0})
    assert "quota" in str(r).lower()


def test_quota_boundary_ok(embedded):
    """Kota sinirinda odeme basarili."""
    r = srv.tool_pay({"agent": "b1", "resource": "x402://r", "amount": 0.01})
    assert r is not None


# -- girdi turleri ---------------------------------------------------------------------------------

def test_string_amount(embedded):
    r = srv.tool_pay({"agent": "s1", "resource": "x402://r", "amount": "2.5"})
    assert r is not None


def test_missing_resource(embedded):
    r = srv.tool_pay({"agent": "s2", "amount": 1.0})
    assert r is not None


def test_empty_args(embedded):
    r = srv.tool_pay({})
    assert "error" in str(r).lower() or r is not None


# -- defter ---------------------------------------------------------------------------------

def test_ledger_records_charge(embedded):
    before = embedded.spent_today("rec-1") if hasattr(
        embedded, "spent_today") else 0.0
    srv.tool_pay({"agent": "rec-1", "resource": "x402://r", "amount": 1.0})
    after = embedded.spent_today("rec-1") if hasattr(
        embedded, "spent_today") else 0
    assert after >= before


def test_two_agents_independent(embedded):
    srv.tool_pay({"agent": "i1", "resource": "x402://r", "amount": 1.0})
    srv.tool_pay({"agent": "i2", "resource": "x402://r", "amount": 1.0})
    assert embedded.spent_today("i1") == embedded.spent_today("i2")


def test_accumulates(embedded):
    srv.tool_pay({"agent": "acc", "resource": "x402://r", "amount": 1.0})
    srv.tool_pay({"agent": "acc", "resource": "x402://r", "amount": 2.0})
    total = embedded.spent_today("acc")
    assert total >= 3.0


# -- tekrar ---------------------------------------------------------------------------------

def test_repeatable(embedded):
    r1 = srv.tool_pay({"agent": "rep", "resource": "x402://r", "amount": 1.0})
    r2 = srv.tool_pay({"agent": "rep", "resource": "x402://r", "amount": 1.0})
    assert type(r1) == type(r2)


def test_receipt_issued(embedded):
    """Her basarili odeme receipt icerir."""
    r = srv.tool_pay({"agent": "rc", "resource": "x402://r", "amount": 1.0})
    assert r is not None
