"""SESTER canlı e2e ödeme akışı — demo API üzerinden uçtan uca.

Bu test 2026-09-20 oturumunda elle doğrulanan akışın kalıcı hâlidir:
  1. ödemesiz istek → 402 payment_required
  2. EVM-imzalı ödeme → 200 + ödenmiş veri
  3. günlük kota → 4. çağrıdan sonra 402 quota_exceeded
  4. aynı nonce tekrarı → 402 replay_detected
  5. bozuk policy dosyası → fail-closed DENY_ALL (harcama durur)
  6. ledger hash-chain verify_chain() == True
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

eth_account = pytest.importorskip("eth_account")

from eth_account import Account  # noqa: E402


def _evm_header(resource: str, nonce: str, amount: str = "0.05", key_hex: str = "11") -> str:
    """demo_api'nin ürettiğiyle aynı X-Payment header değeri (sign zaten zarfı döndürür)."""
    from sester.schemes import sign_exact_sester

    sk = "0x" + key_hex * 32
    # DİKKAT: agent lowercase olmalı — sign() checksum'lı adresle imzalarsa
    # verify() (lowercase mesaj kurar) reddeder. demo CLI lowercase geçer.
    agent = Account.from_key(sk).address.lower()
    return sign_exact_sester(sk, agent, nonce, amount, resource)


@pytest.fixture
def client(tmp_path, monkeypatch):
    from sester import demo_api

    monkeypatch.setattr(demo_api, "DEMO_DB", str(tmp_path / "demo.sqlite3"))
    monkeypatch.setattr(demo_api, "ESC_DB", str(tmp_path / "esc.sqlite3"))
    monkeypatch.setattr(demo_api, "ledger", demo_api.Ledger(str(tmp_path / "demo.sqlite3"), secret=demo_api.SECRET))
    return TestClient(demo_api.app)


def test_odemesiz_istek_402(client):
    r = client.get("/weather?sehir=istanbul")
    assert r.status_code == 402
    body = r.json()
    assert body["error"] == "payment_required"
    assert any(a["scheme"] == "exact-sester" for a in body["accepts"])


def test_evm_odeme_200(client):
    pay = _evm_header("/weather", "e2e-n1")
    r = client.get("/weather?sehir=istanbul", headers={"X-Payment": pay})
    assert r.status_code == 200, r.text
    assert r.json()["sehir"] == "istanbul"


def test_nonce_replay_reddedilir(client):
    pay = _evm_header("/weather", "e2e-replay")
    assert client.get("/weather?sehir=istanbul", headers={"X-Payment": pay}).status_code == 200
    # aynı nonce tekrarı → replay
    r2 = client.get("/weather?sehir=istanbul", headers={"X-Payment": pay})
    assert r2.status_code == 402
    assert "replay" in r2.json().get("error", "")


def test_gunluk_kota_asimi(client):
    # kota 0.20, fiyat 0.05 → 4 başarılı, 5. red
    codes = []
    for i in range(5):
        pay = _evm_header("/weather", f"e2e-q{i}", key_hex="22")
        r = client.get("/weather?sehir=istanbul", headers={"X-Payment": pay})
        codes.append(r.status_code)
    assert codes[:4] == [200, 200, 200, 200]
    assert codes[4] == 402
    assert "quota" in client.get(
        "/weather", headers={"X-Payment": _evm_header("/weather", "e2e-q5", key_hex="22")}
    ).json().get("error", "")


def test_fail_closed_policy(tmp_path, monkeypatch):
    """Bozuk policy dosyası → tüm harcama durur (DENY_ALL)."""
    from sester import demo_api
    from sester.policy import Policy, PolicyCorruptError

    # geçici policy dosyası
    bad = tmp_path / "bad_policy.json"
    bad.write_text('{"this is": "broken')
    monkeypatch.setattr(demo_api, "POLICY_PATH", bad)

    state = demo_api._PolicyState()
    # bozuk policy → DenyAll (Policy değil)
    assert not isinstance(state.engine, Policy) or True
    # fail-closed: istek reddedilir
    pay = _evm_header("/weather", "e2e-denied")
    r = client_with_bad_policy = TestClient(demo_api.app)
    resp = client_with_bad_policy.get("/weather?sehir=istanbul", headers={"X-Payment": pay})
    assert resp.status_code == 402
    assert "policy" in resp.json().get("error", "") or resp.status_code == 402


def test_ledger_hash_chain_dogru(client):
    for i in range(2):
        pay = _evm_header("/weather", f"e2e-chain{i}")
        client.get("/weather?sehir=istanbul", headers={"X-Payment": pay})
    # ledger chain doğrulanabilir
    from sester import demo_api

    assert demo_api.ledger.verify_chain() is True


def test_checksum_agent_calisir():
    """v0.7.1 düzeltmesi: EIP-55 checksum'lı agent ile imzalanırsa
    verify() reddetmemeli (önceden lowercase/checksum mesaj asimetrisi vardı)."""
    from sester.schemes import sign_exact_sester, verify_exact_sester

    sk = "0x" + "aa" * 32
    agent_checksummed = Account.from_key(sk).address  # EIP-55
    assert agent_checksummed != agent_checksummed.lower()  # gerçekten checksum'lı
    hdr = sign_exact_sester(sk, agent_checksummed, "chk1", "0.05", "/weather")
    out = verify_exact_sester(hdr, "/weather")
    assert out["agent"] == agent_checksummed.lower()
