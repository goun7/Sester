"""Trust modulu testleri — x402 #1777 agent-trust extension paralel.

LEAD 2026-10-01: DID tanima + guven puani + guvene-dayali fiyatlandirma.
Guvenlik kontrati: trust score ASLA DENY/ALLOW degil, yalniz fiyat.
"""

import pytest

from sester.trust import (
    Attestation,
    DID_PREFIX,
    TrustScore,
    assess_trust,
    parse_did,
    trust_price,
)


class TestParseDid:
    def test_gecerli_did_ajani_verir(self):
        assert parse_did(f"{DID_PREFIX}agent-42") == "agent-42"

    def test_baska_metod_reddedilir(self):
        with pytest.raises(ValueError, match="desteklenmeyen DID"):
            parse_did("did:key:z6MkhaXgBZDvotDkL525")

    def test_bos_ajani_reddeder(self):
        with pytest.raises(ValueError, match="bos ajan"):
            parse_did(DID_PREFIX)


class TestAttestation:
    def test_self_attestation_gecersiz(self):
        with pytest.raises(ValueError, match="self-attestation"):
            Attestation(attestor="a1", subject="a1")

    @pytest.mark.parametrize("w", [-0.1, 1.1, 2.0])
    def test_agirlik_aralik_disi_reddedilir(self, w):
        with pytest.raises(ValueError, match="agirlik"):
            Attestation(attestor="a1", subject="a2", weight=w)

    def test_gecerli_attestation(self):
        a = Attestation(attestor="a1", subject="a2", weight=0.5)
        assert a.attestor == "a1" and a.weight == 0.5


class TestAssessTrust:
    def test_attestation_yoksa_base_donar(self):
        t = assess_trust("a1", base_score=0.8)
        assert t.score == 0.8
        assert t.attestations_used == 0

    def test_attestation_base_ile_harmanlanir(self):
        # base 0.8, att 1.0, discount 0.3 → 0.8*0.7 + 1.0*0.3 = 0.86
        t = assess_trust(
            "a1", base_score=0.8,
            attestations=[Attestation(attestor="a2", subject="a1")],
            attestation_discount=0.3,
        )
        assert t.attestations_used == 1
        assert abs(t.score - 0.86) < 1e-9

    def test_dusuk_attestor_reputation_dusuk_etki(self):
        # attestor'un reputation'i 0.0 ise agirlik 0 → att etkisi 0 → base
        t = assess_trust(
            "a1", base_score=0.6,
            attestations=[Attestation(attestor="a2", subject="a1")],
            attestor_scores={"a2": 0.0},
        )
        # weighted=0 → base doner
        assert t.score == 0.6
        assert t.attestations_used == 0  # etkisiz sayildi

    def test_baska_subject_attestation_lanir(self):
        t = assess_trust(
            "a1", base_score=0.5,
            attestations=[Attestation(attestor="a2", subject="baska")],
        )
        assert t.attestations_used == 0
        assert t.score == 0.5

    def test_score_aralikta_kalir(self):
        for base in (0.0, 0.25, 0.5, 0.75, 1.0):
            t = assess_trust(
                "a1", base_score=base,
                attestations=[Attestation(attestor="a2", subject="a1",
                                          weight=1.0)],
            )
            assert 0.0 <= t.score <= 1.0

    def test_base_aralik_disi_reddedilir(self):
        with pytest.raises(ValueError, match="base_score"):
            assess_trust("a1", base_score=1.5)

    def test_tier_esikleri(self):
        assert TrustScore(agent="x", score=0.95, base=0.9,
                          attestations_used=0).tier == "platinum"
        assert TrustScore(agent="x", score=0.8, base=0.8,
                          attestations_used=0).tier == "gold"
        assert TrustScore(agent="x", score=0.6, base=0.6,
                          attestations_used=0).tier == "silver"
        assert TrustScore(agent="x", score=0.3, base=0.3,
                          attestations_used=0).tier == "bronze"


class TestTrustPrice:
    def test_dusuk_score_indirimsiz(self):
        # 0.5 ve altinda indirim yok
        assert trust_price(100_000, 0.0) == 100_000
        assert trust_price(100_000, 0.5) == 100_000

    def test_yuksek_score_indirim_verir(self):
        # 1.0 → %25 indirim → 75000
        p = trust_price(100_000, 1.0, max_discount_pct=0.25)
        assert p == 75_000

    def test_floor_asla_asagi_inmez(self):
        # cok yuksek score ama floor %80 → 80000
        p = trust_price(100_000, 1.0, floor_pct=0.8,
                        max_discount_pct=0.25)
        assert p == 80_000

    def test_ara_deger_lineer(self):
        # 0.75 → (0.75-0.5)/0.5 = 0.5 → %12.5 indirim → 87500
        p = trust_price(100_000, 0.75, max_discount_pct=0.25)
        assert p == 87_500

    def test_negatif_taban_reddedilir(self):
        with pytest.raises(ValueError, match="negatif"):
            trust_price(-1, 0.9)

    def test_score_aralik_disi_reddedilir(self):
        with pytest.raises(ValueError, match="trust_score"):
            trust_price(100_000, 1.2)

    def test_sifir_fiyat_guvenli(self):
        assert trust_price(0, 1.0) == 0
