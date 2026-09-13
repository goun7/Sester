"""SESTER JWS testleri — AP2 mandate imza-katmanı (RFC 7515, KARAR_63B v0.3).

Kapsam: HS256 (stdlib) üret+doğrula uçtan-uca; ES256 (cryptography varsa);
fail-closed retler (payload-kazıma, yanlış-anahtar, alg-none, bozuk-form);
resolver'sız form-bağlamı uyumu; middleware-entegrasyonu (imzalı → 200,
kazınmış → 402).
"""

from __future__ import annotations

import base64
import json
import time

import pytest

from sester.adapters import (
    AdapterError,
    Ap2Mandate,
    install_adapters,
    sign_mandate_jws,
    verify_ap2_mandate,
    verify_mandate_jws,
)

WALLET = "0xjws000000000000000000000000000000000000"
USER = "did:user:gokun"
HS_SECRET = b"jws-hs256-test-secret"


def _mandate_body(**over) -> dict:
    t = time.time()
    m = {
        "mandate_id": "man-jws-1",
        "agent": WALLET,
        "principal": USER,
        "valid_from": t - 10,
        "valid_to": t + 3600,
        "scope": {"resource_prefixes": ["/weather"],
                  "per_request_max_minor": 100_000, "currency": "USDC"},
    }
    m.update(over)
    return m


def _signed_header(body: dict, *, alg: str = "HS256", key=HS_SECRET,
                   kid: str | None = "k1") -> str:
    sig = sign_mandate_jws(body, alg=alg, key=key, kid=kid)
    raw = base64.urlsafe_b64encode(json.dumps({**body, "signature": sig}).encode()
                                   ).decode().rstrip("=")
    return f"AP2-Mandate {raw}"


# ---------------------------------------------------------------- HS256 (stdlib)

def test_108_hs256_roundtrip_end_to_end():
    body = _mandate_body()
    h = _signed_header(body)
    intent = verify_ap2_mandate(h, "/weather", 50_000, "USDC",
                                resolve_key=lambda kid, alg: HS_SECRET)
    assert intent.agent == WALLET and intent.nonce == "man-jws-1"


def test_109_tampered_payload_rejected():
    body = _mandate_body()
    h = _signed_header(body)
    # orijinal imzayı koru, gövdeyi kazı: scope üst-sınırını yükselt
    orig = json.loads(base64.urlsafe_b64decode(
        h.split(" ", 1)[1] + "=" * (-len(h.split(" ", 1)[1]) % 4)))
    scraped = {**body, "signature": orig["signature"]}
    scraped["scope"]["per_request_max_minor"] = 10_000_000
    raw = base64.urlsafe_b64encode(json.dumps(scraped).encode()).decode().rstrip("=")
    with pytest.raises(AdapterError, match="uyuşmuyor"):
        verify_ap2_mandate(f"AP2-Mandate {raw}", "/weather", 50_000, "USDC",
                           resolve_key=lambda kid, alg: HS_SECRET)


def test_110_wrong_key_rejected():
    h = _signed_header(_mandate_body())
    with pytest.raises(AdapterError, match="uyuşmuyor"):
        verify_ap2_mandate(h, "/weather", 50_000, "USDC",
                           resolve_key=lambda kid, alg: b"wrong-secret")


def test_111_alg_none_rejected():
    body = _mandate_body()
    hdr = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWS"}).encode()
                                   ).decode().rstrip("=")
    pay = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    raw = base64.urlsafe_b64encode(json.dumps(
        {**body, "signature": f"{hdr}.{pay}."}).encode()).decode().rstrip("=")
    with pytest.raises(AdapterError, match="alg"):
        verify_ap2_mandate(f"AP2-Mandate {raw}", "/weather", 50_000, "USDC",
                           resolve_key=lambda kid, alg: HS_SECRET)


def test_112_malformed_jws_forms_rejected():
    with pytest.raises(AdapterError):
        verify_mandate_jws("tek-segment", resolve_key=lambda k, a: HS_SECRET)
    with pytest.raises(AdapterError):
        verify_mandate_jws("a.b", resolve_key=lambda k, a: HS_SECRET)
    with pytest.raises(AdapterError):
        verify_mandate_jws("!!!.eyJ9.sig", resolve_key=lambda k, a: HS_SECRET)


def test_113_unknown_kid_fails_closed():
    h = _signed_header(_mandate_body())
    with pytest.raises(AdapterError, match="kid"):
        verify_ap2_mandate(h, "/weather", 50_000, "USDC",
                           resolve_key=lambda kid, alg: None)


# ---------------------------------------------------------------- ES256 (opsiyonel)

def test_114_es256_roundtrip_or_explicit_skip():
    cryptography = pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.asymmetric import ec

    priv = ec.generate_private_key(ec.SECP256R1())
    from cryptography.hazmat.primitives import serialization

    pem_priv = priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    pem_pub = priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    body = _mandate_body()
    h = _signed_header(body, alg="ES256", key=pem_priv, kid="es1")
    intent = verify_ap2_mandate(h, "/weather", 50_000, "USDC",
                                resolve_key=lambda kid, alg: pem_pub)
    assert intent.protocol == "ap2"


def test_115_es256_wrong_key_rejected():
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    priv = ec.generate_private_key(ec.SECP256R1())
    other = ec.generate_private_key(ec.SECP256R1())
    pem_priv = priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    pem_other = other.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    h = _signed_header(_mandate_body(), alg="ES256", key=pem_priv)
    with pytest.raises(AdapterError, match="uyuşmuyor"):
        verify_ap2_mandate(h, "/weather", 50_000, "USDC",
                           resolve_key=lambda kid, alg: pem_other)


# ------------------------------------------------- resolver'sız uyum + entegrasyon

def test_116_without_resolver_form_binding_only():
    body = _mandate_body()
    h = _signed_header(body)  # imza "yanlış" olsa bile — resolver yoksa form-bağlamı
    intent = verify_ap2_mandate(h, "/weather", 50_000, "USDC",
                                resolve_key=None)
    assert intent.nonce == "man-jws-1"
    # form-şartı: çok-kısa imza ret
    bad = base64.urlsafe_b64encode(json.dumps(
        {**body, "signature": "kisa"}).encode()).decode().rstrip("=")
    with pytest.raises(AdapterError, match="formda değil"):
        Ap2Mandate.parse(f"AP2-Mandate {bad}").verify(resolve_key=None)


def test_117_middleware_accepts_signed_rejects_scraped(tmp_path):
    from sester.ledger import Ledger
    from sester.middleware import SesterMeter

    led = Ledger(tmp_path / "jws.sqlite3", secret="jws")
    meter = SesterMeter(None, led, price=0.05, daily_quota=0.10, secret="jws")
    install_adapters(meter.register_scheme, price_minor=meter.price_minor,
                     key_resolver=lambda kid, alg: HS_SECRET)

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})

    async def call(payment):
        meter.app = app
        out = []
        scope = {"type": "http", "path": "/weather",
                 "headers": [(b"x-payment", payment.encode())]}

        async def s(m):
            out.append(m)

        await meter(scope, None, s)
        return out[0]["status"]

    good = _signed_header(_mandate_body())
    assert asyncio_run(call(good)) == 200

    # kazıma: zarf-gövdesi B (üst-sınır yükseltilmiş) + A'nın geçerli imzası
    # → expected_body-bağı 402 döndürmeli (fail-closed)
    body_a = _mandate_body(mandate_id="man-jws-2")
    body_b = _mandate_body(mandate_id="man-jws-2")
    body_b["scope"]["per_request_max_minor"] = 10_000_000
    sig_a = sign_mandate_jws(body_a, alg="HS256", key=HS_SECRET, kid="k1")
    evil = {**body_b, "signature": sig_a}
    raw = base64.urlsafe_b64encode(json.dumps(evil).encode()).decode().rstrip("=")
    assert asyncio_run(call(f"AP2-Mandate {raw}")) == 402
    # tamamen imzasız gövde de 402
    raw_nosig = base64.urlsafe_b64encode(json.dumps(body_b).encode()).decode().rstrip("=")
    assert asyncio_run(call(f"AP2-Mandate {raw_nosig}")) == 402


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)
