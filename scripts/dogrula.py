#!/usr/bin/env python3
"""Alıcı-tarafı kanıt-dogrulayıcı — 81-MERGEN / müşteri-denetçisi perspektifi.

Bu script BİLGİNCE sester kütüphanesini İÇERMEZ (yalnız stdlib: json + hashlib):
kanıt-bundle'ı üretenden bağımsız doğrulanır — 63↔81 kontratının S4 kabulü.

Kullanım:  python scripts/dogrula.py adoption/s1-kanit-bundle.json
Çıkış:     0 = SAĞLAM, 1 = KIRIK (neden yazılır), 3 = SAĞLAM-AMA-UYARI
           (bilinmeyen-event_type — K0 §7 rule 9 okuma-kapısı; --strict ile
           bu-uyarı RED'e-dönüşür, bkz. aşağıda)

Bilinmeyen-tip davranışı (K0 §7 rule 9, Tamga AT-060-aynası): kanıt-zinciri
GREEN-geçse-bile bir-operatörün doğrudan-yazdığı bilinmeyen-event_type sessizce
geçemez. Varsayılan WARN (+exit-3); --strict ile RED. Üçüncü-seçenek-yasak:
alıcı ya-değerlendirir-ya-belgeler — sessiz-geçiş-yok.
"""

from __future__ import annotations

import hashlib
import json
import sys

GENESIS = "0" * 64

# K0 §1-çekirdek tipler (DONUK kablo-kimliği ile-aynı-küme). --known-types
# ile-açık-geçersiz-kılınabilir; sabit-liste-ancak-çekirdek-küme-stabil-
# olduğu-için-kabul-edilebilir (kirlenme-yapılamaz: bu-küme asla-değişmez,
# aksi-halde-alıcılar-zaten-kırılırdı).
CORE_EVENT_TYPES = frozenset({
    "charge_receipt", "refund", "permission_decision", "policy_denied",
    "escalation_parked", "escalation_approved", "escalation_denied",
    "escalation_consumed", "protocol_intent", "settlement", "webhook_delivery",
})
# Dinamik ön-ek aileleri (K0 §2): "{ön-ek}{kind}" — çekirdek-olmayan-ama-
# bilinen-kalıp; kural-9-bunları-da-değerlendirir (kapalı-kind-içinde-iseler).
_EVENT_TYPE_FAMILIES = ("facilitator_", "tenderix_")


def is_known_event_type(t: str) -> bool:
    """K0-rule-9 okuma-kapısı-yardımcısı (sester-free, pür-stdlib)."""
    if t in CORE_EVENT_TYPES:
        return True
    return any(t.startswith(pfx) for pfx in _EVENT_TYPE_FAMILIES)


def unknown_event_types(events: list) -> set:
    """Alıcı-tarafı-taksonomi-asserti — K0-rule-9'un-yardımcısı.
    Karar-alıcıda: varsayılan-warn, --strict ile-reject."""
    return {e["event_type"] for e in events
            if not is_known_event_type(e["event_type"])}


def merkle(leaves: list[str]) -> str:
    if not leaves:
        return GENESIS
    layer = list(leaves)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [hashlib.sha256((a + b).encode()).hexdigest()
                 for a, b in zip(layer[::2], layer[1::2])]
    return layer[0]


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("-")]
    flags = {a for a in argv[1:] if a.startswith("-")}
    if len(args) != 1:
        print("kullanım: dogrula.py [--strict] [--known-types=t1,t2] <bundle.json>")
        return 2
    strict = "--strict" in flags
    known_override = None
    for f in flags:
        if f.startswith("--known-types="):
            known_override = frozenset(
                t for t in f[len("--known-types="):].split(",") if t)
    if known_override is not None:
        # okuma-kapısını-alıcının-kümesiyle-değiştir (kural-9: karar-alıcıda)
        globals()["CORE_EVENT_TYPES"] = known_override
        globals()["_EVENT_TYPE_FAMILIES"] = ()

    bundle = json.loads(open(args[0], encoding="utf-8").read())
    events = bundle["events"]
    # Ekonomik-tip-kapısı-ÖNCE (Tamga AT-062): canonical-hesabı `:.6f` ile
    # string-amount'ta-crash-verir; tip-temizliği-olmadan-zincir-doğrulama
    # anlamsız-olacağı-için-bu-kontrol-önce-gelir (fail-early-değil-fail-
    # açık-reason-ile).
    bad_amounts = []
    for ev in events:
        if ev["event_type"] != "charge_receipt":
            continue
        am = ev["amount"]
        if isinstance(am, bool) or not isinstance(am, (int, float)):
            bad_amounts.append((ev["seq"], f"sayı-değil: {am!r}"))
        elif am < 0:
            bad_amounts.append((ev["seq"], f"negatif: {am}"))

    prev = GENESIS
    proofs: list[str] = []
    for ev in events:
        # bool/string-amount'u-burada-crash-etmeden-formatla (tip-uyarısı
        # yukarıda-zaten-basıldı-ve-exit-koduna-yansıdı; zincir-doğrulaması
        # bağımsız-gerçeklik-kontrolü-olarak-devam-eder)
        am = ev["amount"]
        am_s = (f"{float(am):.6f}"
                if isinstance(am, (int, float)) and not isinstance(am, bool)
                else str(am))
        if ev["prev_proof"] != prev:
            print(f"✗ zincir-kopması @seq={ev['seq']}")
            return 1
        canonical = "|".join([
            f"{ev['ts']:.6f}", ev["event_type"], ev["agent_id"], ev["host"],
            am_s, ev["payload"], prev,
        ])
        h = hashlib.sha256(canonical.encode()).hexdigest()
        if h != ev["proof"]:
            print(f"✗ proof-uyuşmazlığı @seq={ev['seq']} — veri-değiştirilmiş")
            return 1
        proofs.append(h)
        prev = h
    if bundle["head"] != prev:
        print("✗ head uyuşmuyor")
        return 1
    if bundle["merkle_root"] != merkle(proofs):
        print("✗ merkle-kökü uyuşmuyor")
        return 1

    # K0 §7 rule-9 okuma-kapısı (Tamga AT-060-aynası): zincir-GREEN-olsa-bile
    # bilinmeyen-event_type sessizce-geçemez — alıcı-değerlendirir-veya-belgeler.
    unknown = unknown_event_types(events)
    if unknown:
        msg = (f"⚠ bilinmeyen-event_type: {sorted(unknown)} — operatör-"
               "doğrudan-yazımı-olabilir (K0 §7 rule 3 opaklık: GREEN-geçer)")
        if strict:
            print(f"✗ RED (strict): {msg}")
            return 1
        print(msg)

    # Ekonomik-okuma-kapısı (Tamga AT-062-aynası): negatif charge_receipt =
    # değer-çıkarma-yolu. spent_today (quota-kararı) charge_receipt'i (+) sayar;
    # operatör-negatif-yazarsa kota-sıfırlanır → limit-aşımı. refund zaten
    # negatif-etkili-AMA-onun-işareti-tipte-amount'da-değil; o-yüzden-kısıt
    # yalnızca charge_receipt'e. bool-tuzağı-da-kapsanır: float(True)==1.0,
    # JSON-bool'u-sayı-giydirir — isinstance-float/int-ve-bool-reddi.
    # (tip-taraması-yukarıda-önce-yapıldı; burada-sadece-karar)
    if bad_amounts:
        detail = "; ".join(f"@{s} {why}" for s, why in bad_amounts[:3])
        msg = (f"⚠ uygunsuz-charge_receipt-amount: {detail} — kota-bypass-"
               "yolu (Tamga AT-062-ekonomik-sınıf)")
        if strict:
            print(f"✗ RED (strict): {msg}")
            return 1
        print(msg)

    agents = sorted({e["agent_id"] for e in events})
    receipts = sum(1 for e in events if e["event_type"] == "charge_receipt")
    total = sum(e["amount"] for e in events
                if e["event_type"] == "charge_receipt"
                and isinstance(e["amount"], (int, float))
                and not isinstance(e["amount"], bool))
    print(f"✓ SAĞLAM: {len(events)} olay · {receipts} ücretli-işlem · toplam {total:.2f}")
    print(f"  ajanlar: {', '.join(agents)}")
    print(f"  head: {prev}")
    print(f"  merkle-kök: {bundle['merkle_root']}")
    return 3 if (unknown or bad_amounts) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
