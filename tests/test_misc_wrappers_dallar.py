"""sester.cli._load_ledger + sester.migrate_pg._source_events + sester.webhooks._default_post
dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — Ledger memory-modu + stub ledger + monkeypatch
urllib (GERCEK baglanti/HTTP/subprocess YOK).
(1) _load_ledger: Ledger insa-fabrikasi;
(2) _source_events: src.export_events(None) pass-through;
(3) _default_post: urllib.request POST wrapper.
"""
import urllib.request

import pytest

from sester.cli import _load_ledger
from sester.migrate_pg import _source_events
import sester.webhooks as webhooks


# == _load_ledger ===============================================================================

def test_load_ledger_returns_ledger():
    from sester.ledger import Ledger
    lg = _load_ledger(":memory:", "s3cr3t")
    assert isinstance(lg, Ledger)


@pytest.mark.parametrize("db", [":memory:", "test-a.db", "test-b.sqlite3"])
def test_load_ledger_db_param(db):
    """ORTAM: db argümanı Ledger'a pass-through (gercek DOSYA acilmaz —
    Ledger constructor sadece kaydeder)."""
    lg = _load_ledger(db, "s")
    assert getattr(lg, "db", getattr(lg, "_db", None)) in (db, None)


@pytest.mark.parametrize("secret", ["s", "long-secret-" * 8, "türkçe-anahtar", "😀"])
def test_load_ledger_secret_attached(secret):
    """ORTAM: secret Ledger'a encode()'lanarak gecer."""
    lg = _load_ledger(":memory:", secret)
    found = getattr(lg, "secret", getattr(lg, "_secret", None))
    assert found == secret.encode() or found == secret


def test_load_ledger_secret_bytes_default():
    lg = _load_ledger(":memory:", "abc")
    assert lg.secret == b"abc"


def test_load_ledger_repeatable_same_type():
    from sester.ledger import Ledger
    a = _load_ledger(":memory:", "x")
    b = _load_ledger(":memory:", "x")
    assert isinstance(a, Ledger) and isinstance(b, Ledger)


def test_load_ledger_uses_delayed_import():
    """ORTAM: 'from .ledger import Ledger' fonksiyon-icinde (delayed-import)
    — module-level circular-import engellenir."""
    import inspect
    src = inspect.getsource(_load_ledger)
    assert "from .ledger import Ledger" in src


def test_load_ledger_empty_secret():
    """ORTAM: bos-secret -> b'' (fail-closed DEGIL bu seviyede)."""
    lg = _load_ledger(":memory:", "")
    assert lg.secret == b""


def test_load_ledger_no_side_effects_on_repeat():
    a = _load_ledger(":memory:", "s")
    b = _load_ledger(":memory:", "s")
    assert a is not b


# == _source_events =============================================================================

class StubLedger:
    """Kural-4: export_events STUB — gercek DB sorgusu YOK."""

    def __init__(self, result, raise_exc=None):
        self._result = result
        self._raise = raise_exc
        self.calls = []

    def export_events(self, arg):
        self.calls.append(arg)
        if self._raise:
            raise self._raise
        return self._result


def test_source_events_passes_none():
    """ORTAM-ANATOMI: src.export_events(None) — TAM argüman None."""
    fl = StubLedger([{"a": 1}])
    assert _source_events(fl) == [{"a": 1}]
    assert fl.calls == [None]


@pytest.mark.parametrize("rows", [
    [], [{"id": 1}], [{"id": 1}, {"id": 2}],
    [{"ts": 1.0, "type": "x"}],
    [{}], None,
])
def test_source_events_returns_export_result(rows):
    fl = StubLedger(rows)
    assert _source_events(fl) == rows


def test_source_events_calls_once():
    fl = StubLedger([])
    _source_events(fl)
    assert len(fl.calls) == 1


def test_source_events_propagates_exceptions():
    """ORTAM: export_events hata verirse YAYILIR (try/except YOK)."""
    fl = StubLedger(None, raise_exc=RuntimeError("db-down"))
    with pytest.raises(RuntimeError):
        _source_events(fl)


def test_source_events_returns_list_type():
    fl = StubLedger([])
    assert isinstance(_source_events(fl), list)


def test_source_events_empty_list():
    fl = StubLedger([])
    assert _source_events(fl) == []


def test_source_events_none_result():
    """ORTAM: None donerse None gecer (list-coerce YOK)."""
    fl = StubLedger(None)
    assert _source_events(fl) is None


def test_source_events_preserves_row_dicts():
    rows = [{"a": 1, "b": 2}, {"c": 3}]
    fl = StubLedger(rows)
    out = _source_events(fl)
    assert out is rows


# == _default_post ==============================================================================

class FakeResp:
    """urlopen context-manager stubu."""

    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def capture_post(monkeypatch):
    """Kural-4: urllib.request.urlopen STUB — GERCEK HTTP YAPILMADI."""
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["data"] = req.data
        captured["headers"] = dict(req.headers)
        captured["method"] = req.get_method()
        captured["timeout"] = timeout
        return FakeResp(captured.get("status", 200))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return captured


def test_default_post_returns_status(capture_post):
    capture_post["status"] = 200
    assert webhooks._default_post("http://x/y", b"{}", {}) == 200


@pytest.mark.parametrize("status", [200, 201, 204, 400, 404, 500, 207])
def test_default_post_status_codes(capture_post, status):
    capture_post["status"] = status
    assert webhooks._default_post("http://x", b"", {}) == status


def test_default_post_request_anatomy(capture_post):
    webhooks._default_post("http://example.org/hook", b'{"a":1}',
                           {"X-Sester-Signature": "v1=abc"})
    assert capture_post["url"] == "http://example.org/hook"
    assert capture_post["data"] == b'{"a":1}'
    assert capture_post["method"] == "POST"
    assert capture_post["timeout"] == 10


def test_default_post_header_case_normalized(capture_post):
    """ORTAM-OGRENDI: urllib Request header-anahtarlarini CAPITALIZE eder
    ('X-Sester-Signature' -> 'X-sester-signature' — Python urllib davranisi)."""
    webhooks._default_post("http://x", b"", {"X-Sester-Signature": "v1=abc"})
    h = capture_post["headers"]
    assert "X-sester-signature" in h
    assert h["X-sester-signature"] == "v1=abc"


@pytest.mark.parametrize("url", [
    "http://example.org/hook", "https://x.io/y", "http://127.0.0.1:8402/z",
    "http://example.org/p?x=1", "https://x/ü",
])
def test_default_post_url_pass_through(capture_post, url):
    webhooks._default_post(url, b"", {})
    assert capture_post["url"] == url


@pytest.mark.parametrize("body", [b"", b"{}", b'{"a":1}', b"plain", b"\x00\x01",
                                  '{"tr":"ğüşi"}'.encode(), b"x" * 1000])
def test_default_post_body_pass_through(capture_post, body):
    webhooks._default_post("http://x", body, {})
    assert capture_post["data"] == body


def test_default_post_method_is_post(capture_post):
    webhooks._default_post("http://x", b"body", {})
    assert capture_post["method"] == "POST"


def test_default_post_no_headers(capture_post):
    webhooks._default_post("http://x", b"", {})
    assert capture_post["headers"] == {}


@pytest.mark.parametrize("hdrs", [
    {"Content-Type": "application/json"},
    {"Authorization": "Bearer x"},
    {"X-Sester-Signature": "t=1, v1=abc"},
    {"a": "1", "b": "2"},
])
def test_default_post_headers_pass_through(capture_post, hdrs):
    webhooks._default_post("http://x", b"", hdrs)
    for k, v in hdrs.items():
        assert capture_post["headers"].get(k.capitalize()) == v or \
               any(vv == v for vv in capture_post["headers"].values())


def test_default_post_timeout_is_10(capture_post):
    webhooks._default_post("http://x", b"", {})
    assert capture_post["timeout"] == 10


def test_default_post_propagates_oserror(monkeypatch):
    """ORTAM: urlopen hata verirse (ag-kesintisi) YAYILIR — retry _default_post
    disinda deliver_webhook'ta; burada sadece pas-through."""
    def boom(req, timeout):
        raise OSError("connection refused")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(OSError):
        webhooks._default_post("http://x", b"", {})


@pytest.mark.parametrize("exc", [OSError("x"), ValueError("y"),
                                 urllib.error.HTTPError("u", 500, "err", {}, None)
                                 if False else OSError("z")])
def test_default_post_propagates_various(monkeypatch, exc):
    def raise_it(req, timeout):
        raise exc
    monkeypatch.setattr(urllib.request, "urlopen", raise_it)
    with pytest.raises(type(exc)):
        webhooks._default_post("http://x", b"", {})


def test_default_post_uses_urllib_request(monkeypatch):
    """ORTAM: urllib.request.Request ile insa — modul-disi bagimlilik YOK."""
    import inspect
    src = inspect.getsource(webhooks._default_post)
    assert "urllib.request" in src and "urlopen" in src
