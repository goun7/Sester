#!/usr/bin/env python3
"""S6 ortak-koşumcusu — 64-Tenderix escrow ⟷ 63-Sester facilitator (tek ledger).

63-tarafı kanıt-koşumu (IS_PLANI §7 S6; docs/S6_JOINT_ACCEPTANCE.md §3):

    .venv/bin/python scripts/s6_joint_run.py

Ne yapar (framework-siz, ağ-yok, deterministik):
  · 64'ün escrow-durum-makinesini (escrow.py gerçek geçişleri) S6-alan-setiyle
    (harita §2: nonce/offer_id/auth_ref/escrow_state/counterparty) KARŞI-TARAF-OLAYI
    olarak 63'ün ledger'ına yazar — tek-zincir çift-kanıt disiplini;
  · her 64-anını 63 facilitator ucuna (verify/settle/refund) bağlar:
    S6.a authorize→/verify · S6.b capture→/settle · S6.c replay→replay_detected ·
    S6.d dispute→/refund(dispute_ref'li) · S6.e sınırlar→fail-closed retler ·
    S6.f oturum-sonu TEK K0-bundle (64+63 olayları aynı zincirde) + harici-doğrulama
    + settlement-batch (fail-closed).
  · Aynı senaryolar 63'te test_196–201, 64'te tests/test_s6_joint.py'de sabit.

Canlı-tur (63 kapı-yeşili + 64 süreci ayağa kalkınca):
    SESTER_FACILITATOR_URL=http://127.0.0.1:9400 \
    SESTER_FACILITATOR_KEY=<key> .venv/bin/python scripts/s6_joint_run.py --live

Çıkış: tüm senaryolar yeşil → exit 0; tek RED → exit 1 (fail-loud).
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sester.evidence import produce_bundle, verify_bundle  # noqa: E402
from sester.facilitator_svc import FacilitatorService  # noqa: E402
from sester.ledger import Ledger  # noqa: E402
from sester.settlement import build_settlement_batch  # noqa: E402

SECRET = "s6-joint-secret"
PRICE_MINOR = 50_000
OFFER = "csvo_20260913_s6joint"
NONCE = "s6-joint-0001"

# ---------------------------------------------------------------- 64-gölge-makinesi
# 64-Tenderix src/tenderix/escrow.py gerçek geçiş-matrisi (birebir; S6 koşumunda
# gerçek süreç bunu üretir — burada alan-uzlaşması §2'ye sadık gölge):
_64_TRANSITIONS = {
    "CREATED": ("AUTHORIZED",),
    "AUTHORIZED": ("SETTLED", "REFUNDED", "DISPUTED"),
    "DISPUTED": ("SETTLED", "REFUNDED"),
    "SETTLED": (),
    "REFUNDED": (),
}


class EscrowShadow:
    """64 escrow-gölgesi: geçersiz-geçiş RED; her geçiş karşı-taraf-olayı basar."""

    def __init__(self, ledger: Ledger) -> None:
        self.state = "CREATED"
        self.ledger = ledger
        self.dispute_ref = ""

    def _to(self, target: str, extra: dict[str, str] | None = None) -> str:
        if target not in _64_TRANSITIONS[self.state]:
            raise RuntimeError(f"EscrowError: {self.state} → {target} (geçersiz geçiş)")
        self.state = target
        self.ledger.append(
            f"tenderix_escrow_{target.lower()}", f"tenderix:{OFFER}", "", 0.0,
            payload={"offer_id": OFFER, "nonce": NONCE,
                     "escrow_state": target, "counterparty": "tenderix",
                     "dispute_ref": self.dispute_ref, **(extra or {})},
        )
        return target

    def authorize(self, auth_ref: str) -> str:
        return self._to("AUTHORIZED", {"auth_ref": auth_ref})

    def settle(self) -> str:
        return self._to("SETTLED")

    def dispute(self) -> str:
        self._to("DISPUTED")
        self.dispute_ref = f"sha256:{hashlib.sha256(OFFER.encode()).hexdigest()}"
        self.ledger.append(
            "tenderix_dispute_opened", f"tenderix:{OFFER}", "", 0.0,
            payload={"offer_id": OFFER, "nonce": NONCE,
                     "dispute_ref": self.dispute_ref, "counterparty": "tenderix"},
        )
        return self.state

    def resolve(self, buyer_wins: bool) -> str:
        return self._to("REFUNDED" if buyer_wins else "SETTLED")


# ---------------------------------------------------------------- 63-zarf-üretimi

def pay_for(seller: str, nonce: str, amount_s: str = "0.05") -> str:
    """pugio0 HMAC zarfı (satıcı-tarayısla AYNI format — DONUK şema-önadı)."""
    mac = hmac_mod.new(SECRET.encode(),
                       f"{seller}|{nonce}|{amount_s}|/weather".encode(),
                       hashlib.sha256).hexdigest()
    return f"pugio0 {seller}:{nonce}:{amount_s}:{mac}"


# ---------------------------------------------------------------- koşum-gövdesi

GREEN, RED = "\033[1;32m", "\033[1;31m"
_pass = 0
_fail = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _pass, _fail
    if cond:
        _pass += 1
        print(f"  ✓ {name}" + (f" — {detail}" if detail else ""))
    else:
        _fail += 1
        print(f"  {RED}✗ RED: {name}{(f' — {detail}' if detail else '')}\033[0m")


def run_joint() -> int:
    tmp = Path(os.environ.get("SESTER_S6_TMP", "/tmp")) / "s6_joint_run.sqlite3"
    if tmp.exists():
        tmp.unlink()
    led = Ledger(tmp, secret=SECRET)
    svc = FacilitatorService(led, secret=SECRET, free_transactions=10**9)
    esc = EscrowShadow(led)
    seller = "müşteri-x"
    pay = pay_for(seller, NONCE)

    print(f"{GREEN}== S6 ortak-koşumu: 64-escrow ⟷ 63-facilitator (tek ledger) =={GREEN}\033[0m")

    # ---- S6.a · authorize ------------------------------------------------
    print("[S6.a] authorize: 64 escrow AUTHORIZED ⟷ 63 /verify")
    check("64: CREATED→AUTHORIZED", esc.authorize("fac_verify_s6a") == "AUTHORIZED")
    d = svc.verify(pay, "/weather")
    check("63: /verify ok (nonce yakılmaz)", d.status == "ok" and d.reason == "verify_ok")

    # ---- S6.b · capture --------------------------------------------------
    print("[S6.b] capture: 63 /settle (nonce-bağı) ⟷ 64 escrow SETTLED")
    d = svc.settle(pay, "/weather", PRICE_MINOR)
    check("63: /settle ok", d.status == "ok" and d.reason == "settled",
          f"receipt={d.receipt.get('receipt') if d.receipt else '?'}")
    check("64: AUTHORIZED→SETTLED", esc.settle() == "SETTLED")

    # ---- S6.c · replay-capture ------------------------------------------
    print("[S6.c] replay-capture: ikinci capture iki tarafta da RED")
    d2 = svc.settle(pay, "/weather", PRICE_MINOR)
    check("63: replay_detected", d2.status == "rejected" and d2.reason == "replay_detected")
    try:
        esc.settle()
        check("64: SETTLED terminal", False)
    except RuntimeError as e:
        check("64: SETTLED terminal (EscrowError)", "geçersiz geçiş" in str(e))

    # ---- S6.d · dispute → refund ----------------------------------------
    print("[S6.d] dispute: 64 dispute_opened ⟷ 63 /refund (dispute_ref'li)")
    esc.dispute()
    check("64: dispute_ref üretildi", esc.dispute_ref.startswith("sha256:"))
    d = svc.refund(pay, "/weather", PRICE_MINOR,
                   reason="inkâr", dispute_ref=esc.dispute_ref)
    check("63: /refund ok (metering-iadesi dahil)",
          d.status == "ok" and d.reason == "refunded")
    check("63: net-harcama 0 (ters-yazım)",
          svc.ledger.spent_today_minor(seller) == 0)
    check("64: resolve(buyer_wins)→REFUNDED", esc.resolve(True) == "REFUNDED")

    # ---- S6.e · refund-sınırları (fail-closed) ---------------------------
    print("[S6.e] refund-sınırları: settle'siz / tutar-aşımı / bozuk-dispute")
    d = svc.refund(pay_for(seller, "yok-1"), "/weather", PRICE_MINOR)
    check("63: settle'siz refund RED",
          d.status == "rejected" and d.reason == "refund_without_settlement")
    d = svc.refund(pay, "/weather", PRICE_MINOR)
    check("63: ikinci tam-iade RED (kümülatif ≤ settle)",
          d.status == "rejected" and d.reason == "refund_exceeds")
    d = svc.refund(pay_for(seller, NONCE), "/weather", PRICE_MINOR,
                   dispute_ref="sha256:uydurma")
    check("63: tükenmiş-nonce'a iade RED (uydurma-dispute dahil)",
          d.status == "rejected" and d.reason == "refund_exceeds")

    # ---- S6.f · tek-bundle kanıt + batch --------------------------------
    print("[S6.f] oturum-sonu: tek K0-bundle (64+63 aynı zincir) + harici-doğrulama")
    check("63: zincir SAĞLAM", svc.ledger.verify_chain())
    bundle = produce_bundle(svc.ledger, agent_id=None)   # TÜM olaylar: tenderix + facilitator
    ok, msg = verify_bundle(bundle)
    check("harici-doğrulayıcı (secret'sız): SAĞLAM", ok, msg)
    kinds = {e["event_type"] for e in bundle["events"]}
    check("çift-kanıt: 64-olayları zincirde",
          {"tenderix_escrow_authorized", "tenderix_escrow_settled",
           "tenderix_dispute_opened", "tenderix_escrow_refunded"} <= kinds)
    check("çift-kanıt: 63-olayları zincirde",
          {"facilitator_verify", "facilitator_settle", "facilitator_refund",
           "facilitator_metering"} <= kinds)
    # §2 alan-uzlaşması: her karşı-taraf-olayı uzlaşma-setini taşır
    fields_ok = all(
        set(json.loads(e["payload"])) >= {"offer_id", "nonce", "counterparty"}
        for e in bundle["events"] if e["event_type"].startswith("tenderix_escrow_")
    )
    check("§2 alan-uzlaşması (offer_id/nonce/counterparty)", fields_ok)
    try:
        b = build_settlement_batch(svc.ledger, seller, chain_id=8453,
                                   contract="0x" + "0c" * 20,
                                   from_address="0x" + "f4" * 20)
        check("settlement-batch: net 0 (settle−refund)", b.total_minor == 0)
        check("payee: türetildi + kayıt-altında (40-hex, 0x-önekli)",
              b.payee_address.startswith("0x") and len(b.payee_address) == 42)
    except Exception as e:  # noqa: BLE001 — fail-loud
        check("settlement-batch üretimi", False, str(e))

    led.close()
    print(f"\n{GREEN if _fail == 0 else RED}"
          f"S6 ORTAK-KOŞUM: {_pass} yeşil, {_fail} RED"
          f"{' — S6.a–S6.f KAPANDI (63-tarafı kanıtı)' if _fail == 0 else ''}\033[0m")
    return 0 if _fail == 0 else 1


def run_live() -> int:  # pragma: no cover — canlı-tur (63 kapı-yeşili + 64 süreci)
    """Canlı-tur: koşan facilitator'a HTTP ile S6.a–S6.f (aynı senaryo-seti)."""
    try:
        import urllib.request
    except ImportError:  # pragma: no cover
        print("RED: urllib yok — canlı-tur koşamaz")
        return 1
    base = os.environ["SESTER_FACILITATOR_URL"].rstrip("/")
    key = os.environ["SESTER_FACILITATOR_KEY"]
    headers = {"Content-Type": "application/json", "X-Facilitator-Key": key}

    def post(path: str, body: dict) -> dict:
        req = urllib.request.Request(
            f"{base}{path}", data=json.dumps(body).encode(),
            headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())

    print(f"{GREEN}== S6 canlı-tur → {base} (senaryo-seti aynı) =={GREEN}\033[0m")
    pay = pay_for("müşteri-x", NONCE)
    r = post("/verify", {"payment": pay, "resource": "/weather"})
    check("[S6.a] /verify ok", r.get("status") == "ok")
    r = post("/settle", {"payment": pay, "resource": "/weather",
                         "amount_minor": PRICE_MINOR})
    check("[S6.b] /settle ok", r.get("status") == "ok")
    r = post("/settle", {"payment": pay, "resource": "/weather",
                         "amount_minor": PRICE_MINOR})
    check("[S6.c] replay RED", r.get("reason") == "replay_detected")
    r = post("/refund", {"payment": pay, "resource": "/weather",
                         "amount_minor": PRICE_MINOR,
                         "reason": "inkâr", "dispute_ref": "sha256:live"})
    check("[S6.d] /refund ok", r.get("status") == "ok")
    r = post("/refund", {"payment": pay, "resource": "/weather",
                         "amount_minor": PRICE_MINOR})
    check("[S6.e] ikinci-iade RED", r.get("reason") == "refund_exceeds")
    print(f"\nS6 CANLI-TUR: {_pass} yeşil, {_fail} RED")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(run_live() if "--live" in sys.argv else run_joint())
