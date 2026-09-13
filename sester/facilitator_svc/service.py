"""FacilitatorService — S5 çekirdeği (framework-siz; testlerde birebir kullanılır).

Sorumluluklar:
  verify(zarf, resource) → status ok|rejected|unknown  (kanıt-olayı yazılır)
  settle(zarf)           → settlement ya da idempotent-red (kanıt-olayı yazılır)
  seller_metering        — facilitator'ın KENDİ faturalaması: satıcı-başına
                           işlem-sayacı + free-band (ilk 10k bedava) + %1+$0.005
  build_batch            — kapatılan satıcı-segmentini on-chain-batch'e indirger
                           (sester/settlement.py; chain/contract sabitli)

Doğrulama-motoru kopya-DEĞİLDIR: şema-çözümleme/HMAC/replay/kota yolu,
SesterMeter ile AYNI çekirdeği kullanır (sınıf-kompozisyonu). Böylece
facilitator'ın "doğru" tanımı, satıcı-tarafı middleware'ınkiyle tek-kaynaklıdır.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..ledger import MINOR, Ledger
from ..middleware import PaymentErr, SesterMeter

FREE_TRANSACTIONS = 10_000          # MONETIZATION lane-1: ayda ilk 10k bedava
PERCENT_FEE = 0.01                  # %1 işlem-ücreti
FLAT_FEE_MINOR = 5_000              # $0.005 (6-dec minor)


class FacilitatorServiceError(Exception):
    """Servis-kuralı ihlali (fail-closed ret-kararıyla döndürülür)."""


@dataclass(frozen=True)
class ServiceDecision:
    status: str                 # ok | rejected | unknown
    reason: str = ""
    receipt: dict[str, Any] | None = None


class _VerifyLedger:
    """SesterMeter'ın nonce/replay-çekirdeğini yeniden-kullanan zarf.

    SesterMeter, parser'ları `self.ledger.claim_nonce` + `self.ledger.append`
    üzerinden çağırır; facilitator aynı ledger'a YAZAR ama handler-akışı
    (charge_receipt/kota) SATICIDA kalır — facilitator yalnız kanıt tutar.
    """

    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger

    def claim_nonce(self, agent: str, nonce: str) -> bool:
        return self.ledger.claim_nonce(agent, nonce)

    def append(self, *a, **kw):  # SesterMeter iç-kullanımı için uyum
        return self.ledger.append(*a, **kw)

    def spent_today(self, agent: str) -> float:  # pragma: no cover - yedek-yol
        return 0.0

    def spent_today_minor(self, agent: str) -> int:  # pragma: no cover - yedek-yol
        return 0


class FacilitatorService:
    """x402 verify/settle + satıcı-metering + batch — tek-süreç MVP."""

    def __init__(self, ledger: Ledger, *, secret: str = "facilitator-secret",
                 free_transactions: int = FREE_TRANSACTIONS,
                 percent_fee: float = PERCENT_FEE,
                 flat_fee_minor: int = FLAT_FEE_MINOR,
                 chain_id: int = 8453, contract: str = "0x" + "0c" * 20,
                 from_address: str = "0x" + "f4" * 20) -> None:
        self.ledger = ledger
        self.secret = secret.encode()
        self.free_transactions = int(free_transactions)
        self.percent_fee = float(percent_fee)
        self.flat_fee_minor = int(flat_fee_minor)
        self.chain_id = int(chain_id)
        self.contract = contract.lower()
        self.from_address = from_address.lower()
        # SesterMeter'ın parser-kompozisyonu (handler/ASGI KULLANILMAZ):
        self._meter = SesterMeter(
            None, _VerifyLedger(ledger), secret=secret,
            price=0.0, daily_quota=10**9,   # kota-kararı satıcıda; facilitator kota-TUTMAZ
            pay_to="facilitator",
        )

    # ------------------------------------------------- kanıt-yardımcıları

    def _proof(self, kind: str, subject: str, resource: str, payload: dict) -> dict:
        return self.ledger.append(f"facilitator_{kind}", subject, resource,
                                  payload=payload)

    # ------------------------------------------------- verify / settle

    def _parse(self, payment: str, resource: str) -> tuple[str | None, dict[str, Any]]:
        """Zarfı satıcı-tarafıyla AYNI çekirdekle çözümle (kaynak-bağlı).
        Dönüş: (satıcı, parsed) — çözülemezse (None, {}). Bilinmeyen-önek ile
        bozuk-zarf ayrımı için önek çağıranın denetlemesi gerekir."""
        prefix = payment.strip().split(" ", 1)[0]
        parser = self._meter._schemes.get(prefix)
        if parser is None:
            return None, {}
        try:
            parsed = parser(payment, resource)
        except PaymentErr:
            return None, {}
        return str(parsed.get("agent")), parsed

    def verify(self, payment: str, resource: str) -> ServiceDecision:
        """Zarfı doğrula (şema→HMAC/EVM; replay-settle'da — verify nonce yakmaz)."""
        prefix = payment.strip().split(" ", 1)[0]
        if prefix not in self._meter._schemes:
            self._proof("verify", "bilinmeyen", resource,
                        {"decision": "deny", "rule_id": "unknown_scheme"})
            return ServiceDecision("rejected", "unknown_scheme")
        seller, parsed = self._parse(payment, resource)
        if seller is None:
            self._proof("verify", "bilinmeyen", resource,
                        {"decision": "deny", "rule_id": "malformed-payment"})
            return ServiceDecision("rejected", "malformed-payment")
        self._proof("verify", seller, resource,
                    {"decision": "allow", "rule_id": "verify_ok"})
        return ServiceDecision("ok", "verify_ok")

    def settle(self, payment: str, resource: str, amount_minor: int) -> ServiceDecision:
        """Onaylı zarfı kesinleştir: nonce bir-kez; kanıt + metering-sayacı."""
        prefix = payment.strip().split(" ", 1)[0]
        if prefix not in self._meter._schemes:
            self._proof("settle", "bilinmeyen", resource,
                        {"decision": "deny", "rule_id": "unknown_scheme"})
            return ServiceDecision("rejected", "unknown_scheme")
        seller, parsed = self._parse(payment, resource)
        if seller is None:
            self._proof("settle", seller or "bilinmeyen", resource,
                        {"decision": "deny", "rule_id": "malformed-payment"})
            return ServiceDecision("rejected", "malformed-payment")
        nonce = str(parsed.get("nonce"))
        if not nonce:  # pragma: no cover - parser'lar nonce'suz dönmez
            return ServiceDecision("rejected", "nonce-missing")
        if not self.ledger.claim_nonce(f"svc:{seller}", nonce):
            self._proof("settle", seller, resource,
                        {"decision": "deny", "rule_id": "replay"})
            return ServiceDecision("rejected", "replay_detected")
        # ekonomik olay: batch total'ı bundan iner (middleware charge_receipt şeması)
        amount = int(amount_minor) / MINOR
        self.ledger.append("charge_receipt", seller, resource, amount,
                           amount_minor=int(amount_minor),
                           payload={"nonce": nonce, "scheme": "facilitator"})
        rec = self._proof("settle", seller, resource,
                          {"decision": "allow", "nonce": nonce,
                           "amount_minor": int(amount_minor)})
        metering = self.record_transaction(seller, int(amount_minor))
        return ServiceDecision("ok", "settled",
                               {"receipt": rec["hash"][:16], **metering})

    # ------------------------------------------------- satıcı-metering (lane-1)

    def record_transaction(self, seller: str, amount_minor: int) -> dict[str, Any]:
        """%1 + $0.005; ilk `free_transactions` işlem bedava — kanıt-olaylı sayaç.
        n = bu settle'dan ÖNCEKİ işlem-sayısı (sınır n < free ile denetlenir)."""
        n = self._tx_count(seller)
        free_band = n < self.free_transactions
        charged_minor = 0 if free_band else (
            int(round(amount_minor * self.percent_fee)) + self.flat_fee_minor)
        self._proof("metering", seller, "",
                    {"tx_index": n, "amount_minor": int(amount_minor),
                     "charged_minor": charged_minor,
                     "free_band": free_band})
        return {"tx_index": n, "charged_minor": charged_minor,
                "free_band": free_band}

    def _tx_count(self, seller: str) -> int:
        """İşlem-sayacı — yalnız gerçek settle'lar; iade-kredisi satırları
        (payload.refund_of) sayılmaz (yoksa free-band erken kapanır)."""
        n = 0
        for r in self.ledger.export_events(agent_id=seller):
            if r["event_type"] != "facilitator_metering":
                continue
            try:
                p = json.loads(r.get("payload") or "{}")
            except json.JSONDecodeError:
                continue
            if "refund_of" not in p:
                n += 1
        return n

    def seller_invoice(self, seller: str) -> dict[str, Any]:
        """Satıcı-başına fatura-öngörüsü (panel/healthz doldurur)."""
        tx = self._tx_count(seller)
        charged = 0
        for r in self.ledger.export_events(agent_id=seller):
            if r["event_type"] != "facilitator_metering":
                continue
            try:
                p = json.loads(r.get("payload") or "{}")
            except json.JSONDecodeError:
                continue
            charged += int(p.get("charged_minor", 0))
        return {"seller": seller, "transactions": tx,
                "charged_minor": charged,
                "charged": charged / MINOR,
                "free_band": tx <= self.free_transactions}

    # ------------------------------------------------- refund (S6 sözleşmesi)

    def refund(self, payment: str, resource: str, amount_minor: int, *,
               reason: str = "", dispute_ref: str = "") -> ServiceDecision:
        """S6 §2: yalnız settle-edilmiş (seller, nonce) için ters-yazım.
        nonce-bağı KIRILMAZ (claim zaten settle'da); dispute_ref kanıta düşer;
        metering negatif-düzeltme olayıyla iade edilir (denetlenebilir)."""
        prefix = payment.strip().split(" ", 1)[0]
        if prefix not in self._meter._schemes:
            self._proof("refund", "bilinmeyen", resource,
                        {"decision": "deny", "rule_id": "unknown_scheme"})
            return ServiceDecision("rejected", "unknown_scheme")
        seller, parsed = self._parse(payment, resource)
        if seller is None:
            self._proof("refund", seller or "bilinmeyen", resource,
                        {"decision": "deny", "rule_id": "malformed-payment"})
            return ServiceDecision("rejected", "malformed-payment")
        nonce = str(parsed.get("nonce"))
        settled_minor = self._settled_minor_for(seller, nonce)
        if settled_minor is None:
            self._proof("refund", seller, resource,
                        {"decision": "deny", "rule_id": "refund_without_settlement"})
            return ServiceDecision("rejected", "refund_without_settlement")
        # S6 kuralı: nonce başına TOPLAM iade ≤ settle (kısmi-iadeler birikir)
        already = self._refunded_minor_for(seller, nonce)
        if int(amount_minor) > settled_minor - already:
            self._proof("refund", seller, resource,
                        {"decision": "deny", "rule_id": "refund_exceeds",
                         "settled_minor": settled_minor, "already_refunded": already})
            return ServiceDecision("rejected", "refund_exceeds")
        # ters-yazım: ledger'da 'refund' (spent_today/sign ın ters-yön kuralıyla uyumlu)
        amount = int(amount_minor) / MINOR
        self.ledger.append("refund", seller, resource, amount,
                           amount_minor=int(amount_minor),
                           payload={"nonce": nonce, "reason": reason,
                                    "dispute_ref": dispute_ref})
        self._proof("refund", seller, resource,
                    {"decision": "allow", "nonce": nonce,
                     "amount_minor": int(amount_minor),
                     "dispute_ref": dispute_ref})
        self._proof("metering", seller, "",
                    {"tx_index": self._tx_count(seller),
                     "amount_minor": -int(amount_minor),
                     "charged_minor": 0, "free_band": True,
                     "refund_of": nonce})
        return ServiceDecision("ok", "refunded",
                               {"refund_minor": int(amount_minor),
                                "dispute_ref": dispute_ref})

    def _settled_minor_for(self, seller: str, nonce: str) -> int | None:
        """Settle-edilen tutar (facilitator_settle olayından); settle-yoksa None."""
        for r in self.ledger.export_events(agent_id=seller):
            if r["event_type"] != "facilitator_settle":
                continue
            try:
                p = json.loads(r.get("payload") or "{}")
            except json.JSONDecodeError:
                continue
            if p.get("nonce") == nonce and p.get("decision") == "allow":
                return int(p.get("amount_minor", 0))
        return None

    def _refunded_minor_for(self, seller: str, nonce: str) -> int:
        """Bu nonce için yapılmış toplam iade (refund olaylarından)."""
        total = 0
        for r in self.ledger.export_events(agent_id=seller):
            if r["event_type"] != "refund":
                continue
            try:
                p = json.loads(r.get("payload") or "{}")
            except json.JSONDecodeError:
                continue
            if p.get("nonce") == nonce:
                total += int(r.get("amount_minor") or 0)
        return total

    # ------------------------------------------------- batch (settlement.py)

    def build_batch(self, seller: str) -> dict[str, Any]:
        """Kapatılan satıcı-segmentini on-chain-batch'e indirger (non-custodial)."""
        from ..settlement import SettlementError, build_settlement_batch

        batch = build_settlement_batch(
            self.ledger, seller, chain_id=self.chain_id,
            contract=self.contract, from_address=self.from_address,
        )
        self._proof("batch", seller, "",
                    {"sha_digest": batch.sha_digest,
                     "merkle_root": batch.merkle_root,
                     "event_count": batch.event_count,
                     "total_minor": batch.total_minor})
        return {
            "agent": batch.agent, "chain_id": batch.chain_id,
            "contract": batch.contract, "total_minor": batch.total_minor,
            "merkle_root": batch.merkle_root, "calldata": batch.calldata,
            "sha_digest": batch.sha_digest,
        }
