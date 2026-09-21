"""SESTER settlement testleri — on-chain ödeme-batch'i (v0.4, püür-stdlib).

Çapalar: keccak-256 bilinen-vektörleri (Wikipedia/NIST), merkle özellikleri,
ABI-calldata çözümlemesi, K0-yaprak bağlantısı, fail-closed (bozuk-zincir,
boş-segment), digest determinizmi.
"""

from __future__ import annotations

import pytest

from sester.evidence import produce_bundle
from sester.ledger import Ledger
from sester.settlement import (
    SETTLE_ABI_SIGNATURE,
    SettlementError,
    build_settle_calldata,
    build_settlement_batch,
    keccak256,
    merkle_root_keccak,
)

ADDR = "0x" + "ab" * 20          # 40-hex ajan-cüzdanı
CONTRACT = "0x" + "cd" * 20
FROM = "0x" + "ee" * 20


def test_174_keccak256_known_vectors():
    """Bilinen-vektörler — yanlış keccak = yanlış zincir-kökü; çapa ŞART."""
    assert keccak256(b"").hex() == \
        "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert keccak256(b"abc").hex() == \
        "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"
    assert keccak256(b"The quick brown fox jumps over the lazy dog").hex() == \
        "4d741b6f1eb29cb2a9b9911c82f56fa8d73b04959d3d9d222895df6c0b28aa15"


def test_175_merkle_root_keccak_properties():
    a = keccak256(b"a")
    b = keccak256(b"b")
    c = keccak256(b"c")
    # tek-yaprak = kendisi
    assert merkle_root_keccak([a]) == a
    # çift-yaprak = keccak(a|b)
    assert merkle_root_keccak([a, b]) == keccak256(a + b)
    # tek-sayı: son-yaprak kendisiyle eşlenir (deterministik)
    three = merkle_root_keccak([a, b, c])
    expect = keccak256(keccak256(a + b) + keccak256(c + c))
    assert three == expect
    # boş → fail-closed
    with pytest.raises(SettlementError, match="boş"):
        merkle_root_keccak([])


def test_176_selector_is_keccak_prefix():
    sel = keccak256(SETTLE_ABI_SIGNATURE.encode())[:4]
    assert len(sel) == 4
    cd = build_settle_calldata(agent=ADDR, total_minor=50_000,
                               currency="USDC",
                               evidence_root="0x" + "11" * 32, count=3)
    assert cd.startswith("0x" + sel.hex())
    # sha256 ile KESIN farklı (keccak ≠ sha3-256 pad'i)
    import hashlib
    assert sel != hashlib.sha256(SETTLE_ABI_SIGNATURE.encode()).digest()[:4]


def test_177_calldata_abi_layout_decodable():
    root = "0x" + "11" * 32
    cd = build_settle_calldata(agent=ADDR, total_minor=123_456,
                               currency="USDC", evidence_root=root, count=7)
    raw = bytes.fromhex(cd[2:])
    # head: selector + 5 slot = 4 + 160 byte; tail: string
    selector, head = raw[:4], raw[4:164]
    tail = raw[164:]
    agent = head[0:32]
    total = int.from_bytes(head[32:64], "big")
    str_off = int.from_bytes(head[64:96], "big")
    root_arg = head[96:128]
    count = int.from_bytes(head[128:160], "big")
    assert agent == bytes.fromhex("ab" * 20).rjust(32, b"\x00")
    assert total == 123_456
    assert str_off == 160  # 5*32 — string-tail offset
    assert root_arg == bytes.fromhex("11" * 32)
    assert count == 7
    # tail: USDC-string (length + right-padded)
    assert int.from_bytes(tail[0:32], "big") == 4
    assert tail[32:36] == b"USDC"


def test_178_batch_happy_path_k0_link(tmp_path):
    led = Ledger(tmp_path / "st.sqlite3", secret="s-st")
    led.append("charge_receipt", ADDR, "/weather", 0.05,
               amount_minor=50_000, payload={"nonce": "s1"})
    led.append("charge_receipt", ADDR, "/weather", 0.03,
               amount_minor=30_000, payload={"nonce": "s2"})
    led.append("refund", ADDR, "/weather", 0.02, amount_minor=20_000)

    batch = build_settlement_batch(led, ADDR, chain_id=84532,  # Base-sepolia
                                   contract=CONTRACT, from_address=FROM)
    assert batch.total_minor == 60_000                 # 50k + 30k − 20k
    assert batch.agent == ADDR and batch.currency == "USDC"
    # yapraklar = K0 kanıt-proof'ları
    bundle = produce_bundle(led, agent_id=ADDR)
    assert batch.leaves == [e["proof"] for e in bundle["events"]]
    # kök = keccak-merkle (sha256-bundle-kökünden FARKLI katman)
    assert batch.merkle_root == "0x" + merkle_root_keccak(
        [bytes.fromhex(h) for h in batch.leaves]).hex()
    assert batch.merkle_root[2:] != bundle["merkle_root"]
    # calldata kökü ve sayısı batch ile tutarlı
    raw = bytes.fromhex(batch.calldata[2:])
    assert int.from_bytes(raw[4 + 128:4 + 160], "big") == 3
    assert batch.chain_id == 84532 and batch.event_count == 3
    # zincir SAĞLAM (batch üretimi zinciri bozmaz)
    assert led.verify_chain()


def test_179_fail_closed_empty_and_corrupt(tmp_path):
    led = Ledger(tmp_path / "st2.sqlite3", secret="s-st2")
    # boş-segment → ret
    led.append("charge_receipt", "0x" + "ff" * 20, "/x", 0.01, amount_minor=10_000)
    with pytest.raises(SettlementError, match="kanıt-yok"):
        build_settlement_batch(led, ADDR, chain_id=1,
                               contract=CONTRACT, from_address=FROM)
    # bozuk-zincir → ret (fail-closed)
    led.append("charge_receipt", ADDR, "/weather", 0.05,
               amount_minor=50_000, payload={"nonce": "c1"})
    led.conn.execute("UPDATE events SET amount = 0.99 WHERE agent_id = ?", (ADDR,))
    assert led.verify_chain() is False
    with pytest.raises(SettlementError, match="fail-closed"):
        build_settlement_batch(led, ADDR, chain_id=1,
                               contract=CONTRACT, from_address=FROM)


def test_180_digest_determinism_and_binding(tmp_path, monkeypatch):
    """Aynı içerik (+aynı ts-dizisi) → aynı batch-digest; kontrat-bağı digest'i
    değiştirir (replay-on-other-contract kapanır)."""
    import time as _t

    base = {"t": _t.time()}
    state = {"n": 0}

    def fake():
        state["n"] += 1
        return base["t"] + state["n"] * 0.001

    monkeypatch.setattr(_t, "time", fake)

    def make(name):
        state["n"] = 0  # her senaryo aynı ts-dizisini alır
        led = Ledger(tmp_path / f"{name}.sqlite3", secret="s-det")
        led.append("charge_receipt", ADDR, "/weather", 0.05,
                   amount_minor=50_000, payload={"nonce": "det-1"})
        return led

    b1 = build_settlement_batch(make("d1"), ADDR, chain_id=1,
                                contract=CONTRACT, from_address=FROM)
    b2 = build_settlement_batch(make("d2"), ADDR, chain_id=1,
                                contract=CONTRACT, from_address=FROM)
    assert b1.sha_digest == b2.sha_digest
    # kontrat-bağı: başka kontrat → başka digest (calldata aynı)
    b3 = build_settlement_batch(make("d3"), ADDR, chain_id=1,
                                contract="0x" + "99" * 20, from_address=FROM)
    assert b3.sha_digest != b1.sha_digest
    assert b3.calldata == b1.calldata


def test_181_minor_dual_read_in_batch(tmp_path):
    """Eski-kayıt (NULL kolon) → major'dan türetim; batch tutarı tam-sayı."""
    led = Ledger(tmp_path / "st3.sqlite3", secret="s-st3")
    led.append("charge_receipt", ADDR, "/weather", 0.05)   # major-yol (geri-uyum)
    led.conn.execute("UPDATE events SET amount_minor = NULL")
    batch = build_settlement_batch(led, ADDR, chain_id=1,
                                   contract=CONTRACT, from_address=FROM)
    assert batch.total_minor == 50_000


def test_185_batch_rejects_net_negative(tmp_path):
    """AT-062-ekonomik-ayna (ödeme-katmanı): net-negatif-batch = değer-
    çıkarma-yolu. refund'lar charge'lardan-fazlaysa-agent'ten-para-çekiliyor
    demektir — bu on-chain calldata'ya-gidemez. build_settlement_batch
    append'in-yazma-kapısından-bağımsız-olarak-burada-da-rede-etmeli
    (operatör-doğrudan-SQL-yazımı-append'i-atlayabilir)."""
    led = Ledger(tmp_path / "neg.sqlite3", secret="neg")
    # 1 charge (50 minor) + 3 refund (50'şer) → net -100 minor
    led.append("charge_receipt", ADDR, "/x", 0.50, amount_minor=50,
               payload={"nonce": "c1"})
    for i in range(3):
        led.append("refund", ADDR, "/x", 0.50, amount_minor=50,
                   payload={"nonce": f"r{i}"})
    try:
        with pytest.raises(SettlementError, match="negatif settlement-toplamı"):
            build_settlement_batch(led, ADDR, chain_id=84532, contract=CONTRACT,
                                   from_address=FROM)
    finally:
        led.close()


def test_186_batch_accepts_net_positive_after_refunds(tmp_path):
    """Negatif-kontrolün-yanlış-red-vermediğini-kanıtlar: refund'lar-varken
    net-pozitif-batch-normal-üretilmeli (refund-bir-iade-aracıdır,-yasak-
    değildir; yalnızca-net-eksiyasak)."""
    led = Ledger(tmp_path / "pos.sqlite3", secret="pos")
    led.append("charge_receipt", ADDR, "/x", 1.00, amount_minor=100,
               payload={"nonce": "c1"})
    led.append("refund", ADDR, "/x", 0.25, amount_minor=25,
               payload={"nonce": "r1"})
    try:
        batch = build_settlement_batch(led, ADDR, chain_id=84532,
                                       contract=CONTRACT, from_address=FROM)
        assert batch.total_minor == 75  # 100 - 25
    finally:
        led.close()
