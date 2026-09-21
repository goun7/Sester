"""SESTER — Ajan ticaret yığını, B-katmanı (AgentMeter) v0.

Katmanlar:
  policy     — Policy-DSL-v0 v0 alt-kümesi (fail-closed cüzdan politikası)
  ledger     — hash-chain'li SQLite usage ledger (tamga-uyumlu olay şeması)
  middleware — x402 el sıkışması + sayaç + kota (ASGI/Starlette)
  panel      — basit HTML tablo (kim, kaç çağrı, ne kadar)
  webhooks   — HMAC-imzalı kanıt-teslimi (alıcı-tarafı-doğrulamalı)
  escalation — insan-onay bileti (then: escalate → 402)
  settlement — on-chain batch calldata (non-custodial, pure-stdlib keccak)

Kimlik-tarihi: Pugio → Sikke → Sester (bkz. identity-migration record). Donuk
kablo-alanları (pugio0, pugio_bundle_version, pugio_evidence_bundle,
source:sikke) v2'ye kadar alıcı-uyumu için korunur.

Public-yüzey (v0.7.2): metering-paketi olarak-tek-import. Aşağıdaki-isimler
bait — yeni-eklenen-her-yüzey `__all__`-içinde-olmak-zorunda (test_69-şartı).
Kanal-kararları değiştirebilir-ama-mevcut-isimler-kopmaz (donuk-yüzey).
"""

from .escalation import EscalationQueue
from .ledger import Ledger
from .middleware import PaymentErr, SesterMeter
from .policy import Decision, DenyAll, Policy, PolicyCorruptError
from .webhooks import (build_webhook_payload, deliver_webhook, sign_webhook,
                       verify_webhook)

__all__ = [
    # metering-çekirdeği
    "SesterMeter",
    "PaymentErr",
    # politika-katmanı
    "Policy",
    "DenyAll",
    "Decision",
    "PolicyCorruptError",
    # kanıt-zinciri
    "Ledger",
    # insan-onay
    "EscalationQueue",
    # kanıt-teslimi
    "sign_webhook",
    "verify_webhook",
    "build_webhook_payload",
    "deliver_webhook",
]

__version__ = "0.7.3"
