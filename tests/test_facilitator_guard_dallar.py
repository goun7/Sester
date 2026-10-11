"""sester.facilitator_svc.app._guard (create_app closure) dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — route.endpoint fonksiyonu DOGRUDAN cagrilir
(GERCEK HTTP / uvicorn / network YOK — TestClient bile DEGIL).
_guard: X-Facilitator-Key header'ini sha256-turevli key ile karsilastirir
(hmac.compare_digest — zamanlama-saldiri direnci).
"""
import hashlib
import os

import pytest
from fastapi import HTTPException

from sester.facilitator_svc.app import create_app
from sester.ledger import Ledger


@pytest.fixture
def key():
    return hashlib.sha256(f"facilitator-key:{os.environ['SESTER_FACILITATOR_SECRET']}"
                          .encode()).hexdigest()


@pytest.fixture(autouse=True)
def _env_secret(monkeypatch):
    monkeypatch.setenv("SESTER_FACILITATOR_SECRET", "guard-test-secret")


@pytest.fixture
def verify_ep():
    """create_app closure'indaki _guard'a route.endpoint ile ulas (HTTP YOK)."""
    app = create_app(Ledger(":memory:", secret="s"))
    routes = {r.path: r for r in app.routes if hasattr(r, "endpoint")}
    return routes["/verify"].endpoint


def call_guard(ep, x_key):
    """req=None gecilebilir: _guard once calisir, RED'den sonra req KULLANILMAZ."""
    try:
        ep(None, x_key)
        return None
    except HTTPException as e:
        return e
    except AttributeError:
        return "passed-guard"


# == RED-yollari =================================================================================

class TestReject:
    @pytest.mark.parametrize("x_key", [None, "", "wrong-key", "deadbeef",
                                       "x" * 64, "0" * 128])
    def test_invalid_key_raises_401(self, verify_ep, x_key):
        """ORTAM: not x_key or compare_digest(x_key, key) -> 401."""
        exc = call_guard(verify_ep, x_key)
        assert exc is not None
        assert getattr(exc, "status_code", None) == 401

    def test_detail_message(self, verify_ep):
        exc = call_guard(verify_ep, "wrong")
        assert exc.detail == "auth-key geçersiz"

    def test_raises_http_exception(self, verify_ep):
        assert isinstance(call_guard(verify_ep, None), HTTPException)

    def test_none_rejected(self, verify_ep):
        """ORTAM: header YOK (None) -> RED (fail-closed)."""
        assert call_guard(verify_ep, None) is not None

    def test_empty_string_rejected(self, verify_ep):
        """ORTAM: bos-string falsy -> RED (not x_key kisa-devre)."""
        assert call_guard(verify_ep, "") is not None

    def test_prefix_of_key_rejected(self, verify_ep, key):
        """ORTAM: key'in on-ek'i TAM-ESLESME ISTEMEZ."""
        assert call_guard(verify_ep, key[:32]) is not None

    def test_key_with_suffix_rejected(self, verify_ep, key):
        assert call_guard(verify_ep, key + "x") is not None

    def test_case_mismatch_rejected(self, verify_ep, key):
        """ORTAM: compare_digest case-sensitive."""
        assert call_guard(verify_ep, key.upper()) is not None


# == KABUL-yolu ==================================================================================

class TestAccept:
    def test_correct_key_passes_guard(self, verify_ep, key):
        """ORTAM: dogru-key -> _guard return None, sonraki satir (svc.verify)
        req=None oldugu icin AttributeError verir — yani guard GECILDI."""
        assert call_guard(verify_ep, key) == "passed-guard"

    def test_correct_key_no_http_exception(self, verify_ep, key):
        assert not isinstance(call_guard(verify_ep, key), HTTPException)

    def test_key_derived_from_secret(self, verify_ep):
        """ORTAM: key = sha256(f'facilitator-key:{secret}').hexdigest()."""
        k = hashlib.sha256(b"facilitator-key:guard-test-secret").hexdigest()
        assert call_guard(verify_ep, k) == "passed-guard"

    def test_custom_auth_key(self):
        """ORTAM: auth_key verilirse sha256-turevli DEGIL, birebir karsilastirilir."""
        app = create_app(Ledger(":memory:", secret="s"), auth_key="my-custom-key")
        routes = {r.path: r for r in app.routes if hasattr(r, "endpoint")}
        ep = routes["/verify"].endpoint
        assert call_guard(ep, "my-custom-key") == "passed-guard"
        assert call_guard(ep, hashlib.sha256(
            b"facilitator-key:guard-test-secret").hexdigest()) is not None

    def test_custom_key_overrides_default(self):
        app = create_app(Ledger(":memory:", secret="s"), auth_key="exact-key")
        routes = {r.path: r for r in app.routes if hasattr(r, "endpoint")}
        ep = routes["/verify"].endpoint
        assert call_guard(ep, "exact-key") == "passed-guard"


# == tüm-route'lerde-guard =======================================================================

class TestAllRoutesGuarded:
    @pytest.mark.parametrize("path", ["/verify", "/settle", "/refund"])
    def test_each_protected_route_has_guard(self, path):
        """ORTAM: her korumali route _guard ile baslar (401 once)."""
        app = create_app(Ledger(":memory:", secret="s"))
        routes = {r.path: r for r in app.routes if hasattr(r, "endpoint")}
        assert path in routes
        ep = routes[path].endpoint
        assert getattr(call_guard(ep, None), "status_code", None) == 401

    def test_openapi_route_not_guarded(self):
        """ORTAM: /openapi.json ve /docs herkese-acik (guard YOK)."""
        app = create_app(Ledger(":memory:", secret="s"))
        paths = {r.path for r in app.routes if hasattr(r, "endpoint")}
        assert "/openapi.json" in paths
        assert "/docs" in paths

    def test_healthz_not_guarded(self):
        app = create_app(Ledger(":memory:", secret="s"))
        paths = {r.path for r in app.routes if hasattr(r, "endpoint")}
        assert "/healthz" in paths


# == anahtar-turev ===============================================================================

class TestKeyDerivation:
    def test_key_is_sha256_hex(self, key):
        assert len(key) == 64
        int(key, 16)

    def test_different_secret_different_key(self, monkeypatch):
        """ORTAM: secret DEGISINCE key DEGISIR (tek-yol secret'ten)."""
        monkeypatch.setenv("SESTER_FACILITATOR_SECRET", "other-secret")
        app = create_app(Ledger(":memory:", secret="s"))
        routes = {r.path: r for r in app.routes if hasattr(r, "endpoint")}
        ep = routes["/verify"].endpoint
        old = hashlib.sha256(b"facilitator-key:guard-test-secret").hexdigest()
        assert call_guard(ep, old) is not None
        new = hashlib.sha256(b"facilitator-key:other-secret").hexdigest()
        assert call_guard(ep, new) == "passed-guard"

    def test_missing_secret_raises_runtimeerror(self, monkeypatch):
        """ORTAM: fail-closed — secret YOKSA create_app acilista RED."""
        monkeypatch.delenv("SESTER_FACILITATOR_SECRET", raising=False)
        with pytest.raises(RuntimeError):
            create_app(Ledger(":memory:", secret="s"))

    def test_explicit_secret_used(self, monkeypatch):
        """ORTAM: secret= argümani env'e ONCELIKLI."""
        monkeypatch.setenv("SESTER_FACILITATOR_SECRET", "env-secret")
        app = create_app(Ledger(":memory:", secret="s"), secret="explicit-secret")
        routes = {r.path: r for r in app.routes if hasattr(r, "endpoint")}
        ep = routes["/verify"].endpoint
        assert call_guard(ep, hashlib.sha256(
            b"facilitator-key:explicit-secret").hexdigest()) == "passed-guard"
        assert call_guard(ep, hashlib.sha256(
            b"facilitator-key:env-secret").hexdigest()) is not None
