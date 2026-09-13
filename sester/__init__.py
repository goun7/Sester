"""SESTER — Ajan ticaret yığını, B-katmanı (AgentMeter) v0.

Katmanlar:
  policy     — KURAL_DSL_V0 v0 alt-kümesi (fail-closed cüzdan politikası)
  ledger     — hash-chain'li SQLite usage ledger (tamga-uyumlu olay şeması)
  middleware — x402 el sıkışması + sayaç + kota (ASGI/Starlette)
  panel      — basit HTML tablo (kim, kaç çağrı, ne kadar)

Kimlik-tarihi: Pugio → Sikke → Sester (bkz. ESKI_KIMLIK.md). Donuk
kablo-alanları (pugio0, pugio_bundle_version, pugio_evidence_bundle,
source:sikke) v2'ye kadar alıcı-uyumu için korunur.
"""

__version__ = "0.5.0"
