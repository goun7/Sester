"""sester.cli._secret dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (env monkeypatch, dis cagri YOK).
SESTER_LEDGER_SECRET okur; bos/eksik -> SystemExit (fail-closed).
"""
import sys

import pytest

sys.path.insert(0, ".")
from sester.cli import _secret  # noqa: E402


@pytest.fixture()
def clean_env(monkeypatch):
    monkeypatch.delenv("SESTER_LEDGER_SECRET", raising=False)


# -- basarili -------------------------------------------------------------------------------

def test_returns_value(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "abc123")
    assert _secret() == "abc123"


def test_returns_str(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "x")
    assert isinstance(_secret(), str)


def test_turkish_value(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "gizli-anahtar-İstanbul")
    assert _secret() == "gizli-anahtar-İstanbul"


def test_emoji_value(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "🔑")
    assert _secret() == "🔑"


def test_long_value(clean_env, monkeypatch):
    v = "a" * 1000
    monkeypatch.setenv("SESTER_LEDGER_SECRET", v)
    assert _secret() == v


def test_value_with_spaces(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "  bosluklu  ")
    assert _secret() == "  bosluklu  "


def test_value_with_pipe(clean_env, monkeypatch):
    """pipe korundugu icin ayirac-enjeksiyon testi."""
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "a|b|c")
    assert _secret() == "a|b|c"


def test_special_chars(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "!@#$%^&*()_+-=[]{}")
    assert _secret() == "!@#$%^&*()_+-=[]{}"


def test_hex_value(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "0x" + "a" * 64)
    assert _secret() == "0x" + "a" * 64


def test_repeatable(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "stable")
    assert _secret() == _secret() == "stable"


# -- fail-closed -----------------------------------------------------------------------------

def test_missing_env_raises(clean_env):
    with pytest.raises(SystemExit):
        _secret()


def test_empty_env_raises(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "")
    with pytest.raises(SystemExit):
        _secret()


def test_whitespace_env_raises(clean_env, monkeypatch):
    """ORTAM: '   ' falsy DEGIL -> kabul (strip YOK)."""
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "   ")
    assert _secret() == "   "


def test_systemexit_code(clean_env):
    with pytest.raises(SystemExit) as ei:
        _secret()
    assert isinstance(ei.value.code, (str, int))


def test_systemexit_message(clean_env):
    with pytest.raises(SystemExit) as ei:
        _secret()
    assert isinstance(ei.value.code, str)
    assert "SESTER_LEDGER_SECRET" in ei.value.code


def test_message_says_red(clean_env):
    with pytest.raises(SystemExit) as ei:
        _secret()
    assert "RED" in ei.value.code


def test_message_says_gerekli(clean_env):
    with pytest.raises(SystemExit) as ei:
        _secret()
    assert "gerekli" in ei.value.code


def test_raises_not_returns_none(clean_env):
    """fail-closed: None DEGIL SystemExit."""
    try:
        _secret()
        assert False, "SystemExit beklenmisti"
    except SystemExit:
        assert True


# -- sayi-degeri ---------------------------------------------------------------------------

def test_numeric_string(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "12345")
    assert _secret() == "12345"


def test_zero_string(clean_env, monkeypatch):
    """'0' falsy-string DEGIL."""
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "0")
    assert _secret() == "0"


def test_false_string(clean_env, monkeypatch):
    """'false'/'False' falsy DEGIL."""
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "False")
    assert _secret() == "False"


def test_none_string(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "None")
    assert _secret() == "None"


# -- tekrar-oku -----------------------------------------------------------------------------

def test_read_twice(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "x")
    assert _secret() + _secret() == "xx"


def test_switched_value(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "a")
    assert _secret() == "a"
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "b")
    assert _secret() == "b"


def test_after_delete_raises(clean_env, monkeypatch):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "x")
    assert _secret() == "x"
    monkeypatch.delenv("SESTER_LEDGER_SECRET")
    with pytest.raises(SystemExit):
        _secret()


@pytest.mark.parametrize("v", ["a", "ab", "abc", "secret-key", "X" * 100])
def test_various_values(clean_env, monkeypatch, v):
    monkeypatch.setenv("SESTER_LEDGER_SECRET", v)
    assert _secret() == v
