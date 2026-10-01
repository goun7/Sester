"""SESTER agreement-session — x402 #3646 terms-bound lifecycle.

2026-10-01 — [#3646](https://github.com/x402-foundation/x402/issues/3646)
"agreement-session — terms-bound lifecycle across x402 payments"

Problem: bir ajan-iliskisi birden fazla bagimsiz x402 ödemeyi TEK bir
anlasma cercevesinde gerceklestirir. x402 her ödemeyi settle eder ama
aralarinda ortak bir tanimlayici veya yasam-dongusu YOK.

Sester'in halihazirda sundugu 7 yetenek bu bosugun TAM karsiligidir:
  1. terms kabulü        → policy kurallari
  2. spending budget     → daily_quota + agreement budget
  3. birden fazla ödeme  → append-only ledger
  4. ödemeyi baglama     → her event agreement_id tasiyor
  5. crash sonrasi kanit → hash-chain (verify_chain)
  6. budget dolunca dur  → remaining() <= 0
  7. dogrulanabilir kayit→ export() + verify_chain()

GUVENLIK KONTRATI:
    AgreementSession HICBIR ZAMAN ödeme yapmaz veya onaylar — o bir
    *gözlem ve sinirlama* katmanidir. Ödeme yine SesterMeter'dan gecer.
    Bu modül ledger'a sadece okur + agreement kayitlari yazar
    (yeni event-type EKLEMEZ — mevcut 'permission_decision' payload'unda
    agreement_id tasiyarak, taksonomiyi genisletmeden).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

# payload icinde agreement'i baglayan anahtar (event taksonomisini
# genisletmeden — permission_decision payload'inda tasiyoruz)
AGREEMENT_KEY = "agreement_id"


@dataclass(frozen=True)
class Terms:
    """Anlasma sartlari (degismez — imzalandiktan sonra)."""

    agreement_id: str
    budget_minor: int        # toplam harcama siniri (minor units)
    expires_at: float        # unix epoch; 0 = suresiz
    terms_version: str = "1.0"
    description: str = ""

    def __post_init__(self) -> None:
        if self.budget_minor < 0:
            raise ValueError("negatif budget")
        if not self.agreement_id:
            raise ValueError("bos agreement_id")

    def expired(self, now: float | None = None) -> bool:
        if self.expires_at <= 0:
            return False
        t = time.time() if now is None else now
        return t >= self.expires_at

    @property
    def is_active(self) -> bool:
        """Süresi dolmamış (budget'suz hâli — budget state'te)."""
        return not self.expired()


@dataclass
class AgreementState:
    """Anlasmanin canli durumu (ledger'dan turetilir)."""

    terms: Terms
    spent_minor: int = 0
    payments: int = 0
    last_event_seq: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.terms.budget_minor - self.spent_minor)

    @property
    def budget_exhausted(self) -> bool:
        return self.terms.budget_minor > 0 and self.spent_minor >= self.terms.budget_minor

    @property
    def is_active(self) -> bool:
        return not self.terms.expired() and not self.budget_exhausted


class AgreementSession:
    """Terms-bound lifecycle — ledger uzerinde, crash-safe.

    Sadece OKUR + agreement kaydini payload icinde tasiyan bir
    yardimci fonksiyon sunar (bind_payment). Append yine cagiriciya ait.
    """

    def __init__(self, terms: Terms) -> None:
        self.terms = terms

    @property
    def is_active(self) -> bool:
        """Terms bazli: suresi dolmamissa aktif (budget state ile takip)."""
        return self.terms.is_active

    def bind_payment(self, agent: str, resource: str,
                     state: AgreementState | None = None) -> dict:
        """Bir permission_decision payload'una agreement baglama ekler.

        state verilirse budget doluysa reddeder (fail-closed).
        Cagirici bunu ledger.append(payload=...) ile yazar.
        """
        if self.terms.expired():
            raise ValueError(
                f"agreement {self.terms.agreement_id} suresi dolmus"
            )
        if state is not None and state.budget_exhausted:
            raise ValueError(
                f"agreement {self.terms.agreement_id} budget dolu "
                f"({state.spent_minor}/{self.terms.budget_minor} minor)"
            )
        return {
            "decision": "allow",
            AGREEMENT_KEY: self.terms.agreement_id,
            "agent": agent,
            "resource": resource,
        }

    def state_from(self, spent_minor: int, payments: int,
                   last_seq: int = 0) -> AgreementState:
        """Ledger'dan okunan degerlerle durum olustur."""
        return AgreementState(
            terms=self.terms,
            spent_minor=spent_minor,
            payments=payments,
            last_event_seq=last_seq,
        )


def agreement_filter(payload: dict | None, agreement_id: str) -> bool:
    """Bir ledger event payload'inin bu agreement'a ait olup olmadigi."""
    if not payload:
        return False
    return payload.get(AGREEMENT_KEY) == agreement_id
