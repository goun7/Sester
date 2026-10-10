"""scripts/s6_joint_run.run_live dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-3: urllib.request.urlopen STUBLANIYOR — gercek HTTP YAPILMADI.
Kural-4: saf in-memory; env monkeypatch.
"""
import json
import os
import sys
import urllib.request

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_REPO, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import s6_joint_run as S6  # noqa: E402


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def _stub_urlopen(monkeypatch, responses):
    """urllib.request.urlopen'u patchler (gercek HTTP YOK)."""
    calls = {"posts": []}

    def _urlopen(req, timeout=10):
        calls["posts"].append({
            "url": req.full_url,
            "body": json.loads(req.data.decode()),
            "headers": req.headers,
            "method": req.method,
            "timeout": timeout,
        })
        for path, payload in responses.items():
            if req.full_url.endswith(path):
                if isinstance(payload, Exception):
                    raise payload
                return _Resp(payload)
        raise AssertionError(f"stub yolu karsilamadi: {req.full_url}")

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    return calls


@pytest.fixture(autouse=True)
def _reset_counters(monkeypatch):
    """check() modul-sayacini sifirla (diger testleri etkilemesin)."""
    monkeypatch.setattr(S6, "_pass", 0)
    monkeypatch.setattr(S6, "_fail", 0)


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setenv("SESTER_FACILITATOR_URL", "https://fac.test")
    monkeypatch.setenv("SESTER_FACILITATOR_KEY", "secret-key")


def _run_live(monkeypatch, capsys, responses):
    _stub_urlopen(monkeypatch, responses)
    return S6.run_live(), capsys.readouterr().out


_OK = {
    "/verify": {"status": "ok"},
    "/settle": {"status": "ok"},
    "/refund": {"status": "ok"},
}


# -- hata ---------------------------------------------------------------------------------

def test_missing_url_raises(monkeypatch):
    monkeypatch.delenv("SESTER_FACILITATOR_URL", raising=False)
    monkeypatch.setenv("SESTER_FACILITATOR_KEY", "k")
    with pytest.raises(KeyError):
        S6.run_live()


def test_missing_key_raises(monkeypatch):
    monkeypatch.setenv("SESTER_FACILITATOR_URL", "https://fac.test")
    monkeypatch.delenv("SESTER_FACILITATOR_KEY", raising=False)
    with pytest.raises(KeyError):
        S6.run_live()


def test_no_env_raises(monkeypatch):
    monkeypatch.delenv("SESTER_FACILITATOR_URL", raising=False)
    monkeypatch.delenv("SESTER_FACILITATOR_KEY", raising=False)
    with pytest.raises(KeyError):
        S6.run_live()


# -- mutlu-yol ---------------------------------------------------------------------------------

def test_all_green_returns_0(monkeypatch, capsys, env):
    # /settle ve /refund iki farkli yanit (replay + refund_exceeds)
    responses = {
        "/verify": {"status": "ok"},
    }
    settle = [{"status": "ok"}, {"reason": "replay_detected"}]
    refund = [{"status": "ok"}, {"reason": "refund_exceeds"}]
    calls = _stub_urlopen(monkeypatch, responses)

    # sira-bazli yanit: /settle ve /refund coklu cagri
    seq = {"s": 0, "r": 0}

    def _urlopen(req, timeout=10):
        calls["posts"].append({
            "url": req.full_url,
            "body": json.loads(req.data.decode()),
            "headers": req.headers,
        })
        p = req.full_url.rsplit("/", 1)[-1]
        if p == "verify":
            return _Resp({"status": "ok"})
        if p == "settle":
            i = seq["s"]
            seq["s"] += 1
            return _Resp(settle[i])
        if p == "refund":
            i = seq["r"]
            seq["r"] += 1
            return _Resp(refund[i])
        raise AssertionError(p)

    urllib.request.urlopen = _urlopen
    rc = S6.run_live()
    out = capsys.readouterr().out
    assert rc == 0
    assert "S6 CANLI-TUR" in out


def test_returns_int(monkeypatch, capsys, env):
    responses = {
        "/verify": {"status": "ok"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "ok"},
    }
    rc, out = _run_live(monkeypatch, capsys, responses)
    assert isinstance(rc, int)


def test_url_from_env(monkeypatch, capsys):
    """SESTER_FACILITATOR_URL dogru kullanilir (stub-eslesme hatasi)."""
    monkeypatch.setenv("SESTER_FACILITATOR_URL", "https://hedef.test")
    monkeypatch.setenv("SESTER_FACILITATOR_KEY", "k")
    calls = _stub_urlopen(monkeypatch, {})
    with pytest.raises(AssertionError):
        S6.run_live()


# -- kirmizi-kontroller ---------------------------------------------------------------------------------

def test_verify_red_returns_1(monkeypatch, capsys, env):
    responses = {
        "/verify": {"status": "error"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "ok"},
    }
    rc, out = _run_live(monkeypatch, capsys, responses)
    assert rc == 1
    assert "RED" in out or "S6 CANLI-TUR" in out


def test_settle_red_returns_1(monkeypatch, capsys, env):
    responses = {
        "/verify": {"status": "ok"},
        "/settle": {"status": "error"},
        "/refund": {"status": "ok"},
    }
    rc, _ = _run_live(monkeypatch, capsys, responses)
    assert rc == 1


def test_replay_not_detected_returns_1(monkeypatch, capsys, env):
    responses = {
        "/verify": {"status": "ok"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "ok"},
    }
    rc, out = _run_live(monkeypatch, capsys, responses)
    assert rc == 1
    assert "S6.c" in out


def test_refund_red_returns_1(monkeypatch, capsys, env):
    responses = {
        "/verify": {"status": "ok"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "error"},
    }
    rc, _ = _run_live(monkeypatch, capsys, responses)
    assert rc == 1


# -- istek-icerigi ---------------------------------------------------------------------------------

def test_posts_to_correct_paths(monkeypatch, capsys, env):
    calls = _stub_urlopen(monkeypatch, {
        "/verify": {"status": "ok"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "ok"},
    })
    S6.run_live()
    paths = [c["url"].rsplit("/", 1)[-1] for c in calls["posts"]]
    assert paths == ["verify", "settle", "settle", "refund", "refund"]


def test_base_url_used(monkeypatch, capsys, env):
    monkeypatch.setenv("SESTER_FACILITATOR_URL", "https://hedef.test/")
    calls = _stub_urlopen(monkeypatch, {
        "/verify": {"status": "ok"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "ok"},
    })
    S6.run_live()
    assert all(c["url"].startswith("https://hedef.test/")
               for c in calls["posts"])


def test_trailing_slash_stripped(monkeypatch, capsys, env):
    monkeypatch.setenv("SESTER_FACILITATOR_URL", "https://f.test///")
    calls = _stub_urlopen(monkeypatch, {
        "/verify": {"status": "ok"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "ok"},
    })
    S6.run_live()
    assert "//verify" not in calls["posts"][0]["url"]


def test_key_in_headers(monkeypatch, capsys, env):
    calls = _stub_urlopen(monkeypatch, {
        "/verify": {"status": "ok"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "ok"},
    })
    S6.run_live()
    # urllib basliklari standartlastirir: X-facilitator-key / Content-type
    h = calls["posts"][0]["headers"]
    assert h.get("X-facilitator-key", h.get("X-Facilitator-Key")) == "secret-key"
    ct = h.get("Content-type", h.get("Content-Type"))
    assert ct == "application/json"


def test_post_method(monkeypatch, capsys, env):
    calls = _stub_urlopen(monkeypatch, {
        "/verify": {"status": "ok"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "ok"},
    })
    S6.run_live()
    assert calls["posts"][0]["method"] == "POST"


def test_verify_payload_has_payment(monkeypatch, capsys, env):
    calls = _stub_urlopen(monkeypatch, {
        "/verify": {"status": "ok"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "ok"},
    })
    S6.run_live()
    body = calls["posts"][0]["body"]
    assert "payment" in body and body["resource"] == "/weather"


def test_settle_payload_amount(monkeypatch, capsys, env):
    calls = _stub_urlopen(monkeypatch, {
        "/verify": {"status": "ok"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "ok"},
    })
    S6.run_live()
    settle = [c for c in calls["posts"] if c["url"].endswith("/settle")][0]
    assert settle["body"]["amount_minor"] == S6.PRICE_MINOR


def test_refund_payload_reason(monkeypatch, capsys, env):
    calls = _stub_urlopen(monkeypatch, {
        "/verify": {"status": "ok"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "ok"},
    })
    S6.run_live()
    refunds = [c for c in calls["posts"] if c["url"].endswith("/refund")]
    assert refunds[0]["body"]["reason"] == "inkâr"
    assert refunds[0]["body"]["dispute_ref"].startswith("sha256:")


def test_same_nonce_across_calls(monkeypatch, capsys, env):
    calls = _stub_urlopen(monkeypatch, {
        "/verify": {"status": "ok"},
        "/settle": {"status": "ok"},
        "/refund": {"status": "ok"},
    })
    S6.run_live()
    pays = [c["body"]["payment"] for c in calls["posts"]]
    assert len(set(pays)) == 1


# -- http-hatasi ---------------------------------------------------------------------------------

def test_http_error_propagates(monkeypatch, capsys, env):
    class _Err(Exception):
        pass

    responses = {"/verify": _Err("baglanti reddi")}
    with pytest.raises(_Err):
        _run_live(monkeypatch, capsys, responses)


# -- yardimcilar ---------------------------------------------------------------------------------

def test_pay_for_returns_str():
    p = S6.pay_for("musteri-test", "nonce-1")
    assert isinstance(p, str) and len(p) > 0


def test_pay_for_deterministic_per_nonce():
    a = S6.pay_for("musteri-x", "n")
    b = S6.pay_for("musteri-x", "n")
    assert a == b


def test_pay_for_customer_matters():
    a = S6.pay_for("musteri-x", "n")
    b = S6.pay_for("musteri-y", "n")
    assert a != b


def test_price_minor_positive():
    assert S6.PRICE_MINOR > 0


def test_nonce_value():
    assert isinstance(S6.NONCE, str) and S6.NONCE
