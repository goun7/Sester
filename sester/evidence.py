"""SESTER evidence — 81-kanıt-köprüsü v0: dışa-doğrulanabilir kanıt-bundle'ı.

63↔81 kontratı (execution plan §7 S4): SESTER olayları, agent-filtreli kanıt-segmenti
olarak export edilir. İç zincir HMAC-mühürlü (secret ister); bundle buna ek
**kamuya proof-zinciri** taşır: her olayın proof'u yalnız sha256(canonical) —
secret'sız, kütüphanesiz (pür sha256 + JSON) doğrulanır:

  1) her olay: sha256(canonical(prev_proof dahil)) == proof
  2) bağ: events[i].prev_proof == events[i-1].proof (ilk: GENESIS)
  3) kök: merkle(proof-listesi) == bundle.merkle_root

Merkle: çiftler sha256(a+b); tek-son eleman kendisiyle eşlenir; boş → GENESIS.
Alıcı: 81-MERGEN denetçisi / müşteri-denetimi / vergi-kanalı kaydı (₿-tahsilat §4
şerhli-fatura kanıt-eşi) — "kanıt-okuma-oranı" metriğinin (execution plan §4) altyapısı.

Not: `pugio_bundle_version` DONUK kablo-alanıdır (identity-migration record) — alıcılar
bu alan-adını bilir; v2'ye kadar değişmez.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

GENESIS = "0" * 64
BUNDLE_VERSION = 1


def _canonical(ev: dict[str, Any], prev_proof: str) -> str:
    return "|".join([
        f"{float(ev['ts']):.6f}", ev["event_type"], ev["agent_id"], ev["host"],
        f"{float(ev['amount']):.6f}", ev["payload"], prev_proof,
    ])


def proof_hash(ev: dict[str, Any], prev_proof: str) -> str:
    return hashlib.sha256(_canonical(ev, prev_proof).encode()).hexdigest()


def _merkle(leaves: list[str]) -> str:
    if not leaves:
        return GENESIS
    layer = list(leaves)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [hashlib.sha256((a + b).encode()).hexdigest()
                 for a, b in zip(layer[::2], layer[1::2])]
    return layer[0]


def produce_bundle(ledger: Any, agent_id: str | None = None) -> dict[str, Any]:
    """Ledger'dan dışa-doğrulanabilir kanıt-bundle'ı üret."""
    events = ledger.export_events(agent_id)
    out: list[dict[str, Any]] = []
    prev = GENESIS
    for ev in events:
        p = proof_hash(ev, prev)
        out.append({
            "seq": ev["seq"], "ts": ev["ts"], "event_type": ev["event_type"],
            "agent_id": ev["agent_id"], "host": ev["host"], "amount": ev["amount"],
            "payload": ev["payload"], "prev_proof": prev, "proof": p,
        })
        prev = p
    return {
        "pugio_bundle_version": BUNDLE_VERSION,   # DONUK alan — alıcı-uyumu
        "generated": time.time(),
        "agent": agent_id,
        "head": prev,
        "merkle_root": _merkle([e["proof"] for e in out]),
        "event_count": len(out),
        "events": out,
    }


def verify_bundle(bundle: dict[str, Any]) -> tuple[bool, str]:
    """Alıcı-tarafı: sester kütüphanesi ve secret OLMADAN doğrula.
    Dönüş: (ok, mesaj)."""
    try:
        if int(bundle.get("pugio_bundle_version", 0)) != BUNDLE_VERSION:
            return False, "bundle-sürümü bilinmiyor"
        events = bundle.get("events")
        if not isinstance(events, list):
            return False, "events liste değil"
        prev = GENESIS
        proofs: list[str] = []
        expected_seq = None
        for ev in events:
            if expected_seq is not None and ev["seq"] != expected_seq:
                return False, f"seq-atlaması: {expected_seq} beklenirken {ev['seq']}"
            expected_seq = ev["seq"] + 1
            if ev["prev_proof"] != prev:
                return False, f"zincir-kopması @seq={ev['seq']}"
            expect = proof_hash(ev, prev)
            if expect != ev["proof"]:
                return False, f"proof-uyuşmazlığı @seq={ev['seq']} (veri-değişikliği)"
            proofs.append(ev["proof"])
            prev = ev["proof"]
        if bundle.get("head") != prev:
            return False, "head uyuşmuyor"
        if bundle.get("merkle_root") != _merkle(proofs):
            return False, "merkle-kökü uyuşmuyor"
        return True, f"SAĞLAM: {len(events)} olay, head={prev[:12]}…"
    except (KeyError, TypeError, ValueError) as e:
        return False, f"bundle-bozuk: {e}"


def bundle_json(bundle: dict[str, Any]) -> str:
    """Dosyaya/iletime hazır sabit-sıralı JSON."""
    return json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
