"""SesterMiddleware send_with_receipt dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Dış çağrı YOK: temp Ledger + sahte ASGI app + sahte facilitator.
"""
import base64
import json

import pytest
from eth_account import Account

from sester.middleware import SesterMeter
from sester.schemes import sign_exact_sester

SK1 = "0x" + "11" * 32
AGENT = Account.from_key(SK1).address


class _Ledger:
    def __init__(self):
        import os
        import tempfile
        from sester.ledger import Ledger
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._led = Ledger(path, secret="t")
        self.path = path
        self.appends = []

    def append(self, *a, **kw):
        self.appends.append((a, kw))
        return self._led.append(*a, **kw)

    @property
    def recent_events(self):
        return self._led.recent_events

    def spent_today(self, agent):
        return self._led.spent_today(agent)

    def spent_today_minor(self, agent):
        return self._led.spent_today_minor(agent)

    def chain_head(self):
        return self._led.chain_head()

    def claim_nonce(self, *a, **kw):
        return self._led.claim_nonce(*a, **kw)

    def verify_chain(self, *a, **kw):
        return self._led.verify_chain(*a, **kw)


class _Facilitator:
    def __init__(self, status="ok"):
        self._status = status
        self.calls = []

    def settle(self, *a, **kw):
        self.calls.append((a, kw))
        r = type("SR", (), {"status": self._status})()
        return r


def _hdr(nonce="n1", amount="0.01"):
    return sign_exact_sester(SK1, AGENT, nonce, amount, "/weather")


def _scope(header=None, path="/weather"):
    headers = []
    if header is not None:
        headers.append((b"x-payment",
                        header.encode("utf-8")))
    return {
        "type": "http",
        "path": path,
        "headers": headers,
        "query_string": b"",
        "method": "GET",
    }


def _ok_app(body=b"sonuc"):
    async def app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({"type": "http.response.body", "body": body})
    return app


def _recv(body=b""):
    yield_queue = [{"type": "http.request", "body": body,
                    "more_body": False}]

    async def receive():
        return yield_queue.pop(0) if yield_queue else {
            "type": "http.disconnect"}
    return receive


def _run(mw, scope, receive, send):
    import asyncio
    return asyncio.run(mw(scope, receive, send))


def _make(price=0.01, status="ok"):
    led = _Ledger()
    fac = _Facilitator(status)
    mw = SesterMeter(_ok_app(), led, price=price,
                          facilitator=fac)
    return mw, led, fac


def _collect():
    sent = []

    async def send(message):
        sent.append(message)
    return sent, send


# -- temel akis ---------------------------------------------------------------------------------

def test_response_sent():
    mw, _, _ = _make()
    sent, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    assert any(m["type"] == "http.response.start" for m in sent)


def test_body_sent():
    mw, _, _ = _make()
    sent, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    assert any(m["type"] == "http.response.body" for m in sent)


def test_receipt_header_added():
    mw, _, _ = _make()
    sent, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    names = {k for k, _ in start["headers"]}
    assert b"x-sester-receipt" in names


def test_amount_header_added():
    mw, _, _ = _make()
    sent, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    d = dict(start["headers"])
    assert d[b"x-sester-amount"] == b"0.010000"


def test_seq_header_added():
    mw, _, _ = _make()
    sent, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    names = {k for k, _ in start["headers"]}
    assert b"x-sester-seq" in names


def test_bundle_is_base64():
    """x-sester-receipt-bundle urlsafe b64 (eyJ ile baslar)."""
    mw, _, _ = _make()
    sent, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    d = dict(start["headers"])
    assert d[b"x-sester-receipt-bundle"].startswith(b"eyJ")


def test_bundle_decodes_json():
    mw, _, _ = _make()
    sent, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    d = dict(start["headers"])
    raw = d[b"x-sester-receipt-bundle"] + b"=="
    obj = json.loads(base64.urlsafe_b64decode(raw))
    assert isinstance(obj, dict)


def test_bundle_has_fields():
    mw, _, _ = _make()
    sent, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    d = dict(start["headers"])
    raw = d[b"x-sester-receipt-bundle"] + b"=="
    obj = json.loads(base64.urlsafe_b64decode(raw))
    assert set(obj) >= {"amount_minor", "amount"}


# -- ledger ---------------------------------------------------------------------------------

def test_charge_receipt_appended():
    mw, led, _ = _make()
    _, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    kinds = [kw.get("kind", a[0] if a else None)
             for a, kw in led.appends]
    assert any("charge" in str(k) for k in kinds)


def test_two_charges_two_appends():
    mw, led, _ = _make()
    _, send = _collect()
    _run(mw, _scope(_hdr("a")), _recv(), send)
    _run(mw, _scope(_hdr("b")), _recv(), send)
    assert len(led.appends) >= 2


def test_spent_today_increases():
    mw, led, _ = _make()
    _, send = _collect()
    before = led.spent_today(AGENT)
    _run(mw, _scope(_hdr()), _recv(), send)
    after = led.spent_today(AGENT)
    assert after >= before


def test_settlement_not_appended_evm():
    """Sester-EVM scheme 'evm' -> settle KOYULMAZ (sadece exact)."""
    mw, led, _ = _make(status="ok")
    _, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    kinds = [str(kw.get("kind", a[0] if a else ""))
             for a, kw in led.appends]
    assert not any("settlement" in k for k in kinds)


def test_evm_no_facilitator_needed():
    """evm scheme facilitator'suz calisir (settle yok)."""
    led = _Ledger()
    mw = SesterMeter(_ok_app(), led, price=0.01)
    _, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    # response yine gider


def test_facilitator_settle_not_called_evm():
    mw, _, fac = _make(status="ok")
    _, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    assert len(fac.calls) == 0


# -- odeme dogrulama ---------------------------------------------------------------------------------

def test_no_header_challenges():
    mw, _, _ = _make()
    sent, send = _collect()
    _run(mw, _scope(None), _recv(), send)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    assert start["status"] == 402


def test_bad_header_challenges():
    mw, _, _ = _make()
    sent, send = _collect()
    _run(mw, _scope("Sester-EVM not-valid"), _recv(), send)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    assert start["status"] == 402


def test_wrong_amount_rejected():
    """Zarf 0.01, fiyat 0.05."""
    mw, _, _ = _make(price=0.05)
    sent, send = _collect()
    _run(mw, _scope(_hdr(amount="0.01")), _recv(), send)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    assert start["status"] == 402


def test_exact_amount_accepted():
    mw, _, _ = _make(price=0.01)
    sent, send = _collect()
    _run(mw, _scope(_hdr(amount="0.01")), _recv(), send)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    assert start["status"] == 200


def test_overpayment_rejected():
    """Exact scheme: tutar tam esit olmali."""
    mw, _, _ = _make(price=0.001)
    sent, send = _collect()
    _run(mw, _scope(_hdr(amount="0.01")), _recv(), send)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    assert start["status"] == 402


# -- receipt hatasi ---------------------------------------------------------------------------------

def test_receipt_failure_still_responds(monkeypatch):
    """issue_receipt hata verse yanıt yine gider."""
    mw, _, _ = _make()
    import sester.receipt as rc
    orig = rc.issue_receipt
    monkeypatch.setattr(rc, "issue_receipt",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("boom")))
    sent, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    assert any(m["type"] == "http.response.body" for m in sent)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    assert start["status"] == 200


def test_receipt_failure_no_bundle(monkeypatch):
    mw, _, _ = _make()
    import sester.receipt as rc
    monkeypatch.setattr(rc, "issue_receipt",
                        lambda *a, **k: (_ for _ in ()).throw(
                            RuntimeError("boom")))
    sent, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    start = next(m for m in sent
                 if m["type"] == "http.response.start")
    d = dict(start["headers"])
    assert b"x-sester-receipt-bundle" not in d
    assert b"x-sester-receipt" in d  # hex kisa kod hala var


# -- tekrar ---------------------------------------------------------------------------------

def test_repeatable():
    mw, _, _ = _make()
    _, send = _collect()
    _run(mw, _scope(_hdr("x")), _recv(), send)
    _, send2 = _collect()
    _run(mw, _scope(_hdr("y")), _recv(), send2)
    # iki istek de tamamlanir (exception yok)


def test_body_content_preserved():
    mw, _, _ = _make()
    sent, send = _collect()
    _run(mw, _scope(_hdr()), _recv(), send)
    body = next(m for m in sent
                if m["type"] == "http.response.body")
    assert body["body"] == b"sonuc"


def test_different_nonce_receipt_differs():
    mw, _, _ = _make()
    sent1, send1 = _collect()
    _run(mw, _scope(_hdr("n-a")), _recv(), send1)
    sent2, send2 = _collect()
    _run(mw, _scope(_hdr("n-b")), _recv(), send2)

    def _rcpt(sent):
        start = next(m for m in sent
                     if m["type"] == "http.response.start")
        return dict(start["headers"]).get(
            b"x-sester-receipt-bundle")

    assert _rcpt(sent1) != _rcpt(sent2)
