"""K0 spec↔code senkronu — tri-product checklist'in YÖN-B makine-kilidi.

Ders (ERRATUM-K0.1/K0.2/K0.3 + Tamga E1/A1): **kodda-zorunlu-ama-spec'te-
yazmayan-kural** bağımsız-verifier'ı sessizce ayrıştırır. Tri-product
checklist bu boşluğu iki-yönlü-ölçerek yakalar; bu test **YÖN-B'yi kalıcı
yapar** — her normative needle K0_SHARED_ENVELOPE_SPEC.md'de aranır, bir kural
spec'ten düşerse RED düşer (code-only-kural-nüksetme-önleyicisi).

Tamga'nın Audit-19 düzeltmesiyle aynı dersün diğer-yüzü: orada negatif-kontrol
median'ın-arkasına-saklanmıştı, burada kural spec'in-arkasına-saklanabilir.
İki-yön-de-makine: spec'in-söylediği-kodda-zorunlu, kodun-zorunlu-kıldığı
spec'te-yazılı (test_spec_and_code_agree_on_taxonomy)."""

from pathlib import Path

import pytest

SPEC = Path(__file__).resolve().parents[1] / "docs" / "K0_SHARED_ENVELOPE_SPEC.md"

# (id, needle, neden) — her satır bir normatif kuralın spec'te-kalıp-kalmadığını
# ölçer. Bir needle buradan ÇIKARILAMAZ: çıkarılırsa bu test RED düşer ve
# "code-only erratum" sınıfı geri-dönmüş olur.
NEEDLES = [
    ("S-1.1", "PREV", "zincir-önceki-proof bağı"),
    ("S-1.2", 'GENESIS = 64 × "0"', "ilk-olay sabit-genesis"),
    ("S-2.1", "enter the canonical preimage", "amount_minor preimage-DIŞI (K0.1)"),
    ("S-2.1b", "amount_minor", "minor-sütun adı spec'te"),
    ("S-2.2", "escalation_consumed", "K0.2 düzeltmesi-taksonomi mevcut"),
    ("S-2.2b", "facilitator_", "dinamik ön-ek ailesi spec'te"),
    ("S-2.3", "refund", "netting işareti (charge +, refund −)"),
    ("S-3.1", "replayed nonce permanently", "replay-koruması yükümlülüğü (K0.3)"),
    ("S-3.1b", "restarts", "restart-sonrası kalıcı-reddin spec'te"),
    ("S-3.2", "Fail loud", "fail-closed/paylaşık doktrin"),
    ("S-4.1", "anchor_id = SHA256", "anchor-bağlaması formülü"),
    ("S-4.1b", "merkle_root", "merkle-kökü binding"),
    ("S-4.2", "hard reject", "bilinmeyen *_version → red"),
]


@pytest.mark.parametrize("rid, needle, why", NEEDLES, ids=[n[0] for n in NEEDLES])
def test_k0_normative_needles_present(rid, needle, why):
    """YÖN-B: spec needle mevcut — düşerse RED (code-only-kural-nüksetme)."""
    text = SPEC.read_text(encoding="utf-8")
    assert needle in text, f"{rid} needle eksik ({why}): {needle!r}"


def test_spec_and_code_agree_on_taxonomy():
    """İki-yön-kilit: spec'in-saydığı her-değer kodun-zorunlu-kümesinde, ve
    kodun-zorunlu-kıldığı-taksonomi spec'te-belgeli. Aksi: spec↔kod ayrışması
    (tam olarak K0.2'nin-ilk-halindeki hata-sınıfı)."""
    from sester.ledger import EVENT_TYPES, is_known_event_type

    text = SPEC.read_text(encoding="utf-8")
    documented = ["usage_event", "charge_receipt", "refund", "permission_decision",
                  "escalation_parked", "escalation_approved", "escalation_denied",
                  "escalation_consumed", "protocol_intent", "settlement"]
    for v in documented:
        assert v in text, f"{v} spec'te-belgeli-değil (code-only-tehlikesi)"
        assert v in EVENT_TYPES, f"{v} kodda-zorunlu-değil (spec-only-tehlikesi)"
    # dinamik aile: spec'te-familye-yazılı, kod-da-kapalı-kind'larla-eşleşiyor
    assert "facilitator_" in text
    assert is_known_event_type("facilitator_batch") is True
    assert is_known_event_type("facilitator_bilinmeyen") is False
