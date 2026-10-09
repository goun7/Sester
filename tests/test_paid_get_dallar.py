"""fastapi_client_demo.paid_get dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Dış çağrı YOK: httpx.Client stub (gercek gateway YOK).
"""
import importlib.util
import json
import os

import pytest

_spec = importlib.util.spec_from_file_location(
    "demo", os.path.join("examples", "fastapi_client_demo.py"))
_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_demo)
paid_get = _demo.paid_get
GATEWAY = _demo.GATEWAY


class _Resp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code = status
        self._body = body if body is not None else {"ok": True}
        self.text = text

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class _FakeClient:
    def __init__(self, resp=None):
        self.resp = resp or _Resp()
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, headers, timeout))
        return self.resp


def _run(resp=None):
    c = _FakeClient(resp)
    r = paid_get(c, "/weather/istanbul")
    return r, c


# -- 200 ---------------------------------------------------------------------------------

def test_200_returns_json():
    r, _ = _run(_Resp(200, {"data": "gunesli"}))
    assert r == {"data": "gunesli"}


def test_200_returns_dict():
    r, _ = _run()
    assert isinstance(r, dict)


def test_200_body_passthrough():
    r, _ = _run(_Resp(200, {"x": [1, 2, 3]}))
    assert r["x"] == [1, 2, 3]


def test_url_built_from_gateway():
    _, c = _run()
    assert c.calls[0][0] == f"{GATEWAY}/weather/istanbul"


def test_payment_header_sent():
    _, c = _run()
    assert "X-Payment" in c.calls[0][1]


def test_payment_header_resource_from_path():
    _, c = _run()
    assert c.calls[0][1]["X-Payment"].startswith("Sester-EVM ")


def test_timeout_10():
    _, c = _run()
    assert c.calls[0][2] == 10


def test_deep_path_resource():
    _, c = _run(_Resp(200))
    paid_get(c, "/a/b/c/d")
    assert "/a/b/c/d" in c.calls[-1][0]


# -- 402 ---------------------------------------------------------------------------------

def test_402_returns_none():
    r, _ = _run(_Resp(402, {"error": "yetersiz"}))
    assert r is None


def test_402_json_error_printed(capsys):
    _run(_Resp(402, {"error": "kota-doldu"}))
    assert "kota-doldu" in capsys.readouterr().out


def test_402_rejected_message(capsys):
    _run(_Resp(402, {"error": "x"}))
    assert "reddedildi" in capsys.readouterr().out


def test_402_non_json_body(capsys):
    _run(_Resp(402, body=json.JSONDecodeError("no json","d",0), text="hata-sayfasi"))
    out = capsys.readouterr().out
    assert "hata-sayfasi" in out


def test_402_non_json_truncated(capsys):
    _run(_Resp(402, body=json.JSONDecodeError("x","d",0),
               text="A" * 500))
    out = capsys.readouterr().out
    assert "A" * 120 in out
    assert "A" * 121 not in out


def test_402_empty_body(capsys):
    _run(_Resp(402, body=json.JSONDecodeError("x","d",0), text=""))
    assert "reddedildi" in capsys.readouterr().out


def test_402_no_data_returned():
    r, _ = _run(_Resp(402, {"data": "gizli"}))
    assert r is None


# -- diger status ---------------------------------------------------------------------------------

def test_500_raises_runtime():
    with pytest.raises(RuntimeError):
        _run(_Resp(500))


def test_500_message_has_status():
    with pytest.raises(RuntimeError, match="500"):
        _run(_Resp(500))


def test_403_raises():
    with pytest.raises(RuntimeError):
        _run(_Resp(403))


def test_404_raises():
    with pytest.raises(RuntimeError):
        _run(_Resp(404))


def test_502_raises():
    with pytest.raises(RuntimeError):
        _run(_Resp(502))


# -- client etkilesimi ---------------------------------------------------------------------------------

def test_client_called_once():
    _, c = _run()
    assert len(c.calls) == 1


def test_repeatable():
    a, _ = _run()
    b, _ = _run()
    assert a == b


def test_two_paths_two_calls():
    c = _FakeClient(_Resp(200))
    paid_get(c, "/a")
    paid_get(c, "/b")
    assert len(c.calls) == 2


def test_two_paths_different_urls():
    c = _FakeClient(_Resp(200))
    paid_get(c, "/a")
    paid_get(c, "/b")
    assert c.calls[0][0] != c.calls[1][0]


def test_no_leading_slash_handling():
    c = _FakeClient(_Resp(200))
    paid_get(c, "/x")
    assert c.calls[0][0].endswith("/x")


def test_payment_header_varies_by_path():
    c = _FakeClient(_Resp(200))
    paid_get(c, "/weather/istanbul")
    h1 = c.calls[0][1]["X-Payment"]
    paid_get(c, "/weather/ankara")
    h2 = c.calls[1][1]["X-Payment"]
    assert h1 != h2
