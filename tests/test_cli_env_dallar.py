"""sester.cli._db + _node_secret dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — args-stub + monkeypatch os.environ (gercek DB YOK).
(1) _db: args.ledger || env SESTER_LEDGER_DB || 'sester.sqlite3';
(2) _node_secret: args.node_secret || env SESTER_NODE_SECRET || None.
"""
import pytest

from sester.cli import _db, _node_secret


class Args:
    """Minimal argparse-namespace stubu — sadece istenen alan set-edilir."""

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("SESTER_LEDGER_DB", raising=False)
    monkeypatch.delenv("SESTER_NODE_SECRET", raising=False)


# == _db ========================================================================================

def test_db_returns_str():
    assert isinstance(_db(Args(ledger="x.db")), str)


def test_db_attr_wins(clean_env):
    assert _db(Args(ledger="cli.db")) == "cli.db"


@pytest.mark.parametrize("falsy", [None, ""])
def test_db_falsy_attr_falls_through(falsy, clean_env):
    """ORTAM: args.ledger None/BOS -> env'e, oradan default'a."""
    assert _db(Args(ledger=falsy)) == "sester.sqlite3"


def test_db_env_used_when_attr_missing_value(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_DB", "env.db")
    assert _db(Args(ledger=None)) == "env.db"


def test_db_attr_wins_over_env(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_DB", "env.db")
    assert _db(Args(ledger="cli.db")) == "cli.db"


def test_db_default_when_nothing_set(clean_env):
    assert _db(Args(ledger=None)) == "sester.sqlite3"


@pytest.mark.parametrize("ledger", [
    "a.db", "/tmp/x.db", "sester.sqlite3", "türkçe.db", "emoji😀.db",
    "path with spaces.db", "a" * 200 + ".db", "./rel.db", "file:memdb1?mode=memory",
])
def test_db_various_values(ledger, clean_env):
    assert _db(Args(ledger=ledger)) == ledger


def test_db_env_empty_string_returns_empty(clean_env, monkeypatch):
    """ORTAM-OGRENDI: SESTER_LEDGER_DB='' (env SET-AMA-BOS) -> os.environ.get
    default DEGIL '' doner (env-anahtari mevcut — .get default yanlis)."""
    monkeypatch.setenv("SESTER_LEDGER_DB", "")
    assert _db(Args(ledger=None)) == ""


def test_db_env_empty_and_attr_empty_returns_empty(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_DB", "")
    assert _db(Args(ledger="")) == ""


def test_db_no_ledger_attr_raises(clean_env):
    """ORTAM: args.ledger alani YOKSA AttributeError YAYILIR (getattr/varsayilan YOK)."""
    with pytest.raises(AttributeError):
        _db(Args())


def test_db_reads_env_lazily(clean_env, monkeypatch):
    """ORTAM: her cagrida env YENIDEN okunur (cached DEGIL)."""
    monkeypatch.setenv("SESTER_LEDGER_DB", "first.db")
    assert _db(Args(ledger=None)) == "first.db"
    monkeypatch.setenv("SESTER_LEDGER_DB", "second.db")
    assert _db(Args(ledger=None)) == "second.db"


def test_db_repeatable(clean_env):
    a = Args(ledger="r.db")
    assert _db(a) == _db(a) == "r.db"


def test_db_args_not_mutated(clean_env):
    a = Args(ledger="m.db")
    _db(a)
    assert a.ledger == "m.db"


@pytest.mark.parametrize("env,expected", [
    ("e1.db", "e1.db"), ("e2.db", "e2.db"), ("", ""),
])
def test_db_env_matrix(env, expected, clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_DB", env)
    assert _db(Args(ledger=None)) == expected


# == _node_secret ===============================================================================

def test_node_secret_returns_none_or_str(clean_env):
    r = _node_secret(Args(node_secret=None))
    assert r is None or isinstance(r, str)


def test_node_secret_attr_wins(clean_env):
    assert _node_secret(Args(node_secret="cli-sec")) == "cli-sec"


@pytest.mark.parametrize("falsy", [None, ""])
def test_node_secret_falsy_attr_falls_through(falsy, clean_env):
    """ORTAM: args.node_secret None/BOS -> env'e, env YOKSA None."""
    assert _node_secret(Args(node_secret=falsy)) is None


def test_node_secret_env_used(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_NODE_SECRET", "env-sec")
    assert _node_secret(Args(node_secret=None)) == "env-sec"


def test_node_secret_attr_wins_over_env(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_NODE_SECRET", "env-sec")
    assert _node_secret(Args(node_secret="cli")) == "cli"


def test_node_secret_default_none(clean_env):
    """ORTAM: env YOKSA None (bos-str DEGIL — 's or None' nothing else)."""
    assert _node_secret(Args(node_secret=None)) is None


@pytest.mark.parametrize("secret", [
    "abc", "0", "false", "None", "   ", "  x  ", "türkçe-anahtar", "😀",
    "a" * 100, "hex-deadbeef", "sk_1234567890",
])
def test_node_secret_various_values(secret, clean_env):
    """ORTAM-OGRENDI: '0'/'false'/'None' STRING falsy DEGIL — kelime-listesi YOK,
    her bos-olmayan str kabul; '   ' (bosluk) da True (strip YAPILMAZ)."""
    assert _node_secret(Args(node_secret=secret)) == secret


def test_node_secret_env_empty_returns_none(clean_env, monkeypatch):
    """ORTAM-OGRENDI: SESTER_NODE_SECRET='' -> 's or None' -> None."""
    monkeypatch.setenv("SESTER_NODE_SECRET", "")
    assert _node_secret(Args(node_secret=None)) is None


def test_node_secret_no_attr_raises(clean_env):
    """ORTAM: args.node_secret alani YOKSA AttributeError YAYILIR."""
    with pytest.raises(AttributeError):
        _node_secret(Args())


def test_node_secret_reads_env_lazily(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_NODE_SECRET", "first")
    assert _node_secret(Args(node_secret=None)) == "first"
    monkeypatch.setenv("SESTER_NODE_SECRET", "second")
    assert _node_secret(Args(node_secret=None)) == "second"


def test_node_secret_repeatable(clean_env):
    a = Args(node_secret="s")
    assert _node_secret(a) == _node_secret(a) == "s"


def test_node_secret_args_not_mutated(clean_env):
    a = Args(node_secret="keep")
    _node_secret(a)
    assert a.node_secret == "keep"


def test_node_secret_independent_from_db_env(clean_env, monkeypatch):
    """ORTAM: iki env birbirinden bagimsiz."""
    monkeypatch.setenv("SESTER_LEDGER_DB", "ledger.db")
    assert _node_secret(Args(node_secret=None)) is None


def test_db_independent_from_node_secret_env(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_NODE_SECRET", "sec")
    assert _db(Args(ledger=None)) == "sester.sqlite3"


@pytest.mark.parametrize("ledger,node_env,expected", [
    (None, None, "sester.sqlite3"),
    (None, "n.db", "n.db"),
    ("c.db", None, "c.db"),
    ("c.db", "n.db", "c.db"),
])
def test_db_full_matrix(ledger, node_env, expected, clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_NODE_SECRET", node_env if node_env else "")
    monkeypatch.setenv("SESTER_LEDGER_DB", node_env if node_env else "")
    if node_env is None:
        monkeypatch.delenv("SESTER_LEDGER_DB", raising=False)
    assert _db(Args(ledger=ledger)) == expected
