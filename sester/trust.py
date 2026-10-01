"""SESTER trust katmani — x402 `agent-trust` extension (issue #1777).

2026-10-01 — [#1777](https://github.com/x402-foundation/x402/issues/1777)
"agent-trust — DID-based identity and trust scoring for x402 payments"
tartismasindaki dort bosugun ikisini doldurur:

1. **Counterparty trustworthiness degerlendirmesi** — ödeme ONCESI
   (mevcut reputation module'u sonrasi icindi; bu modül öncesi)
2. **Trust-based pricing** — güvenilir ajanlara indirim (ücretlendirme
   sinyali olarak trust score)

Kasitli olarak v0-disi birakanlar (architecture decision):
    - **DID tabanli kimlik kaniti (#1)**: tam DID çözümleme ag bagimlidir;
      biz yalniz `did:sester:` tanimayici formatini dogrulariz — çözümleme
      (resolution) cagirmaciya birakilir. Wallet-imzasi akisi zaten
      x402/SESTER'da vardir; burada onu tekrar etmeyiz.
    - **Mutual auth (#4)**: TLS katmani görevidir, ödeme katmaninin degil.

Guvenlik kontrati (cok onemli):
    Trust score HICBIR ZAMAN DENY/ALLOW kararini degistirmez — yalniz
    fiyatlandirmayi etkiler. Güveni politika kararina baglamak, "guvenilir"
    ajanlara otomatik onay demektir; bu da fail-closed kontratini bozar.
    Trust bir *ekonomik sinyaldir*, bir *yetki degildir*.

Matematik:
    trust = reputation_score * (1 - attestation_discount) +
            Σ(attestation.weight * attestor_reputation) /
            Σ(attestor_reputation) * attestation_discount
    Basit ve sinirli: attestation'lar bilincli olarak kucuk tutulur
    (varsayilan agirlik 1.0), ve toplam trust [0,1] araliginda kalir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DID_PREFIX = "did:sester:"


@dataclass(frozen=True)
class Attestation:
    """Baska bir ajanin bu ajan icin 'guvenilir' demesi.

    attestor: kanitlayan ajan (kendi reputation'i agirligi belirler)
    subject: kanitlanan ajan
    weight: [0,1] kanit gucu (varsayilan 1.0)
    """

    attestor: str
    subject: str
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError(f"attestation agirlik [0,1] olmali: {self.weight}")
        if self.attestor == self.subject:
            # kendini kanitlama = sifir bilgi (self-attestation kullanilamaz)
            raise ValueError("self-attestation gecersizdir")


@dataclass(frozen=True)
class TrustScore:
    """Tek ajan icin guven puani [0,1] + nasil hesaplandigi (denetim icin)."""

    agent: str
    score: float
    base: float
    attestations_used: int
    floor_applied: float = 0.0

    @property
    def tier(self) -> str:
        """Insan-okunur sinif (gosterim/fiyatlandirma etiketi icin)."""
        if self.score >= 0.9:
            return "platinum"
        if self.score >= 0.75:
            return "gold"
        if self.score >= 0.5:
            return "silver"
        return "bronze"


def parse_did(did: str) -> str:
    """`did:sester:<agent-id>` → agent-id.

    did:key/w3c çözümlemesi YAPMAZ — yalniz kendi metodumuzu tanir.
    Amac: x402 `Payer-DID` basligindan ajan kimligi cikarip reputation
    anahtarina cevirmek. Hatali format → ValueError (fail-loud).
    """
    if not did.startswith(DID_PREFIX):
        raise ValueError(f"desteklenmeyen DID metodu: {did[:24]!r}")
    agent = did[len(DID_PREFIX):]
    if not agent:
        raise ValueError("DID bos ajan tanimlayicisi")
    return agent


def assess_trust(
    agent: str,
    base_score: float,
    attestations: list[Attestation] | None = None,
    attestor_scores: dict[str, float] | None = None,
    attestation_discount: float = 0.3,
) -> TrustScore:
    """Ajanin guven puanini hesapla (ödeme ONCESI).

    base_score: reputation.score gibi ozel gecmis puani [0,1]
    attestations: diger ajanlarin kanitlari (opsiyonel)
    attestor_scores: her kanitlayicinin kendi reputation puani
        (verilmezse tum agirliklar esit sayilir = 1.0)
    attestation_discount: kanitlarin maksimum etkisi [0,1]
        (varsayilan 0.3: ozel gecmis her zaman baskindir)

    Guvenilirlik: sonuc [0,1] araliginda sinirlanir (bounds).
    """
    if not 0.0 <= base_score <= 1.0:
        raise ValueError(f"base_score [0,1] olmali: {base_score}")
    if not 0.0 <= attestation_discount <= 1.0:
        raise ValueError(
            f"attestation_discount [0,1] olmali: {attestation_discount}"
        )

    atts = [a for a in (attestations or []) if a.subject == agent]
    if not atts:
        return TrustScore(
            agent=agent, score=base_score, base=base_score,
            attestations_used=0,
        )

    scores = attestor_scores or {}
    # agirlikli kanit ortalamasi (kanitlayicinin reputation'i agirlik)
    total_w = 0.0
    weighted = 0.0
    for a in atts:
        w = a.weight * max(0.0, min(1.0, scores.get(a.attestor, 1.0)))
        total_w += w
        weighted += w
    if total_w <= 0.0:
        return TrustScore(
            agent=agent, score=base_score, base=base_score,
            attestations_used=0,
        )

    att_score = min(1.0, weighted / total_w)  # butun agirliklar 1.0 ise 1.0
    blended = base_score * (1.0 - attestation_discount) + \
        att_score * attestation_discount
    # bounds: asla [0,1] disina cikma
    blended = max(0.0, min(1.0, blended))
    return TrustScore(
        agent=agent, score=blended, base=base_score,
        attestations_used=len(atts),
    )


def trust_price(
    base_price_minor: int,
    trust_score: float,
    floor_pct: float = 0.5,
    max_discount_pct: float = 0.25,
) -> int:
    """Guvene dayali fiyatlandirma — güvenilir ajanlara indirim.

    base_price_minor: taban fiyat (minor units)
    trust_score: [0,1]
    floor_pct: fiyat bu oranda altina DUSEMEZ (varsayilan %50)
    max_discount_pct: maksimum indirim orani (varsayilan %25)

    Ekonomik sinirlar (guvenlik kadar onemli):
    - indirim yalnizca score > 0.5'ten baslar (baseline bronze/silver siniri)
    - fiyat asla tabanin floor_pct'si altina inmez
    - sonuc >= 0 (int minor units)
    """
    if base_price_minor < 0:
        raise ValueError("negatif taban fiyat")
    if not 0.0 <= trust_score <= 1.0:
        raise ValueError(f"trust_score [0,1] olmali: {trust_score}")
    if not 0.0 < floor_pct <= 1.0:
        raise ValueError(f"floor_pct (0,1] olmali: {floor_pct}")
    if not 0.0 <= max_discount_pct <= 1.0:
        raise ValueError(f"max_discount_pct [0,1] olmali: {max_discount_pct}")

    floor = max(0, int(base_price_minor * floor_pct))
    # indirim yalniz 0.5 ustunde (lineer 0.5→0 indirim, 1.0→max)
    if trust_score <= 0.5:
        return max(floor, base_price_minor)
    frac = (trust_score - 0.5) / 0.5  # [0,1]
    discount = frac * max_discount_pct
    discounted = int(round(base_price_minor * (1.0 - discount)))
    return max(floor, min(base_price_minor, discounted))
