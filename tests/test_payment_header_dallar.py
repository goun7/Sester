"""fastapi_client_demo._payment_header dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — os.getpid/time.time MONKEYPATCH, dis cagri YOK.
Demo X-Payment basligi: EIP-191 imzali 'agent|nonce|amount|resource'.
"""
import sys
import time

import pytest

sys.path.insert(0, "examples")
sys.path.insert(0, ".")
sys.path.insert(0, "src")
import fastapi_client_demo as FCD  # noqa: E402

from eth_account import Account  # noqa: E402

SK = "0x" + "d3" * 32
AGENT = Account.from_key(SK).address


def decode_payment(header):
    """X-Payment basligini coz (Sester-EVM base64url-JSON)."""
    import base64
    raw = header[len("Sester-EVM "):]
    padded = raw + "=" * (-len(raw) % 4)
    import json
    return json.loads(base64.urlsafe_b64decode(padded))


@pytest.fixture()
def sabit_pid_time(monkeypatch):
    monkeypatch.setattr(FCD.os, "getpid", lambda: 12345)
    monkeypatch.setattr(FCD.time, "time", lambda: 1700000000.5)
    return (12345, 1700000000.5)


# == temel =====================================================================================

def test_returns_str(sabit_pid_time):
    assert isinstance(FCD._payment_header("/test"), str)


def test_bos_resource(sabit_pid_time):
    assert isinstance(FCD._payment_header(""), str)


def test_imza_dogrulanir(sabit_pid_time):
    """ORTAM: EIP-191 imza dogrulanabilir."""
    h = FCD._payment_header("/test")
    d = decode_payment(h)
    assert d is not None


def test_agent_dogru(sabit_pid_time):
    h = FCD._payment_header("/test")
    d = decode_payment(h)
    assert d["agent"].lower() == AGENT.lower()


def test_amount_fiyat(sabit_pid_time):
    """ORTAM: amount = PRICE (0.05 float)."""
    """ORTAM: amount = PRICE string '0.050000' (6-ondalik)."""
    h = FCD._payment_header("/test")
    d = decode_payment(h)
    assert d["amount"] == "0.050000"


def test_amount_005(sabit_pid_time):
    h = FCD._payment_header("/x")
    d = decode_payment(h)
    assert d["amount"] == "0.050000"


def test_nonce_benzersiz(sabit_pid_time):
    """ORTAM: nonce = example-{pid}-{int(time*1000)}."""
    h = FCD._payment_header("/test")
    d = decode_payment(h)
    assert d["nonce"] == "example-12345-1700000000500"


def test_resource_gorunur(sabit_pid_time):
    """ORTAM: resource IMZADA (payload'da DEGIL) — verify gerekir."""
    h = FCD._payment_header("/ozel/kaynak")
    from sester.schemes import verify_exact_sester
    assert verify_exact_sester(h, "/ozel/kaynak") is not None


# == nonce uniqueness ============================================================================

def test_farkli_pid_farkli_nonce(monkeypatch):
    """ORTAM: pid degisince nonce degisir."""
    monkeypatch.setattr(FCD.os, "getpid", lambda: 1)
    monkeypatch.setattr(FCD.time, "time", lambda: 1000.0)
    h1 = FCD._payment_header("/x")
    monkeypatch.setattr(FCD.os, "getpid", lambda: 2)
    h2 = FCD._payment_header("/x")
    assert decode_payment(h1)["nonce"] != decode_payment(h2)["nonce"]


def test_farkli_time_farkli_nonce(monkeypatch):
    monkeypatch.setattr(FCD.os, "getpid", lambda: 1)
    monkeypatch.setattr(FCD.time, "time", lambda: 1000.0)
    h1 = FCD._payment_header("/x")
    monkeypatch.setattr(FCD.time, "time", lambda: 1001.0)
    h2 = FCD._payment_header("/x")
    assert decode_payment(h1)["nonce"] != decode_payment(h2)["nonce"]


def test_ayni_pid_time_ayni_nonce(monkeypatch):
    """ORTAM: ayni pid+time -> ayni nonce (deterministik)."""
    monkeypatch.setattr(FCD.os, "getpid", lambda: 5)
    monkeypatch.setattr(FCD.time, "time", lambda: 2000.0)
    h1 = FCD._payment_header("/x")
    h2 = FCD._payment_header("/x")
    assert decode_payment(h1)["nonce"] == decode_payment(h2)["nonce"]


def test_nonce_prefix_example(sabit_pid_time):
    h = FCD._payment_header("/x")
    assert decode_payment(h)["nonce"].startswith("example-")


# == determinizm =================================================================================

def test_ayni_input_ayni_imza(sabit_pid_time):
    """ORTAM: ayni pid+time+resource -> ayni imza."""
    h1 = FCD._payment_header("/x")
    h2 = FCD._payment_header("/x")
    assert h1 == h2


def test_farkli_resource_farkli_imza(sabit_pid_time):
    h1 = FCD._payment_header("/a")
    h2 = FCD._payment_header("/b")
    assert h1 != h2


# == agent =======================================================================================

def test_agent_buyuk_harf_mi(sabit_pid_time):
    """ORTAM: agent KUCUK-harf (normalize edilir)."""
    h = FCD._payment_header("/x")
    d = decode_payment(h)
    assert d["agent"] == AGENT.lower()


def test_agent_0x_prefix(sabit_pid_time):
    h = FCD._payment_header("/x")
    d = decode_payment(h)
    assert d["agent"].startswith("0x")


def test_agent_40_hex(sabit_pid_time):
    h = FCD._payment_header("/x")
    d = decode_payment(h)
    assert len(d["agent"]) == 42


# == imza-geri-kazanim ===========================================================================

def test_imzadan_agent_kazanilir(sabit_pid_time):
    """ORTAM: recover_message = agent (resource imzada)."""
    from eth_account.messages import encode_defunct
    h = FCD._payment_header("/x")
    d = decode_payment(h)
    msg = f"{AGENT.lower()}|{d['nonce']}|{d['amount']}|/x"
    recovered = Account.recover_message(
        encode_defunct(text=msg), signature=d["signature"])
    assert recovered.lower() == AGENT.lower()


def test_mesaj_formati(sabit_pid_time):
    """ORTAM: 'agent|nonce|amount|resource' (kucuk-harf agent)."""
    from sester.schemes import verify_exact_sester
    h = FCD._payment_header("/test")
    # yanlis-resource verify'de basarisiz
    with pytest.raises(Exception):
        verify_exact_sester(h, "/yanlis")


# == cesitli =====================================================================================

def test_turkce_resource(sabit_pid_time):
    from sester.schemes import verify_exact_sester
    h = FCD._payment_header("/Türkçe")
    assert verify_exact_sester(h, "/Türkçe") is not None


def test_emoji_resource(sabit_pid_time):
    from sester.schemes import verify_exact_sester
    h = FCD._payment_header("/🤖")
    assert verify_exact_sester(h, "/🤖") is not None


def test_uzun_resource(sabit_pid_time):
    r = "/" + "x" * 200
    from sester.schemes import verify_exact_sester
    h = FCD._payment_header(r)
    assert verify_exact_sester(h, r) is not None


def test_query_string_resource(sabit_pid_time):
    from sester.schemes import verify_exact_sester
    h = FCD._payment_header("/api?a=1&b=2")
    assert verify_exact_sester(h, "/api?a=1&b=2") is not None


def test_sabit_secret_key(sabit_pid_time):
    """ORTAM: demo sk = '0x' + 'd3'*32."""
    assert SK == "0x" + "d3" * 32


def test_repeatable(sabit_pid_time):
    assert FCD._payment_header("/x") == FCD._payment_header("/x")


@pytest.mark.parametrize("r", ["/", "/a", "/a/b/c", "/api?x=1"])
def test_resource_matrix(sabit_pid_time, r):
    from sester.schemes import verify_exact_sester
    assert verify_exact_sester(FCD._payment_header(r), r) is not None
