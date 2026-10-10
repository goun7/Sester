"""63-Sester guard_sester.observe_sibling_k1 dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-3: subprocess.run stub — gercek surec YAPILMADI.
"""
import sys

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "scripts/git_hooks")

from guard_sester import observe_sibling_k1  # noqa: E402


class _Spy:
    runs = []
    rc = 0
    ledger = []
    oks = []
    unlink_paths = []


@pytest.fixture
def fake(monkeypatch, tmp_path):
    _Spy.runs = []
    _Spy.rc = 0
    _Spy.ledger = []
    _Spy.oks = []
    _Spy.unlink_paths = []
    k1 = tmp_path / "k1_alici.py"
    k1.write_text("# stub", encoding="utf-8")
    import guard_sester as G
    monkeypatch.setattr(G, "SIBLING_K1", k1)

    class _R:
        returncode = 0
        stdout = "ok"
        stderr = ""
    _r = _R()
    _r.returncode = _Spy.rc

    def _run(cmd, **kw):
        _Spy.runs.append((cmd, kw))
        _r.returncode = _Spy.rc
        return _r
    monkeypatch.setattr(G.subprocess, "run", _run)
    monkeypatch.setattr(G, "note_ledger",
                        lambda *a: _Spy.ledger.append(a))
    monkeypatch.setattr(G, "ok",
                        lambda *a, **kw: _Spy.oks.append(a))

    class _P:
        def unlink(self, missing_ok=False):
            _Spy.unlink_paths.append("probe")
            return None
    monkeypatch.setattr(G.Path, "unlink", _P.unlink)
    return tmp_path


# -- yok ---------------------------------------------------------------------------------

def test_missing_sibling_returns_0(monkeypatch, tmp_path):
    import guard_sester as G
    monkeypatch.setattr(G, "SIBLING_K1", tmp_path / "yok.py")
    assert observe_sibling_k1() == 0


def test_missing_no_subprocess(monkeypatch, tmp_path):
    import guard_sester as G
    monkeypatch.setattr(G, "SIBLING_K1", tmp_path / "yok.py")
    observe_sibling_k1()
    assert _Spy.runs == []


def test_missing_no_ledger(monkeypatch, tmp_path):
    import guard_sester as G
    monkeypatch.setattr(G, "SIBLING_K1", tmp_path / "yok.py")
    observe_sibling_k1()
    assert _Spy.ledger == []


def test_missing_no_ok(monkeypatch, tmp_path):
    import guard_sester as G
    monkeypatch.setattr(G, "SIBLING_K1", tmp_path / "yok.py")
    observe_sibling_k1()
    assert _Spy.oks == []


# -- rc=0 ---------------------------------------------------------------------------------

def test_ok_returns_0(fake):
    assert observe_sibling_k1() == 0


def test_ok_calls_subprocess(fake):
    observe_sibling_k1()
    assert len(_Spy.runs) == 1


def test_ok_cmd_uses_python(fake):
    observe_sibling_k1()
    cmd = _Spy.runs[0][0]
    assert cmd[0] == sys.executable


def test_ok_cmd_uses_sibling_path(fake):
    observe_sibling_k1()
    cmd = _Spy.runs[0][0]
    assert str(cmd[1]).endswith("k1_alici.py")


def test_ok_cmd_has_probe_arg(fake):
    observe_sibling_k1()
    cmd = _Spy.runs[0][0]
    assert len(cmd) == 3
    assert cmd[2].endswith(".jsonl")


def test_ok_timeout_30(fake):
    observe_sibling_k1()
    assert _Spy.runs[0][1]["timeout"] == 30


def test_ok_captures_output(fake):
    observe_sibling_k1()
    assert _Spy.runs[0][1]["capture_output"] is True


def test_ok_text_mode(fake):
    observe_sibling_k1()
    assert _Spy.runs[0][1]["text"] is True


def test_ok_calls_ok_logger(fake):
    observe_sibling_k1()
    assert len(_Spy.oks) == 1


def test_ok_no_drift_ledger(fake):
    observe_sibling_k1()
    assert _Spy.ledger == []


def test_ok_unlinks_probe(fake):
    observe_sibling_k1()
    assert _Spy.unlink_paths == ["probe"]


# -- rc!=0 ---------------------------------------------------------------------------------

def test_drift_returns_0(fake):
    _Spy.rc = 1
    assert observe_sibling_k1() == 0


def test_drift_calls_ledger(fake):
    _Spy.rc = 2
    observe_sibling_k1()
    assert len(_Spy.ledger) == 1


def test_drift_ledger_message_has_DRIFT(fake):
    _Spy.rc = 3
    observe_sibling_k1()
    assert "DRIFT" in _Spy.ledger[0][0]


def test_drift_ledger_mentions_sikke(fake):
    _Spy.rc = 1
    observe_sibling_k1()
    assert "sikke" in _Spy.ledger[0][0]


def test_drift_no_ok_logger(fake):
    _Spy.rc = 1
    observe_sibling_k1()
    assert _Spy.oks == []


def test_drift_still_unlinks_probe(fake):
    _Spy.rc = 1
    observe_sibling_k1()
    assert _Spy.unlink_paths == ["probe"]


def test_drift_runs_subprocess_once(fake):
    _Spy.rc = 1
    observe_sibling_k1()
    assert len(_Spy.runs) == 1


def test_drift_prints_warn(fake, capsys):
    _Spy.rc = 1
    observe_sibling_k1()
    out = capsys.readouterr().out
    assert "[SESTER-guard]" in out


def test_drift_warn_says_commit_not_blocked(fake, capsys):
    _Spy.rc = 1
    observe_sibling_k1()
    out = capsys.readouterr().out
    assert "commit not blocked" in out


def test_negative_rc_also_drift(fake):
    _Spy.rc = -1
    observe_sibling_k1()
    assert len(_Spy.ledger) == 1


# -- probe icerigi ---------------------------------------------------------------------------------

def test_probe_file_written(fake, monkeypatch):
    icerik = []

    class _F:
        name = "/tmp/probe.jsonl"

        def __init__(self, *a, **k):
            pass

        def write(self, s):
            icerik.append(s)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    import guard_sester as G
    monkeypatch.setattr(G.tempfile, "NamedTemporaryFile",
                        lambda *a, **k: _F())
    observe_sibling_k1()
    assert any("sikke" in i for i in icerik)


def test_probe_has_jsonl_suffix(fake, monkeypatch):
    seen = {}

    class _F:
        name = "/tmp/x.jsonl"

        def __init__(self, *a, **k):
            seen["suffix"] = k.get("suffix")

        def write(self, s):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    import guard_sester as G
    monkeypatch.setattr(G.tempfile, "NamedTemporaryFile",
                        lambda *a, **k: _F(**k))
    observe_sibling_k1()
    assert seen["suffix"] == ".jsonl"


def test_probe_delete_false(fake, monkeypatch):
    seen = {}

    class _F:
        name = "/tmp/x.jsonl"

        def __init__(self, *a, **k):
            seen["delete"] = k.get("delete")

        def write(self, s):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    import guard_sester as G
    monkeypatch.setattr(G.tempfile, "NamedTemporaryFile",
                        lambda *a, **k: _F(**k))
    observe_sibling_k1()
    assert seen["delete"] is False


# -- unicode ---------------------------------------------------------------------------------

def test_ledger_has_turkish(fake):
    _Spy.rc = 1
    observe_sibling_k1()
    assert "ihlal edildi" in _Spy.ledger[0][0]


def test_warn_has_ansi_color(fake, capsys):
    _Spy.rc = 1
    observe_sibling_k1()
    assert "33m" in capsys.readouterr().out


# -- tekrar ---------------------------------------------------------------------------------

def test_repeatable_ok(fake):
    observe_sibling_k1()
    observe_sibling_k1()
    assert len(_Spy.runs) == 2


def test_repeatable_drift(fake):
    _Spy.rc = 1
    observe_sibling_k1()
    observe_sibling_k1()
    assert len(_Spy.ledger) == 2
