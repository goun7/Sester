"""sester.adapters._sign_object dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (HS256 HMAC, ES256 cryptography, dis cagri YOK).
'signature' alani disindaki her alan imzalanir (deterministik).
"""
import base64
import hashlib
import hmac
import json
import sys

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "src")
from sester.adapters import _sign_object, sign_mandate_jws  # noqa: E402
from sester.adapters import AdapterError  # noqa: E402


def b64u_decode(s):
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def b64u_encode(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def verify_hs256(jws, key):
    h, p, s = jws.split(".")
    mac = hmac.new(key, f"{h}.{p}".encode(), hashlib.sha256).digest()
    return b64u_encode(mac) == s


KEY = b"test-key-32-bytes-long-enough!"


# == temel =====================================================================================

def test_jws_3_parca():
    r = _sign_object({"a": 1}, alg="HS256", key=KEY)
    assert len(r.split(".")) == 3


def test_imza_dogrulanir():
    r = _sign_object({"a": 1}, alg="HS256", key=KEY)
    assert verify_hs256(r, KEY)


def test_bos_obje():
    r = _sign_object({}, alg="HS256", key=KEY)
    assert verify_hs256(r, KEY)


def test_cok_alan():
    r = _sign_object({"a": 1, "b": "x", "c": [1, 2]}, alg="HS256", key=KEY)
    assert verify_hs256(r, KEY)


def test_returns_str():
    assert isinstance(_sign_object({"a": 1}, alg="HS256", key=KEY), str)


def test_header_alg():
    r = _sign_object({"a": 1}, alg="HS256", key=KEY)
    hdr = json.loads(b64u_decode(r.split(".")[0]))
    assert hdr["alg"] == "HS256"


def test_header_typ():
    r = _sign_object({"a": 1}, alg="HS256", key=KEY)
    hdr = json.loads(b64u_decode(r.split(".")[0]))
    assert hdr["typ"] == "JWS"


def test_payload_alan():
    r = _sign_object({"a": 1}, alg="HS256", key=KEY)
    payload = json.loads(b64u_decode(r.split(".")[1]))
    assert payload == {"a": 1}


def test_kid_yok():
    r = _sign_object({"a": 1}, alg="HS256", key=KEY)
    hdr = json.loads(b64u_decode(r.split(".")[0]))
    assert "kid" not in hdr


def test_kid_var():
    r = _sign_object({"a": 1}, alg="HS256", key=KEY, kid="k1")
    hdr = json.loads(b64u_decode(r.split(".")[0]))
    assert hdr["kid"] == "k1"


# == signature-alani-cikarimi ==================================================================

def test_signature_alani_cikarilir():
    """ORTAM: 'signature' alani DISINDA imzalanir."""
    r = _sign_object({"a": 1, "signature": "eski"}, alg="HS256", key=KEY)
    payload = json.loads(b64u_decode(r.split(".")[1]))
    assert "signature" not in payload


def test_signature_cikarilmaz_degil_mi():
    r = _sign_object({"a": 1, "signature": "eski"}, alg="HS256", key=KEY)
    payload = json.loads(b64u_decode(r.split(".")[1]))
    assert payload == {"a": 1}


def test_signature_yoksa_ayni():
    r1 = _sign_object({"a": 1}, alg="HS256", key=KEY)
    r2 = _sign_object({"a": 1, "signature": "x"}, alg="HS256", key=KEY)
    assert r1 == r2


def test_signature_alani_diger_anahtar_etkilemez():
    r1 = _sign_object({"signature": "x", "a": 1}, alg="HS256", key=KEY)
    r2 = _sign_object({"a": 1, "signature": "y"}, alg="HS256", key=KEY)
    assert r1 == r2


def test_baska_anahtar_etkilenir():
    r = _sign_object({"signature": "x", "a": 2}, alg="HS256", key=KEY)
    payload = json.loads(b64u_decode(r.split(".")[1]))
    assert payload == {"a": 2}


def test_icte_signature_yok():
    """ORTAM: sadece top-level 'signature' cikarilir."""
    r = _sign_object({"a": {"signature": 1}}, alg="HS256", key=KEY)
    payload = json.loads(b64u_decode(r.split(".")[1]))
    assert payload == {"a": {"signature": 1}}


# == determinizm ===============================================================================

def test_deterministik():
    r1 = _sign_object({"a": 1}, alg="HS256", key=KEY)
    r2 = _sign_object({"a": 1}, alg="HS256", key=KEY)
    assert r1 == r2


def test_anahtar_farkli_imza():
    r1 = _sign_object({"a": 1}, alg="HS256", key=KEY)
    r2 = _sign_object({"a": 1}, alg="HS256", key=b"diger-anahtar-32-bytes")
    assert r1 != r2


def test_veri_farkli_imza():
    r1 = _sign_object({"a": 1}, alg="HS256", key=KEY)
    r2 = _sign_object({"a": 2}, alg="HS256", key=KEY)
    assert r1 != r2


def test_alan_sirasi_duzenlenir():
    """ORTAM: json.dumps(sort_keys=True)."""
    r1 = _sign_object({"b": 2, "a": 1}, alg="HS256", key=KEY)
    r2 = _sign_object({"a": 1, "b": 2}, alg="HS256", key=KEY)
    assert r1 == r2


def test_ascii_ensure():
    r = _sign_object({"x": "Türkçe"}, alg="HS256", key=KEY)
    hdr, p, s = r.split(".")
    assert verify_hs256(r, KEY)


# == alg ========================================================================================

def test_desteklenmeyen_alg():
    with pytest.raises(AdapterError):
        _sign_object({"a": 1}, alg="RS256", key=KEY)


def test_alg_none():
    with pytest.raises(AdapterError):
        _sign_object({"a": 1}, alg="none", key=KEY)


def test_alg_bos():
    with pytest.raises(AdapterError):
        _sign_object({"a": 1}, alg="", key=KEY)


def test_alg_hs512():
    """ORTAM: sadece HS256/ES256 destekli."""
    with pytest.raises(AdapterError):
        _sign_object({"a": 1}, alg="HS512", key=KEY)


def test_alg_case_sensitive():
    with pytest.raises(AdapterError):
        _sign_object({"a": 1}, alg="hs256", key=KEY)


def test_es256_calisir():
    """ES256 cryptography ile (opsiyonel)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ec import (
            ECPrivateKey)
        from cryptography.hazmat.primitives import serialization
        k = ECPrivateKey.generate()
        pem = k.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption())
        r = _sign_object({"a": 1}, alg="ES256", key=pem)
        assert len(r.split(".")) == 3
    except ImportError:
        pytest.skip("cryptography yok")


def test_es256_deterministik_degil():
    """ES256 her-imzada farkli (r,s nonce)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ec import (
            ECPrivateKey)
        from cryptography.hazmat.primitives import serialization
        k = ECPrivateKey.generate()
        pem = k.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption())
        r1 = _sign_object({"a": 1}, alg="ES256", key=pem)
        r2 = _sign_object({"a": 1}, alg="ES256", key=pem)
        assert r1 != r2
    except ImportError:
        pytest.skip("cryptography yok")


# == anahtar turleri ============================================================================

def test_key_str():
    """ORTAM: str key -> bytes."""
    r = _sign_object({"a": 1}, alg="HS256", key="str-anahtar")
    assert verify_hs256(r, b"str-anahtar")


def test_key_bytes():
    r = _sign_object({"a": 1}, alg="HS256", key=KEY)
    assert verify_hs256(r, KEY)


def test_key_bos_str():
    r = _sign_object({"a": 1}, alg="HS256", key="")
    assert verify_hs256(r, b"")


def test_key_bos_bytes():
    r = _sign_object({"a": 1}, alg="HS256", key=b"")
    assert verify_hs256(r, b"")


def test_key_uzun():
    r = _sign_object({"a": 1}, alg="HS256", key=b"x" * 1000)
    assert verify_hs256(r, b"x" * 1000)


def test_key_none():
    """ORTAM: None key -> bytes(None) b'None' (TypeError DEGIL)."""
    r = _sign_object({"a": 1}, alg="HS256", key=None)
    assert verify_hs256(r, b"None")


# == cesitli ====================================================================================

def test_turkce_deger():
    r = _sign_object({"ad": "Türkçe"}, alg="HS256", key=KEY)
    payload = json.loads(b64u_decode(r.split(".")[1]))
    assert payload["ad"] == "Türkçe"


def test_emoji_deger():
    r = _sign_object({"e": "🤖"}, alg="HS256", key=KEY)
    payload = json.loads(b64u_decode(r.split(".")[1]))
    assert payload["e"] == "🤖"


def test_nested_obje():
    r = _sign_object({"a": {"b": {"c": [1, 2, 3]}}},
                     alg="HS256", key=KEY)
    assert verify_hs256(r, KEY)


def test_list_deger():
    r = _sign_object({"l": [1, "x", None, True]},
                     alg="HS256", key=KEY)
    payload = json.loads(b64u_decode(r.split(".")[1]))
    assert payload["l"] == [1, "x", None, True]


def test_none_deger():
    r = _sign_object({"n": None}, alg="HS256", key=KEY)
    payload = json.loads(b64u_decode(r.split(".")[1]))
    assert payload["n"] is None


def test_bool_deger():
    r = _sign_object({"b": True}, alg="HS256", key=KEY)
    payload = json.loads(b64u_decode(r.split(".")[1]))
    assert payload["b"] is True


def test_sayi_deger():
    r = _sign_object({"i": 42, "f": 3.14}, alg="HS256", key=KEY)
    payload = json.loads(b64u_decode(r.split(".")[1]))
    assert payload["i"] == 42 and payload["f"] == 3.14


def test_b64url_encoding():
    """ORTAM: base64url (standart DEGIL — '+/' yerine '-_')."""
    r = _sign_object({"a": 1}, alg="HS256", key=KEY)
    parts = r.split(".")
    for p in parts:
        assert "+" not in p and "/" not in p


def test_b64_padding_yok():
    """ORTAM: '=' padding KALDIRILIR."""
    r = _sign_object({"a": 1}, alg="HS256", key=KEY)
    assert "=" not in r


def test_sign_mandate_jws_ayni():
    """ORTAM: _sign_object sign_mandate_jws'e delege eder."""
    r1 = _sign_object({"a": 1}, alg="HS256", key=KEY)
    r2 = sign_mandate_jws({"a": 1}, alg="HS256", key=KEY)
    assert r1 == r2


@pytest.mark.parametrize("obj", [{}, {"a": 1}, {"a": 1, "b": 2},
                                 {"x": "uzun" * 50}, {"n": None}])
def test_obje_matrix(obj):
    r = _sign_object(obj, alg="HS256", key=KEY)
    assert verify_hs256(r, KEY)


@pytest.mark.parametrize("kid", [None, "k1", "uzun-kid-12345", "Türkçe"])
def test_kid_matrix(kid):
    r = _sign_object({"a": 1}, alg="HS256", key=KEY, kid=kid)
    hdr = json.loads(b64u_decode(r.split(".")[0]))
    if kid is None:
        assert "kid" not in hdr
    else:
        assert hdr["kid"] == kid
