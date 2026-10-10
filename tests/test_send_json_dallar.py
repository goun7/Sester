"""middleware._send_json dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory; async send STUBLU (gercek ASGI YOK).
"""
import asyncio
import json

import pytest

from sester.middleware import SesterMeter


class _FakeSend:
    def __init__(self):
        self.messages = []

    async def __call__(self, msg):
        self.messages.append(msg)

    @property
    def start(self):
        return next(m for m in self.messages if m["type"] == "http.response.start")

    @property
    def body(self):
        return next(m for m in self.messages if m["type"] == "http.response.body")

    def headers_dict(self):
        return {k: v for k, v in self.start["headers"]}


def _send_json(mw, send, status=200, payload=None, extra=None):
    return asyncio.run(mw._send_json(send, status, payload or {}, extra))


def _make_mw():
    """Middleware'i __init__'siz kur (sadece _send_json gerekli)."""
    return SesterMeter.__new__(SesterMeter)


# -- mutlu-yol ---------------------------------------------------------------------------------

def test_sends_two_messages():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {"ok": True})
    assert len(send.messages) == 2
    assert send.messages[0]["type"] == "http.response.start"
    assert send.messages[1]["type"] == "http.response.body"


def test_status_propagated():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 402, {"error": "pay"})
    assert send.start["status"] == 402


def test_status_200():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {})
    assert send.start["status"] == 200


def test_status_variants():
    mw = _make_mw()
    for st in (200, 400, 401, 402, 403, 404, 500):
        s = _FakeSend()
        _send_json(mw, s, st, {})
        assert s.start["status"] == st


def test_body_encoded():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {"a": 1})
    assert json.loads(send.body["body"].decode()) == {"a": 1}


def test_body_is_bytes():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {})
    assert isinstance(send.body["body"], bytes)


# -- headers ---------------------------------------------------------------------------------

def test_content_type_header():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {})
    assert send.headers_dict()[b"content-type"] == b"application/json; charset=utf-8"


def test_content_length_header():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {"a": 1})
    expected = len(json.dumps({"a": 1}, ensure_ascii=False).encode())
    assert send.headers_dict()[b"content-length"] == str(expected).encode()


def test_content_length_matches_body():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {"hello": "world"})
    assert int(send.headers_dict()[b"content-length"]) == len(send.body["body"])


def test_extra_headers_added():
    mw = _make_mw()
    send = _FakeSend()
    # extra_headers: (str, str) -> k.encode()/v.encode()
    _send_json(mw, send, 200, {}, [("X-Test", "yes")])
    assert send.headers_dict()[b"x-test"] == b"yes"


def test_extra_headers_lowercased():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {}, [("X-Mixed-Case", "v")])
    assert b"x-mixed-case" in send.headers_dict()


def test_extra_headers_multiple():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {}, [("A", "1"), ("B", "2")])
    assert send.headers_dict()[b"a"] == b"1"
    assert send.headers_dict()[b"b"] == b"2"


def test_extra_headers_none_ok():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {}, None)
    assert len(send.start["headers"]) == 2


def test_extra_headers_empty():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {}, [])
    assert len(send.start["headers"]) == 2


def test_extra_header_overrides_content_type():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {}, [("Content-Type", "text/plain")])
    assert send.headers_dict()[b"content-type"] == b"text/plain"


def test_header_values_bytes():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {}, [("K", "V")])
    for k, v in send.start["headers"]:
        assert isinstance(k, bytes) and isinstance(v, bytes)


# -- unicode ---------------------------------------------------------------------------------

def test_turkish_chars_in_body():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {"msg": "ödeeme reddi: işlem"})
    d = json.loads(send.body["body"].decode())
    assert d["msg"] == "ödeeme reddi: işlem"


def test_ensure_ascii_false():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {"m": "ç"})
    assert send.body["body"].decode("utf-8") == '{"m": "ç"}'


def test_content_length_reflects_unicode():
    """content-length BYTES sayar (utf-8)."""
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {"m": "ç"})
    body = send.body["body"]
    assert int(send.headers_dict()[b"content-length"]) == len(body)


# -- payload ---------------------------------------------------------------------------------

def test_empty_payload():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {})
    assert json.loads(send.body["body"]) == {}


def test_nested_payload():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {"a": {"b": [1, 2, {"c": None}]}})
    assert json.loads(send.body["body"])["a"]["b"][2]["c"] is None


def test_payload_with_list():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {"xs": [1, 2, 3]})
    assert json.loads(send.body["body"])["xs"] == [1, 2, 3]


def test_payload_none_value():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {"n": None})
    assert json.loads(send.body["body"])["n"] is None


# -- tekrar ---------------------------------------------------------------------------------

def test_repeatable():
    mw = _make_mw()
    s1, s2 = _FakeSend(), _FakeSend()
    _send_json(mw, s1, 200, {"a": 1})
    _send_json(mw, s2, 200, {"a": 1})
    assert s1.body["body"] == s2.body["body"]


def test_call_order():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {})
    assert send.messages[0]["type"] == "http.response.start"
    assert send.messages[1]["type"] == "http.response.body"


def test_independent_sends():
    mw = _make_mw()
    a, b = _FakeSend(), _FakeSend()
    _send_json(mw, a, 200, {"v": 1})
    _send_json(mw, b, 200, {"v": 2})
    assert json.loads(a.body["body"])["v"] == 1
    assert json.loads(b.body["body"])["v"] == 2


# -- send-protocol ---------------------------------------------------------------------------------

def test_send_awaited():
    """send coroutine olmali (async def)."""
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {})
    assert send.messages[1]["body"] is not None


def test_start_message_keys():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {})
    assert set(send.start) >= {"type", "status", "headers"}


def test_body_message_keys():
    mw = _make_mw()
    send = _FakeSend()
    _send_json(mw, send, 200, {})
    assert set(send.body) >= {"type", "body"}
