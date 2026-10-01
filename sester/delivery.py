"""SESTER delivery attestation — x402 #1195 Settlement Attestation Receipt.

2026-10-01 — [#1195](https://github.com/x402-foundation/x402/issues/1195)
"Settlement Attestation Receipt (SAR) — canonical delivery proof format"

Problem: x402 odemenin YAPILDIGINI kanitlar; **TESLIMATIN yapildigini
kanitlamaz.** Escrow serbest birakmadan, reputation guncellemeden,
DAG orchestrator devam etmeden once su soruyu cevaplamali:

    "Ajan, odemesi yapilan seyi GERCEKTEN teslim etti mi?"

#2833 ile ayni eksiklik, farklı açidan:
  - #2833: volume is not trust (wash-trade)
  - #1195: settlement is not delivery (self-report yetersiz)

Tasarim karari (architecture decision):
    YENI event-type EKLENMEZ — EVENT_TYPES taksonomisini genisletmek
    fail-closed kontratini zayiflatir (bilinmeyen-tip reddi). Bunun
    yerine mevcut `charge_receipt` payload'ina DELIVERY anahtarlari
    eklenir: teslimat kaniti odeme kaydina BAGLANIR (atomic varsayim:
    odeme + teslimat ayni ledger'da, ayni hash-chain icinde).

SAR formati (minimal, #1195'in "canonical format" hedefine paralel):
    delivery_id    — benzersiz teslimat tanimlayicisi
    delivered_at   — epoch
    content_hash   — teslim edilen icerigin sha256 (opsiyonel; gizlilik)
    attestor       — teslimati onaylayan (satici veya tarafsiz oracle)
    verdict        — delivered | partial | failed
    proof_ref      — tarafsiz kaynak (#2887 oracle pattern'i ile ayni)

GUVENLIK:
    - `failed` verdict'u de YAZILIR (aeoess #2332 kurali: reddin
      pozitif artifakti — basarisiz teslimat sessiz degil)
    - self-attestation reddedilir (attestor == seller TEHLIKELI;
      #1195: "trusts the agent's self-report. That's not a foundation")
      → attestor satici DEGILSE oracle_ref ZORUNLU
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

# charge_receipt payload'inda delivery baglama anahtarlari
DELIVERY_KEY = "delivery"
ATTESTOR_SELLER = "seller"

VERDICT_DELIVERED = "delivered"
VERDICT_PARTIAL = "partial"
VERDICT_FAILED = "failed"
_VALID_VERDICTS = {VERDICT_DELIVERED, VERDICT_PARTIAL, VERDICT_FAILED}


@dataclass(frozen=True)
class DeliveryReceipt:
    """Minimal teslimat kani — #1195 SAR formatina paralel."""

    delivery_id: str
    delivered_at: float
    verdict: str
    attestor: str
    content_hash: str = ""
    proof_ref: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in _VALID_VERDICTS:
            raise ValueError(
                f"gecersiz verdict {self.verdict!r}; "
                f"one of {sorted(_VALID_VERDICTS)}"
            )
        if not self.delivery_id:
            raise ValueError("bos delivery_id")
        # self-attestation kapatildi: satici kendi teslimatini onaylayamaz
        if self.attestor == ATTESTOR_SELLER and not self.proof_ref:
            raise ValueError(
                "satici self-attestation — proof_ref (tarafsiz kaynak) zorunlu"
            )

    def as_payload(self) -> dict:
        """charge_receipt payload'ina eklenecek delivery blogu."""
        out = {
            "delivery_id": self.delivery_id,
            "delivered_at": self.delivered_at,
            "verdict": self.verdict,
            "attestor": self.attestor,
        }
        if self.content_hash:
            out["content_hash"] = self.content_hash
        if self.proof_ref:
            out["proof_ref"] = self.proof_ref
        return out


def content_hash_of(data: bytes) -> str:
    """Teslim edilen icerigin sha256'i (gizlilik: icerik aciklanmaz)."""
    return hashlib.sha256(data).hexdigest()


def attested_receipt(delivery_id: str, verdict: str, attestor: str,
                     content: bytes | None = None,
                     proof_ref: str = "",
                     now: float | None = None) -> DeliveryReceipt:
    """Teslimat kani olustur — test/entegrasyon icin kolay yol."""
    return DeliveryReceipt(
        delivery_id=delivery_id,
        delivered_at=time.time() if now is None else now,
        verdict=verdict,
        attestor=attestor,
        content_hash=content_hash_of(content) if content is not None else "",
        proof_ref=proof_ref,
    )


def extract_delivery(charge_payload: dict | None) -> dict | None:
    """charge_receipt payload'indan delivery blogunu oku."""
    if not charge_payload:
        return None
    d = charge_payload.get(DELIVERY_KEY)
    return d if isinstance(d, dict) else None
