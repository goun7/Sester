"""SESTER 0.5.0 küzeltme-testleri — kapı-koşumunda yakalanan üç RED'in pinleri.

1) Tamga-alıcısı kaynak-uyumu (test_74): DONUK üretici `sikke` basar; kardeş
   alıcı K0 §5 çift-ad-okuma yapmalı (sikke|pugio; bridge_version=1) —
   bilinmeyen RED.
2) Payee-kayıt-defteri (test_193/201): ledger-kimliği EVM-adresi DEĞİL —
   calldata `payee_address` alır; türetme açık-belingi + digest'e bağlı;
   çakışan-yeniden-kayıt RED.
"""
from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

import pytest

from sester.bridges import tamga_anchor_json
from sester.evidence import produce_bundle
from sester.ledger import Ledger
from sester.settlement import (
    SettlementError,
    build_settlement_batch,
    derive_payee_address,
    register_payee,
)

CONTRACT = "0x" + "ab" * 20
FROM = "0x" + "cd" * 20
OTHER = "0x" + "ef" * 20

TAMGA_RECEIVER = Path(
    os.environ.get("SESTER_TAMGA_RECEIVER", "")
    or os.path.join(os.environ.get("SESTER_TAMGA_PATH", ""),
                    "tamga_pugio_receiver.py")
)
CANONICAL_RECEIVER = (
    Path(__file__).resolve().parent.parent / "bridge_receivers" / "tamga_pugio_receiver.py"
)


def _make_bundle(tmp_path: Path, name: str = "b") -> dict:
    """Gerçek ledger'dan gerçek bundle (ledger kapatılır; bundle bağımsız)."""
    led = Ledger(tmp_path / f"{name}.sqlite3", secret="p-payee")
    try:
        led.append("permission_decision", "ag-p", "/weather",
                   payload={"decision": "deny", "rule_id": "quota_exceeded"})
        led.append("charge_receipt", "ag-p", "/weather", 0.05,
                   payload={"nonce": "pn1", "paid": 0.05, "scheme": "pugio0"})
        return produce_bundle(led, agent_id="ag-p")
    finally:
        led.close()


def _make_ledger(tmp_path: Path, agent: str, name: str) -> Ledger:
    led = Ledger(tmp_path / f"{name}.sqlite3", secret="p-payee")
    led.append("permission_decision", agent, "/weather",
               payload={"decision": "deny", "rule_id": "quota_exceeded"})
    led.append("charge_receipt", agent, "/weather", 0.05,
               payload={"nonce": "pn1", "paid": 0.05, "scheme": "pugio0"})
    return led


# ---------------------------------------------------------------- 1) K1 kaynak

def _receiver_source() -> str:
    """Kardeş-alıcı varsa onun kaynağı; yoksa kanonik kopya (aynı sözleşme)."""
    src_path = TAMGA_RECEIVER if TAMGA_RECEIVER.is_file() else CANONICAL_RECEIVER
    return src_path.read_text(encoding="utf-8")


def test_k1_receiver_accepts_frozen_primary_source():
    """Üreticinin DONUK birincil değeri (`sikke`) alıcıda KABUL olmalı —
    bridge_version=2 çift-ad-okuma (sikke|pugio) pin (test_74-RED'i)."""
    src = _receiver_source()
    assert 'not in ("sikke", "pugio")' in src, (
        "alıcı çift-ad-okuma yapmıyor — test_74 RED'i geri-döner")


def test_k1_receiver_rejects_unknown_source():
    """Sessiz-geçiş yok: bilinmeyen-kaynak RED-dalı pin."""
    src = _receiver_source()
    assert "FAIL" in src or "RED" in src  # fail-loud çıktı disiplini korunur


def test_k1_producer_receiver_roundtrip_with_sibling(tmp_path):
    """Gerçek-kardeş varsa uçtan-uca: üretici (DONUK `sikke`) → alıcı KABUL."""
    if not TAMGA_RECEIVER.is_file():
        pytest.skip("kardeş-repo alıcısı bu makinede yok")
    anchor_file = tmp_path / "cipa.jsonl"
    anchor_file.write_text(
        tamga_anchor_json(_make_bundle(tmp_path), agent_label="ag-p") + "\n",
        encoding="utf-8")
    r = subprocess.run([sys.executable, str(TAMGA_RECEIVER), str(anchor_file)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"kardeş-alıcı DONUK-çıpa RED: {r.stdout} {r.stderr}"


def test_canonical_copy_agrees_with_producer(tmp_path):
    """Kanonik kopya da DONUK-çıpayı KABUL eder (kardeşsiz-kanıt, her koşumda)."""
    anchor_file = tmp_path / "cipa.jsonl"
    anchor_file.write_text(
        tamga_anchor_json(_make_bundle(tmp_path), agent_label="ag-p") + "\n",
        encoding="utf-8")
    r = subprocess.run([sys.executable, str(CANONICAL_RECEIVER), str(anchor_file)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"kanonik-alıcı DONUK-çıpa RED: {r.stdout} {r.stderr}"


# ------------------------------------------------------- 2) payee kayıt-defteri

def test_build_batch_derives_and_registers_payee(tmp_path):
    """Ledger-kimliği serbest dizge olsa bile batch ÜRETİLİR: türetme
    açık-belingi + kayıt-altı (sessiz-türetme kanıta bağlanır) — test_193/201."""
    led1 = _make_ledger(tmp_path, "müşteri-x", "d1")
    led2 = _make_ledger(tmp_path, "müşteri-x", "d2")
    try:
        b1 = build_settlement_batch(led1, "müşteri-x", chain_id=1,
                                    contract=CONTRACT, from_address=FROM)
        b2 = build_settlement_batch(led2, "müşteri-x", chain_id=1,
                                    contract=CONTRACT, from_address=FROM)
        assert b1.payee_address.startswith("0x") and len(b1.payee_address) == 42
        # türetme deterministik: bağımsız-ledger aynı agent → aynı payee
        assert b2.payee_address == b1.payee_address
        # calldata'daki agent-alanı artık payee (12-sıfır-pad'den sonra adres)
        raw = bytes.fromhex(b1.calldata[2:])
        assert raw[16:36] == bytes.fromhex(b1.payee_address[2:].lower())
    finally:
        led1.close()
        led2.close()


def test_register_payee_validates_and_locks():
    assert register_payee("sat-a", OTHER) == OTHER
    # aynı-adres idempotent
    assert register_payee("sat-a", OTHER) == OTHER
    # farklı-adres RED (sessiz-yeniden-yönlendirme kapanır)
    with pytest.raises(SettlementError, match="çakışma"):
        register_payee("sat-a", CONTRACT)
    # ledger-kimliği adres-şekli DEĞİL → RED
    with pytest.raises(SettlementError, match="40-hex"):
        register_payee("sat-b", "sat-b")


def test_explicit_payee_wins_and_binds(tmp_path):
    """Açık payee: kayıt-defterine bağlanır + calldata onu taşır."""
    led = _make_ledger(tmp_path, "sat-exp", "expl")
    try:
        b = build_settlement_batch(led, "sat-exp", chain_id=1,
                                   contract=CONTRACT, from_address=FROM,
                                   payee_address=OTHER)
        assert b.payee_address == OTHER
        raw = bytes.fromhex(b.calldata[2:])
        assert raw[16:36] == bytes.fromhex(OTHER[2:].lower())
        # kayıt-defteri artık sat-exp → OTHER (aynı-adres yeniden-kayıt ok)
        assert register_payee("sat-exp", OTHER) == OTHER
    finally:
        led.close()


def test_derive_is_deterministic_and_salt_bound():
    a1 = derive_payee_address("müşteri-x")
    a2 = derive_payee_address("müşteri-x")
    a3 = derive_payee_address("müşteri-x", salt="farklı-salt")
    assert a1 == a2 and a1 != a3
    assert len(a1) == 42 and a1.startswith("0x")
    with pytest.raises(SettlementError, match="40-hex"):
        register_payee("sat-c", derive_payee_address("sat-c")[:-1] + "g")  # hex-dışı
