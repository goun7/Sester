"""sester.pg_ledger._connect dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — psycopg/psycopg2 STUBLA (sys.modules monkeypatch),
GERCEK baglanti KURULMAZ.
Cift-backend: psycopg -> psycopg2 -> RuntimeError.
"""
import sys
import types

import pytest

sys.path.insert(0, ".")
from sester.pg_ledger import _connect  # noqa: E402


class FakeConn:
    def __init__(self, dsn):
        self.dsn = dsn
        self.closed = False

    def close(self):
        self.closed = True


def make_fake_module(name, sentinel=None):
    m = types.ModuleType(name)

    def connect(dsn, *a, **k):
        return FakeConn(f"{name}:{dsn}")

    m.connect = connect
    return m


# == psycopg-onceligi ========================================================================

def test_psycopg_preferred(monkeypatch):
    """psycopg varsa onu kullanir."""
    monkeypatch.setitem(sys.modules, "psycopg", make_fake_module("psycopg"))
    r = _connect("dbname=x")
    assert isinstance(r, FakeConn)
    assert r.dsn == "psycopg:dbname=x"


def test_psycopg_receives_dsn(monkeypatch):
    m = make_fake_module("psycopg")
    got = {}

    def connect(dsn, *a, **k):
        got["dsn"] = dsn
        return FakeConn(dsn)
    m.connect = connect
    monkeypatch.setitem(sys.modules, "psycopg", m)
    _connect("host=localhost dbname=test")
    assert got["dsn"] == "host=localhost dbname=test"


def test_psycopg_kwargs(monkeypatch):
    m = make_fake_module("psycopg")
    got = {}

    def connect(dsn, *a, **k):
        got.update(k)
        return FakeConn(dsn)
    m.connect = connect
    monkeypatch.setitem(sys.modules, "psycopg", m)
    _connect("dsn")
    assert got == {}  # sadece dsn gecer


# == psycopg2-fallback =======================================================================

def test_psycopg2_fallback(monkeypatch):
    """psycopg YOKSA psycopg2 dener."""
    monkeypatch.setitem(sys.modules, "psycopg", None)
    m = make_fake_module("psycopg2")
    monkeypatch.setitem(sys.modules, "psycopg2", m)
    r = _connect("dbname=y")
    assert r.dsn == "psycopg2:dbname=y"


def test_fallback_uses_psycopg2_connect(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", None)
    m2 = make_fake_module("psycopg2")
    monkeypatch.setitem(sys.modules, "psycopg2", m2)
    assert _connect("z").dsn.startswith("psycopg2:")


def test_no_psycopg_import_error_path(monkeypatch):
    """psycopg import'u ImportError verirse psycopg2'ye duser."""
    orig = __import__

    def fake_import(name, *a, **k):
        if name == "psycopg":
            raise ImportError("no psycopg")
        return orig(name, *a, **k)
    monkeypatch.setattr("builtins.__import__", fake_import)
    monkeypatch.setitem(sys.modules, "psycopg2", make_fake_module("psycopg2"))
    r = _connect("w")
    assert r.dsn == "psycopg2:w"


# == ikisi-de-yok =============================================================================

def test_no_backends_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", None)
    monkeypatch.setitem(sys.modules, "psycopg2", None)
    with pytest.raises(RuntimeError):
        _connect("dbname=x")


def test_error_message_mentions_psycopg(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", None)
    monkeypatch.setitem(sys.modules, "psycopg2", None)
    with pytest.raises(RuntimeError) as ei:
        _connect("x")
    assert "psycopg" in str(ei.value)


def test_error_message_mentions_pip(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", None)
    monkeypatch.setitem(sys.modules, "psycopg2", None)
    with pytest.raises(RuntimeError) as ei:
        _connect("x")
    assert "pip install" in str(ei.value)


def test_error_message_mentions_pg_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", None)
    monkeypatch.setitem(sys.modules, "psycopg2", None)
    with pytest.raises(RuntimeError) as ei:
        _connect("x")
    assert "sester[pg]" in str(ei.value)


def test_runtime_error_chains_import_error(monkeypatch):
    """from e ile orijinal ImportError zincirlenir."""
    monkeypatch.setitem(sys.modules, "psycopg", None)
    monkeypatch.setitem(sys.modules, "psycopg2", None)
    with pytest.raises(RuntimeError) as ei:
        _connect("x")
    assert ei.value.__cause__ is not None
    assert isinstance(ei.value.__cause__, ImportError)


# == import-farkliliklari =====================================================================

def test_psycopg2_import_error_to_runtime(monkeypatch):
    """psycopg2 ImportError -> RuntimeError (pragma: no cover)."""
    monkeypatch.setitem(sys.modules, "psycopg", None)
    monkeypatch.setitem(sys.modules, "psycopg2", None)
    try:
        _connect("x")
        assert False
    except RuntimeError:
        assert True


def test_psycopg_import_repeated(monkeypatch):
    """her cagrida yeniden import dener."""
    m = make_fake_module("psycopg")
    monkeypatch.setitem(sys.modules, "psycopg", m)
    a = _connect("a")
    b = _connect("b")
    assert a.dsn != b.dsn


# == dsn-gecis ================================================================================

def test_empty_dsn(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", make_fake_module("psycopg"))
    assert _connect("").dsn == "psycopg:"


def test_full_dsn(monkeypatch):
    dsn = "postgresql://user:pass@host:5432/db"
    monkeypatch.setitem(sys.modules, "psycopg", make_fake_module("psycopg"))
    assert _connect(dsn).dsn == f"psycopg:{dsn}"


def test_unicode_dsn(monkeypatch):
    dsn = "dbname=İstanbul"
    monkeypatch.setitem(sys.modules, "psycopg", make_fake_module("psycopg"))
    assert _connect(dsn).dsn == f"psycopg:{dsn}"


def test_turkish_host(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", make_fake_module("psycopg"))
    r = _connect("host=gokhan-İstanbul")
    assert "İstanbul" in r.dsn


# == cesitli ===================================================================================

def test_returns_connection(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", make_fake_module("psycopg"))
    r = _connect("x")
    assert hasattr(r, "close")


def test_connection_closable(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", make_fake_module("psycopg"))
    r = _connect("x")
    r.close()
    assert r.closed is True


def test_repeatable(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", make_fake_module("psycopg"))
    assert _connect("same").dsn == _connect("same").dsn


def test_no_global_mutation(monkeypatch):
    """stub curaysa bile modules temiz kalir."""
    m = make_fake_module("psycopg")
    monkeypatch.setitem(sys.modules, "psycopg", m)
    _connect("x")
    assert sys.modules["psycopg"] is m


@pytest.mark.parametrize("dsn", [
    "dbname=a", "host=h dbname=b", "postgresql://localhost/c", "",
])
def test_dsn_passthrough(monkeypatch, dsn):
    monkeypatch.setitem(sys.modules, "psycopg", make_fake_module("psycopg"))
    assert _connect(dsn).dsn == f"psycopg:{dsn}"
