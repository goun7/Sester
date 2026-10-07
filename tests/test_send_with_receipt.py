"""send_with_receipt — middleware'in ödeme-kanıtı zarfını taşıyan closure'ı.

middleware.py:509'daki iç fonksiyon; ödeme zaten ledger'a yazıldıktan sonra
downstream ASGI send()'inin etrafına sarılır. Görevi yanıtı HİÇ geciktirmeden
alıcıya bağımsız-doğrulanabilir kanıtı iletmektir:

  · http.response.start üzerine (ve yalnızca oraya) x-sester-receipt,
    x-sester-amount, x-sester-seq ve tam kanıt zarfı x-sester-receipt-bundle
    başlıklarını damgalar;
  · damgalama TEK seferliktir (_stamped) — birden-fazla response.start
    görünse bile kanıt bir kere eklenir;
  · kanıt-üretim hatası yanıtı GECİKTİRMEZ (ödeme zaten alındı; hata
    denetim-izi olarak receipt_fail_total sayacına + stderr'e yansır);
  · exact şemasında handler başladıysa facilitator.settle TAM olarak bir kez
    çağrılır; geçici-on-chain-hata done-bayrağını setlemez (AT-174-düzeltmesi)
    böylece bir sonraki istekte tekrar denenebilir.

Mevcut testler (test_receipt.py) zarfın bütünlüğünü ve secret'sız
doğrulanabilirliğini sabitler; bu dosya TAŞIYICI closure'ın kendi
davranışlarını sabitler: damgalama-yeri, tek-seferliklik, hata-yolu-gecikmez,
settle-bir-kez + yeniden-denenebilir, gövde-dokunulmaz. Standart-test-
araçları (gerçek ASGI akışı, FakeTransport'lı facilitator, tmp ledger);
dış-çağrı yok.
"""
from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import time

import pytest

from sester import Ledger, load_receipt_json, verify_receipt
from sester.facilitator import Facilitator, FakeTransport
from sester.middleware import SesterMeter
from sester.schemes import ExactSesterV2

from eth_account import Account

# exact (EVM) zarfları için deterministik-anahtar çifti
SK1 = "0x" + "11" * 32
ADDR1 = Account.from_key(SK1).address.lower()


def _exact_header(nonce="sn1", amount_usd=0.05, resource="/data", sk=SK1):
    """EIP-712-imzalı geçerli exact zarfı; middleware'in verify_local'ından
    geçer ve facilitator'un /verify aşaması FakeTransport ile kabul eder."""
    return ExactSesterV2.client_header(
        from_addr=ADDR1, to_addr="0x" + "33" * 20,
        amount_usd=amount_usd, private_key=sk, resource=resource,
        nonce_hex=nonce)


# ------------------------------------------------------------------ helpers
def _asgi_app(body=b'{"ok": true}', status=200):
    """Küçük dürüst ASGI uygulaması: start + body yollar."""
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
    return app


def _scope(payment, path="/data"):
    return {"type": "http", "method": "GET", "path": path,
            "headers": [(b"x-payment", payment.encode())]}


def _pugio(agent, nonce, amount, resource, secret="mw-secret"):
    mac = _hmac.new(secret.encode(),
                    f"{agent}|{nonce}|{amount}|{resource}".encode(),
                    hashlib.sha256).hexdigest()
    return f"pugio0 {agent}:{nonce}:{amount}:{mac}"


def _capture():
    """Gönderilen her ASGI mesajını kaydeden send(); start'ların kopyası da
    saklanır çünkü closure mesajı yerinde (in-place) değiştirmez."""
    sent = []

    async def send(m):
        sent.append({k: (list(v) if k == "headers" else v)
                     for k, v in m.items()})

    return send, sent


def _start_headers(sent):
    start = next(m for m in sent if m["type"] == "http.response.start")
    return dict((k.decode(), v.decode()) for k, v in start["headers"])


# ============================================================ damgalama-yeri
def test_receipt_headers_stamped_only_on_response_start(tmp_path):
    """Kanıt başlıkları http.response.start'a damgalanır; http.response.body
    mesajlarına HİÇ dokunulmaz — gövde downstream'indiği gibi iletilir."""
    import asyncio

    led = Ledger(str(tmp_path / "swr1.sqlite3"), secret="mw-secret")
    body = b'{"ok": true}'
    meter = SesterMeter(_asgi_app(body), ledger=led, price=0.05,
                        daily_quota=1.0, secret="mw-secret",
                        receipt_node_secret="node-k")
    pay = _pugio("ag-a", "n1", "0.05", "/data")
    send, sent = _capture()

    asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))

    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 200
    hdr = dict((k.decode(), v.decode()) for k, v in start["headers"])
    assert "x-sester-receipt" in hdr
    assert "x-sester-amount" in hdr
    assert "x-sester-seq" in hdr
    assert "x-sester-receipt-bundle" in hdr
    # gövde mesajı birebir aynı kaldı
    body_msg = next(m for m in sent if m["type"] == "http.response.body")
    assert body_msg["body"] == body
    assert b"x-sester-receipt" not in body_msg["body"]
    assert "headers" not in body_msg
    led.close()


def test_stamp_is_idempotent_across_multiple_response_starts(tmp_path):
    """_stamped bayrağı damgalamayı TEK seferlik kılar: downstream uygulama
    birden-fazla http.response.start gönderse bile kanıt bir kere eklenir."""
    import asyncio

    async def app(scope, receive, send):
        # nadir ama geçerli: yeniden-yazılan başlangıç (chunked / SSE reset)
        for _ in range(2):
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": b"{}"})

    led = Ledger(str(tmp_path / "swr2.sqlite3"), secret="mw-secret")
    meter = SesterMeter(app, ledger=led, price=0.05, daily_quota=1.0,
                        secret="mw-secret")
    pay = _pugio("ag-b", "n2", "0.05", "/data")
    send, sent = _capture()

    asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))

    starts = [m for m in sent if m["type"] == "http.response.start"]
    assert len(starts) == 2
    first = dict((k.decode(), v.decode()) for k, v in starts[0]["headers"])
    second = dict((k.decode(), v.decode()) for k, v in starts[1]["headers"])
    assert "x-sester-receipt" in first
    assert "x-sester-receipt" not in second
    led.close()


def test_amount_and_seq_headers_match_the_ledger_record(tmp_path):
    """Damgalanan değerler ledger'daki CHARGE kaydından gelir; uydurma
    değildir — seq ve amount alıcı tarafından yeniden-hesaplanabilir."""
    import asyncio

    led = Ledger(str(tmp_path / "swr3.sqlite3"), secret="mw-secret")
    meter = SesterMeter(_asgi_app(), ledger=led, price=0.05,
                        daily_quota=1.0, secret="mw-secret")
    pay = _pugio("ag-c", "n3", "0.05", "/data")
    send, sent = _capture()

    asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))
    hdr = _start_headers(sent)

    rows = led.export_events("ag-c")
    charge = next(r for r in rows if r["event_type"] == "charge_receipt")
    assert hdr["x-sester-amount"] == f"{charge['amount']:.6f}"
    assert hdr["x-sester-seq"] == str(charge["seq"])
    assert hdr["x-sester-receipt"] == charge["hash"][:16]
    led.close()


# ============================================================ kanıt zarfı
def test_bundle_is_secretlessly_verifiable(tmp_path):
    """x-sester-receipt-bundle'dan çıkarılan kanıt node-secret VERİLMEDEN
    doğrulanır — alıcı Sester/node-secret bağımlılığı olmadan kanıtlar."""
    import asyncio

    led = Ledger(str(tmp_path / "swr4.sqlite3"), secret="mw-secret")
    meter = SesterMeter(_asgi_app(), ledger=led, price=0.05,
                        daily_quota=1.0, secret="mw-secret",
                        receipt_node_secret="node-k",
                        receipt_node_id="node-y")
    pay = _pugio("ag-d", "n4", "0.05", "/data")
    send, sent = _capture()

    asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))
    blob = _start_headers(sent)["x-sester-receipt-bundle"]
    r = load_receipt_json(base64.urlsafe_b64decode(
        blob + "=" * (-len(blob) % 4)))

    ok, msg = verify_receipt(r)
    assert ok, msg
    assert r["iss"] == "node-y"
    assert r["sub"] == "ag-d"
    led.close()


def test_bundle_carries_the_node_cosign_when_secret_given(tmp_path):
    """node-secret verilince zarf cosign taşır; yanlış-anahtar doğrulamaz
    ama asıl kanıt yine secret'sız doğrulanır (iki-bağlantı)."""
    import asyncio

    led = Ledger(str(tmp_path / "swr5.sqlite3"), secret="mw-secret")
    meter = SesterMeter(_asgi_app(), ledger=led, price=0.05,
                        daily_quota=1.0, secret="mw-secret",
                        receipt_node_secret="node-k")
    pay = _pugio("ag-e", "n5", "0.05", "/data")
    send, sent = _capture()

    asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))
    blob = _start_headers(sent)["x-sester-receipt-bundle"]
    r = load_receipt_json(base64.urlsafe_b64decode(
        blob + "=" * (-len(blob) % 4)))

    assert r["node_cosign"]
    assert verify_receipt(r, node_secret="node-k")[0]
    assert not verify_receipt(r, node_secret="other-k")[0]
    assert verify_receipt(r)[0]
    led.close()


# ============================================================ hata-yolu
def test_receipt_failure_does_not_delay_the_response(tmp_path):
    """FAULT: kanıt-üretimi patladığında yanıt YİNE 200 ile gider — ödeme
    zaten ledger'da; gecikme = ödenen-hizmetin- Tutulması. Hata denetim-izi
    olarak receipt_fail_total'a yansır."""
    import asyncio

    led = Ledger(str(tmp_path / "swr6.sqlite3"), secret="mw-secret")
    meter = SesterMeter(_asgi_app(), ledger=led, price=0.05,
                        daily_quota=1.0, secret="mw-secret")
    pay = _pugio("ag-f", "n6", "0.05", "/data")
    send, sent = _capture()

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("sester.receipt.issue_receipt",
                   lambda *a, **k: (_ for _ in ()).throw(
                       RuntimeError("kanot-uretim-patlamasi")))
        asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))

    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 200
    assert meter._metrics.get("receipt_fail_total", 0) >= 1
    # ödeme hâlâ alındı — kanıt-üretim-hatası onu geri-almaz
    rows = led.export_events("ag-f")
    assert any(r["event_type"] == "charge_receipt" for r in rows)
    led.close()


def test_receipt_failure_still_sends_the_downstream_body(tmp_path):
    """Kanıt-üretim hatasında bile downstream gövde eksiksiz iletilir —
    closure'ın hata-yolu yalnızca damgalamayı atlar, akışı bozmaz."""
    import asyncio

    led = Ledger(str(tmp_path / "swr7.sqlite3"), secret="mw-secret")
    body = b'{"ok": true, "n": 42}'
    meter = SesterMeter(_asgi_app(body), ledger=led, price=0.05,
                        daily_quota=1.0, secret="mw-secret")
    pay = _pugio("ag-g", "n7", "0.05", "/data")
    send, sent = _capture()

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("sester.receipt.issue_receipt",
                   lambda *a, **k: (_ for _ in ()).throw(
                       RuntimeError("boom")))
        asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))

    body_msg = next(m for m in sent if m["type"] == "http.response.body")
    assert body_msg["body"] == body
    led.close()


def test_headers_are_not_stamped_when_response_start_never_comes(tmp_path):
    """Downstream hiç response.start göndermezse (early-abort) damgalama
    olmaz — closure start-görmek zorundadır; sessiz-kanıt yok."""
    import asyncio

    async def app(scope, receive, send):
        # start olmadan gövde — kapatma/abort yolu
        await send({"type": "http.response.body", "body": b""})

    led = Ledger(str(tmp_path / "swr8.sqlite3"), secret="mw-secret")
    meter = SesterMeter(app, ledger=led, price=0.05, daily_quota=1.0,
                        secret="mw-secret")
    pay = _pugio("ag-h", "n8", "0.05", "/data")
    send, sent = _capture()

    asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))

    assert not any(m["type"] == "http.response.start" for m in sent)
    for m in sent:
        assert "headers" not in m
        assert b"x-sester" not in m.get("body", b"")
    led.close()


def _payload(row):
    """Ledger'da payload JSON-dize olarak saklanır (kanıt-hash'lenebilir);
    testlerde karşılaştırmak için açarız."""
    p = row["payload"]
    return json.loads(p) if isinstance(p, str) else p


def _settlement_payloads(rows):
    return [_payload(r) for r in rows if r["event_type"] == "settlement"]


# ============================================================ exact settle
def test_exact_scheme_settles_once_on_response_start(tmp_path):
    """exact şemasında handler başlar başlamaz settle TAM bir kez çağrılır
    ve başarılı settlement ledger'a bir 'settlement' olayı yazar."""
    import asyncio

    led = Ledger(str(tmp_path / "swr9.sqlite3"), secret="mw-secret")
    transport = FakeTransport(verify_results=[{"ok": True}])
    fac = Facilitator("https://x402.test", transport=transport)
    meter = SesterMeter(_asgi_app(), ledger=led, price=0.05,
                        daily_quota=1.0, secret="mw-secret",
                        facilitator=fac)
    pay = "x402 " + _exact_header(nonce="sn1")
    send, sent = _capture()

    asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))

    settles = [c for c in transport.calls if c[0].endswith("/settle")]
    assert len(settles) == 1
    rows = led.export_events(ADDR1)
    payloads = _settlement_payloads(rows)
    assert len(payloads) == 1
    assert payloads[0]["status"] == "settled"
    led.close()


def test_exact_settle_is_not_called_twice_for_the_same_response(tmp_path):
    """Birden-fazla response.start görülse bile settle_once bayrağı
    facilitator'u TEKRAR çağırtmaz (çift-settle = çift-harcama)."""
    import asyncio

    async def app(scope, receive, send):
        for _ in range(2):
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": b"{}"})

    led = Ledger(str(tmp_path / "swr10.sqlite3"), secret="mw-secret")
    transport = FakeTransport(verify_results=[{"ok": True}])
    fac = Facilitator("https://x402.test", transport=transport)
    meter = SesterMeter(app, ledger=led, price=0.05, daily_quota=1.0,
                        secret="mw-secret", facilitator=fac)
    pay = "x402 " + _exact_header(nonce="sn2")
    send, sent = _capture()

    asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))

    settles = [c for c in transport.calls if c[0].endswith("/settle")]
    assert len(settles) == 1
    led.close()


def test_exact_transient_settle_failure_is_retryable_on_the_next_request(tmp_path):
    """AT-174-BULGU-1-düzeltmesi: geçici-on-chain-hata done-bayrağını
    setlemez, böylece bir sonraki istekte settle TEKRAR denenebilir
    (kapanma-anında-bekleyen-settlement-kaybı yok). Her istek kendi nonce'su
    ile ayrı bir ödemedir; başarısız-olan bir sonrakinde tekrar denenebilir."""
    import asyncio

    led = Ledger(str(tmp_path / "swr11.sqlite3"), secret="mw-secret")
    transport = FakeTransport(verify_results=[{"ok": True}, {"ok": True}],
                              settle_fail_first=1)
    fac = Facilitator("https://x402.test", transport=transport)
    meter = SesterMeter(_asgi_app(), ledger=led, price=0.05,
                        daily_quota=1.0, secret="mw-secret",
                        facilitator=fac)

    for nonce in ("f1", "f2"):
        pay = "x402 " + _exact_header(nonce=nonce)
        send, sent = _capture()
        asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))

    settles = [c for c in transport.calls if c[0].endswith("/settle")]
    assert len(settles) == 2
    statuses = [p["status"] for p in _settlement_payloads(led.export_events(ADDR1))]
    assert "settle_failed" in statuses
    assert "settled" in statuses
    led.close()


def test_exact_settle_failure_records_zero_amount_settlement(tmp_path):
    """Başarısız settle sıfır-tutarlı bir 'settlement' olayı yazar —
    gerçek-para hareket-olmadığının denetim-izidir."""
    import asyncio

    led = Ledger(str(tmp_path / "swr12.sqlite3"), secret="mw-secret")
    transport = FakeTransport(verify_results=[{"ok": True}],
                              settle_fail_first=1)
    fac = Facilitator("https://x402.test", transport=transport)
    meter = SesterMeter(_asgi_app(), ledger=led, price=0.05,
                        daily_quota=1.0, secret="mw-secret",
                        facilitator=fac)
    pay = "x402 " + _exact_header(nonce="z1")
    send, sent = _capture()

    asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))

    payloads = _settlement_payloads(led.export_events(ADDR1))
    assert len(payloads) == 1
    assert payloads[0]["status"] == "settle_failed"
    settled = next(r for r in led.export_events(ADDR1)
                   if r["event_type"] == "settlement")
    assert settled["amount"] == 0.0
    led.close()


def test_pugio_scheme_does_not_call_settle(tmp_path):
    """exact dışındaki şemalarda facilitator settle ÇAĞRILMAZ — settle
    yalnızca exact'in on-chain-teminata karşılığıdır."""
    import asyncio

    led = Ledger(str(tmp_path / "swr13.sqlite3"), secret="mw-secret")
    transport = FakeTransport(verify_results=[{"ok": True}])
    fac = Facilitator("https://x402.test", transport=transport)
    meter = SesterMeter(_asgi_app(), ledger=led, price=0.05,
                        daily_quota=1.0, secret="mw-secret",
                        facilitator=fac)
    pay = _pugio("ag-i", "n9", "0.05", "/data")
    send, sent = _capture()

    asyncio.run(meter(_scope(pay, "/data"), lambda: None, send))

    settles = [c for c in transport.calls if c[0].endswith("/settle")]
    assert settles == []
    led.close()
