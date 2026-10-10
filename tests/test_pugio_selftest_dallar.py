"""pugio_watch_receiver._selftest dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (dis cagri YOK); modul-ici zincir kendi uretilir.
"""
import importlib
import sys
import os

import pytest

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "bridge_receivers")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

M = importlib.import_module("pugio_watch_receiver")


@pytest.fixture()
def selftest_output():
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = M._selftest()
    return rc, [l.rstrip("\n") for l in buf.getvalue().splitlines()]


# -- rc ---------------------------------------------------------------------------------

def test_returns_zero():
    assert M._selftest() == 0


def test_returns_int():
    assert isinstance(M._selftest(), int)


def test_prints_two_lines(selftest_output):
    _, lines = selftest_output
    assert len(lines) == 2


def test_clean_line_starts_ok(selftest_output):
    _, lines = selftest_output
    assert lines[0].startswith("OK  ")


def test_tamper_line_starts_ok(selftest_output):
    """kurcalanmış akış REDDedilince satır 'OK  ' ile basar."""
    _, lines = selftest_output
    assert lines[1].startswith("OK  kurcalanmış-akış reddi")


def test_clean_line_saglam(selftest_output):
    _, lines = selftest_output
    assert "akış-SAĞLAM" in lines[0]


def test_clean_line_event_count(selftest_output):
    _, lines = selftest_output
    assert "2 olay" in lines[0]


def test_tamper_line_has_line_number(selftest_output):
    _, lines = selftest_output
    assert "satır 2" in lines[1]


def test_head_hex_in_output(selftest_output):
    _, lines = selftest_output
    assert "head=" in lines[0]


# -- uretilen akış ---------------------------------------------------------------------------------

def test_genesis_is_64_zeros():
    assert M.GENESIS == "0" * 64


def test_bridge_version():
    assert isinstance(M.BRIDGE_VERSION, int)


def test_sha_hex_64():
    h = M._sha("test")
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_sha_deterministic():
    assert M._sha("abc") == M._sha("abc")


def test_sha_input_sensitive():
    assert M._sha("abc") != M._sha("abd")


# -- verify_feed (selftest'in temeli) ---------------------------------------------------------------------------------

def _bundle():
    """selftest'in urettigi akışi yeniden uret."""
    base = {"bridge_version": M.BRIDGE_VERSION, "source": "sikke",
            "watcher_id": "selftest", "bundle_head": "a" * 64,
            "bundle_merkle_root": "b" * 64, "bundle_event_count": 2}
    prev = M.GENESIS
    events = []
    for i, (host, rule, dec) in enumerate(
            [("/weather", "quota_exceeded", "deny"),
             ("/weather", "replay", "deny")], start=1):
        ts = f"{1700000000.0 + i:.6f}"
        sha = M._sha(f"{prev}|{i}|{ts}|ag-w|{host}|{rule}|{dec}")
        events.append({"type": "watch_event",
                       "bridge_version": M.BRIDGE_VERSION,
                       "seq": i, "ts": ts, "agent": "ag-w",
                       "host": host, "rule_id": rule, "decision": dec,
                       "prev_entry_sha": prev, "entry_sha": sha})
        prev = sha
    return [M.json.dumps({"type": "watch_manifest", **base},
                         sort_keys=True, separators=(",", ":")),
            *(M.json.dumps(e, sort_keys=True, separators=(",", ":"))
              for e in events),
            M.json.dumps({"type": "watch_close",
                          "bridge_version": M.BRIDGE_VERSION,
                          "entries": 2, "watch_head": prev},
                         sort_keys=True, separators=(",", ":"))]


def test_verify_feed_clean_ok():
    ok, msg = M.verify_feed(_bundle())
    assert ok is True
    assert "SAĞLAM" in msg


def test_verify_feed_tampered_rejected():
    bad = list(_bundle())
    bad[1] = bad[1].replace('"decision":"deny"', '"decision":"allow"')
    ok, msg = M.verify_feed(bad)
    assert ok is False


def test_verify_feed_tamper_reason_zincir():
    bad = list(_bundle())
    bad[1] = bad[1].replace('"decision":"deny"', '"decision":"allow"')
    _, msg = M.verify_feed(bad)
    assert "zincir" in msg


def test_verify_feed_empty_rejected():
    ok, msg = M.verify_feed([])
    assert ok is False and "eksik" in msg


def test_verify_feed_manifest_only_rejected():
    b = _bundle()
    ok, msg = M.verify_feed(b[:1])
    assert ok is False


def test_verify_feed_close_only_rejected():
    b = _bundle()
    ok, msg = M.verify_feed(b[-1:])
    assert ok is False


def test_verify_feed_second_manifest_rejected():
    b = list(_bundle())
    b.append(b[0])
    ok, msg = M.verify_feed(b)
    assert ok is False
    assert "ikinci manifest" in msg


def test_verify_feed_second_close_rejected():
    b = list(_bundle())
    b.append(b[-1])
    ok, msg = M.verify_feed(b)
    assert ok is False
    assert "ikinci close" in msg


def test_verify_feed_bad_json():
    ok, msg = M.verify_feed(["not json{", b"{"] if False else ["not json"])
    assert ok is False
    assert "JSON bozuk" in msg


def test_verify_feed_blank_lines_skipped():
    b = _bundle()
    ok, _ = M.verify_feed(["", "   ", *b])
    assert ok is True


def test_verify_feed_wrong_bridge_version():
    b = _bundle()
    b[0] = b[0].replace('"bridge_version":1', '"bridge_version":2')
    ok, msg = M.verify_feed(b)
    assert ok is False
    assert "bridge_version" in msg


def test_verify_feed_wrong_source_rejected():
    b = _bundle()
    b[0] = b[0].replace('"source":"sikke"', '"source":"other"')
    ok, msg = M.verify_feed(b)
    assert ok is False
    assert "kaynak" in msg


def test_verify_feed_unknown_type():
    b = list(_bundle())
    b.insert(1, M.json.dumps({"type": "weird", "bridge_version": 1}))
    ok, msg = M.verify_feed(b)
    assert ok is False
    assert "bilinmeyen tip" in msg


def test_verify_feed_event_before_manifest():
    b = _bundle()
    ok, msg = M.verify_feed([b[1]])
    assert ok is False
    assert "manifest'siz" in msg


def test_verify_feed_entries_mismatch():
    b = _bundle()
    b[-1] = b[-1].replace('"entries":2', '"entries":9')
    ok, msg = M.verify_feed(b)
    assert ok is False
    assert "entries" in msg


def test_verify_feed_watch_head_mismatch():
    b = _bundle()
    b[-1] = b[-1].replace('"watch_head":"', '"watch_head":"0')
    ok, msg = M.verify_feed(b)
    assert ok is False
    assert "watch_head" in msg


def test_verify_feed_returns_tuple():
    ok, msg = M.verify_feed(_bundle())
    assert isinstance((ok, msg), tuple)
    assert isinstance(msg, str)


# -- main ---------------------------------------------------------------------------------

def test_main_selftest_flag():
    assert M.main(["prog", "--selftest"]) == 0


def test_main_no_args_returns_2():
    assert M.main(["prog"]) == 2


def test_main_too_many_args_returns_2():
    assert M.main(["prog", "a", "b"]) == 2


# -- tekrar ---------------------------------------------------------------------------------

def test_repeatable():
    assert M._selftest() == M._selftest() == 0
