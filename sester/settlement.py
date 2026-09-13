"""SESTER settlement — on-chain ödeme-batch'i (Ethereum-uyumlu, püür-stdlib).

63-A tezi: metering katmanı off-chain kalır, kanıt-köprüsü on-chain'e
taşınabilir. Bu modül ledger'ın bir agent'a ait kapatılmış segmentini tek
on-chain işlem-kanıtına indirger:

  1) kanıt-yaprakları = K0 kanıt-bundle'ı proof-zinciri (sha256-canonical;
     secret'sız-kamuya katman — evidence.py) — zincir-özet değişmez
  2) keccak-256 merkle-kökü: EVM-de yeniden-hesaplanabilir kanıt-kökü
     (Solidity verifyProof ile her olay ayrı kanıtlanabilir)
  3) `settle(address agent, uint256 totalMinor, string currency,
             bytes32 evidenceRoot, uint64 count)` — ABI-encoded calldata
     (püür-stdlib: fonksiyon-selektörü = keccak256(imza)[:4])
  4) chain-id + kontrat + from-adresi batch'e sabitlenir (başka-zincir-replay
     kapanır); tx-imzalama bilinçli v0.4-dışı: imzalayıcı kendi cüzdanıyla
     bu calldata'yı imzalar (non-custodial tez korunur)
  5) v0.5.0 payee-kayıt-defteri: ledger-kimliği (serbest dizge) asla doğrudan
     `address` alanına GEÇİRİLMEZ — para-gideceği-adres ya `register_payee`
     ile bağlanır ya da açık-belingi türetme (`derive_payee_address`)
     KAYIT-EŞLİĞİNDE kullanılır; batch-digest somut adresi taşır
     (sessiz-türetme kanıta bağlanır — fail-closed)

v0.4 tutar-aritmetiği: total_minor tam-sayı — amount_minor kolonundan
(dual-read: eski NULL kayıtlar major'dan türetilir; backfill ile kolonlanır).
Fail-closed: verify_chain() SAĞLAM değilse batch ÜRETİLMEZ.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .evidence import produce_bundle
from .ledger import MINOR

__all__ = [
    "SETTLE_ABI_SIGNATURE",
    "SettlementBatch",
    "SettlementError",
    "build_settle_calldata",
    "build_settlement_batch",
    "derive_payee_address",
    "keccak256",
    "merkle_root_keccak",
    "register_payee",
]


class SettlementError(Exception):
    """Kanıt-zinciri bozuk ya da batch boş — fail-closed ret."""


# ---------------------------------------------------------------- keccak-256
# Keccak-f[1600], Keccak pad (0x01 … 0x80) — Ethereum'un keccak256'sı.
# Referans-vektörlerle (bilinen-digest) testler çapalar; standart-dışı
# implementasyon asla kabul edilmez (fail-closed test-disiplini).

_KECCAK_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A,
    0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
    0x8000000080008081, 0x8000000000008009, 0x000000000000008A,
    0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
    0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
    0x000000000000800A, 0x800000008000000A, 0x8000000080008081,
    0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]

# rho-dönme ofsetleri r[x][y] (Keccak-team tablosu)
_KECCAK_ROT = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]

_U64 = 0xFFFFFFFFFFFFFFFF


def _rol64(x: int, n: int) -> int:
    return ((x << n) | (x >> (64 - n))) & _U64


def _keccak_f(state: list[int]) -> None:
    """Keccak-f[1600]: flat-lane durumu (lane = x + 5*y) üzerinde 24 tur."""
    A = [[state[x + 5 * y] for y in range(5)] for x in range(5)]
    for rnd in range(24):
        # θ
        C = [A[x][0] ^ A[x][1] ^ A[x][2] ^ A[x][3] ^ A[x][4] for x in range(5)]
        D = [C[(x - 1) % 5] ^ _rol64(C[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                A[x][y] ^= D[x]
        # ρ + π
        B = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                B[y][(2 * x + 3 * y) % 5] = _rol64(A[x][y], _KECCAK_ROT[x][y])
        # χ
        NOT = _U64
        for x in range(5):
            for y in range(5):
                A[x][y] = B[x][y] ^ (((B[(x + 1) % 5][y] ^ NOT)
                                      & B[(x + 2) % 5][y]))
        # ι
        A[0][0] ^= _KECCAK_RC[rnd]
    for x in range(5):
        for y in range(5):
            state[x + 5 * y] = A[x][y]


def keccak256(data: bytes) -> bytes:
    """Keccak-256 (Ethereum) — püür-stdlib. SHA3-256 DEĞİL (pad-biti 0x01)."""
    rate = 136  # 1088-bit rate (1600 - 512)
    state = [0] * 25
    padded = bytearray(data)
    padded.append(0x01)  # keccak pad — SHA3'ten fark burada (0x06)
    while len(padded) % rate:
        padded.append(0x00)
    padded[-1] |= 0x80

    for off in range(0, len(padded), rate):
        for i in range(rate // 8):
            state[i] ^= int.from_bytes(padded[off + i * 8:off + i * 8 + 8],
                                       "little")
        _keccak_f(state)
    return b"".join(state[i].to_bytes(8, "little") for i in range(4))


# ----------------------------------------------------------- keccak merkle

def merkle_root_keccak(leaves: list[bytes]) -> bytes:
    """Keccak-256 merkle-kökü: tek-yaprak = kendisi; çift-yaprak =
    keccak(sol|sağ); tek-kardeş kendisiyle eşlenir (EVM-kanıt-alışkanlığı)."""
    if not leaves:
        raise SettlementError("merkle yaprak-listesi boş")
    level = [bytes(leaf) for leaf in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [keccak256(level[i] + level[i + 1])
                 for i in range(0, len(level), 2)]
    return level[0]


# ------------------------------------------------------- payee kayıt-defteri
# v0.5.0 düzeltmesi: ledger-kimliği ("sat3", "müşteri-x" gibi serbest dizge)
# EVM `address` alanına adres-şeklinde DEĞİLDİR — direkt geçiş SettlementError
# (40-hex değil) ya da daha kötüsü sessiz-türetme üretir. Para-gideceği-adres
# YA kayıt-edilir YA açık-belingi türetmeyle kayıt-altına alınır.

_PAYEE_REGISTRY: dict[str, str] = {}


def register_payee(agent_id: str, address: str) -> str:
    """agent_id → EVM-adres bağını kaydet (idempotent; kanonik form 0x-önekli).
    Aynı-agent-farklı-adres RED olur (sessiz-yeniden-yönlendirme kapanır).
    Defter kanonik 0x-formu saklar — ilk ve tekrar-üretim AYNI digest'i üretir."""
    a = str(address).lower().removeprefix("0x")
    if len(a) != 40 or not all(c in "0123456789abcdef" for c in a):
        raise SettlementError(f"payee adresi 40-hex değil: {address}")
    key = str(agent_id)
    prev = _PAYEE_REGISTRY.get(key)
    if prev is not None and prev != "0x" + a:
        raise SettlementError(
            f"payee çakışması: {agent_id} zaten {prev} adresine kayıtlı")
    _PAYEE_REGISTRY[key] = "0x" + a
    return "0x" + a


def derive_payee_address(agent_id: str, *, salt: str = "sester-payee-v1") -> str:
    """Açık-belingi türetme: payee = keccak256(salt|agent_id)[:20].
    Türetme yalnız kayıt-eşliğinde anlamlıdır — build_settlement_batch bu
    fonksiyonu KAYIT-YAPARAK kullanır; digest somut adresi taşır."""
    return "0x" + keccak256(f"{salt}|{agent_id}".encode())[:20].hex()


# ------------------------------------------------------- settlement batch

SETTLE_ABI_SIGNATURE = "settle(address,uint256,string,bytes32,uint64)"
_SETTLE_SELECTOR = keccak256(SETTLE_ABI_SIGNATURE.encode())[:4]


@dataclass(frozen=True)
class SettlementBatch:
    """On-chain'e taşınan ödeme-batch'i — fail-closed üretim-kanıtı."""
    agent: str                # ledger-kimliği (denetim-iz; on-chain DEĞİL)
    payee_address: str        # para-gideceği EVM-adresi (0x…; kayıt-defterinden)
    chain_id: int
    contract: str
    from_address: str
    total_minor: int
    currency: str
    event_count: int
    merkle_root: str          # keccak-256 (0x-hex)
    leaves: list[str]         # K0 kanıt-proof'ları (sha256-hex)
    calldata: str             # ABI-encoded settle(...) (0x-hex)
    sha_digest: str           # batch özeti (denetim-iz; agent'a raporlanır)


def build_settlement_batch(ledger: Any, agent_id: str, *, chain_id: int,
                           contract: str, from_address: str,
                           currency: str = "USDC",
                           payee_address: str | None = None) -> SettlementBatch:
    """Ledger'ın agent-segmentini on-chain-batch'e indirger.
    Fail-closed: verify_chain() bozuksa, segment boşsa → SettlementError.
    Payee: `payee_address` verilirse kayıt-defterine bağlanır; verilmezse
    önce kayıt-defterine bakılır, yoksa açık-belingi türetip KAYDEDER."""
    if not ledger.verify_chain():
        raise SettlementError("zincir SAĞLAM değil — settlement üretilemez (fail-closed)")

    bundle = produce_bundle(ledger, agent_id=agent_id)
    events = bundle.get("events", [])
    if not events:
        raise SettlementError(f"agent {agent_id} için kanıt-yok — batch boş")

    # yapraklar = K0 kanıt-proof'ları (sha256-canonical; secret'sız katman)
    leaves = [str(ev["proof"]) for ev in events]

    # payee: açık-verilirse kaydet; yoksa kayıt-defteri; o da yoksa türet+kaydet
    if payee_address is not None:
        payee = register_payee(agent_id, payee_address)
    else:
        payee = _PAYEE_REGISTRY.get(str(agent_id)) or register_payee(
            agent_id, derive_payee_address(agent_id))

    # tutar: tam-sayı kolon (dual-read; eski NULL → major-türetim)
    rows = {r["seq"]: r for r in ledger.export_events(agent_id)}
    total = 0
    for ev in events:
        row = rows[ev["seq"]]
        minor = row.get("amount_minor")
        if minor is None:
            minor = int(round(float(row["amount"]) * MINOR))
        if ev["event_type"] == "charge_receipt":
            total += int(minor)
        elif ev["event_type"] == "refund":
            total -= int(minor)

    root = merkle_root_keccak([bytes.fromhex(h) for h in leaves])
    calldata = build_settle_calldata(
        agent=payee, total_minor=total, currency=currency,
        evidence_root="0x" + root.hex(), count=len(events),
    )

    digest = hashlib.sha256(json.dumps({
        "agent": agent_id.lower(), "payee": payee,
        "chain_id": int(chain_id),
        "contract": contract.lower(), "total_minor": total,
        "currency": currency, "root": root.hex(), "leaves": leaves,
    }, sort_keys=True).encode()).hexdigest()

    return SettlementBatch(
        agent=agent_id.lower(), payee_address=payee, chain_id=int(chain_id),
        contract=contract.lower(), from_address=from_address.lower(),
        total_minor=total, currency=currency, event_count=len(events),
        merkle_root="0x" + root.hex(), leaves=leaves, calldata=calldata,
        sha_digest=digest,
    )


# ---------------------------------------------------------------- ABI encode

def _pad_right32(data: bytes) -> bytes:
    return data + b"\x00" * (-len(data) % 32)


def _abi_uint(n: int) -> bytes:
    if n < 0 or n >= 2**256:
        raise SettlementError(f"uint256-dışı: {n}")
    return n.to_bytes(32, "big")


def _abi_address(addr: str) -> bytes:
    a = addr.lower().removeprefix("0x")
    if len(a) != 40:
        raise SettlementError(f"adres 40-hex değil: {addr}")
    return bytes.fromhex(a).rjust(32, b"\x00")


def _abi_string(s: str) -> bytes:
    raw = s.encode()
    return _abi_uint(len(raw)) + _pad_right32(raw)


def build_settle_calldata(*, agent: str, total_minor: int, currency: str,
                          evidence_root: str, count: int) -> str:
    """`settle(address,uint256,string,bytes32,uint64)` → 0x-calldata
    (canonical ABI: head[5] + string-tail)."""
    root_hex = evidence_root.lower().removeprefix("0x")
    if len(root_hex) != 64:
        raise SettlementError("evidence_root 32-byte değil")
    head = b"".join([
        _SETTLE_SELECTOR,
        _abi_address(agent),
        _abi_uint(int(total_minor)),
        _abi_uint(0xA0),                     # string-tail offset (5*32)
        bytes.fromhex(root_hex),             # bytes32
        _abi_uint(int(count) & ((1 << 64) - 1)),
    ])
    return "0x" + (head + _abi_string(currency)).hex()
