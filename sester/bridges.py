"""SESTER bridges — birleşme-değil, köprü kararı (BIRLESTIRME_DEGERLENDIRMESI.md §3).

K1 · Tamga çıpası:  SESTER kanıt-segmentinin chain-head + merkle-kökünü
      Tamga-uyumlu deterministik JSONL zarfı olarak dışa-verir — Tamga-node'u
      bunu kendi ledger'ına alınan-iş kanıtı olarak yazabilir (tip:
      external_anchor; SESTER secret'ı gerekmez, yalnız kamuya proof-alanı).
K2 · Veridict talebi: SESTER politika/sayaç iddialarını Veridict'in
      makine-doğrulanabilir claim-formatına döker — her claim
      `claim_id = sha256(task_id|summary|verifiability)[:16]` kuralına uyar,
      verifiability=reproducible; kanıt, SESTER kanıt-bundle'ının head+merkle'ı.

İki köprü de yalnız-kamu-alanlarla çalışır (non-custodial + secret'sız-
doğrulanabilirlik korunur). Satır-formatları bilinçli-minimal: alıcı tarafı
sester'suz doğrulayabilsin (scripts/dogrula.py disiplini).

Not (ESKI_KIMLIK.md): `source: "sikke"` ve `pugio_evidence_bundle` DONUK
kablo-alanlarıdır — kardeş-repo alıcıları (tamga_pugio_receiver.py vb.)
bu değerleri bilmektedir; v2'ye kadar değişmezler.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

BRIDGE_VERSION = 1


# ---------------------------------------------------------------- K1 · Tamga

def tamga_anchor(bundle: dict[str, Any], *, agent_label: str | None = None) -> dict[str, Any]:
    """Kanıt-bundle'ını Tamga external-anchor zarfına çevir.

    Zarf: tip=external_anchor, kaynak=sikke (DONUK), head + merkle_root +
    event_count; `anchor_id = sha256(head|merkle_root|event_count)[:32]` —
    deterministik, tekrar-üretilebilir; alıcı yalnız sha256 ile bağlar.
    """
    head = str(bundle.get("head", ""))
    merkle = str(bundle.get("merkle_root", ""))
    count = int(bundle.get("event_count", 0))
    if not head or not merkle or count < 0:
        raise ValueError("bundle'da head/merkle_root/event_count eksik")
    anchor_id = hashlib.sha256(f"{head}|{merkle}|{count}".encode()).hexdigest()[:32]
    return {
        "type": "external_anchor",
        "bridge_version": BRIDGE_VERSION,
        "source": "sikke",   # DONUK kablo-alanı (alıcı-uyumu)
        "pugio_bundle_version": bundle.get("pugio_bundle_version"),
        "agent": agent_label or bundle.get("agent"),
        "anchor_id": anchor_id,
        "head": head,
        "merkle_root": merkle,
        "event_count": count,
        "generated": time.time(),
    }


def tamga_anchor_json(bundle: dict[str, Any], **kw) -> str:
    """Deterministik JSONL-satırı (Tamga-node'unun ledger'ına tek-satır yazım).
    `generated` (duvar-saati) bilinçli dışarıda: satır tekrar-üretilebilir olsun."""
    anchor = {k: v for k, v in tamga_anchor(bundle, **kw).items() if k != "generated"}
    return json.dumps(anchor, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def verify_tamga_anchor(anchor: dict[str, Any]) -> tuple[bool, str]:
    """Alıcı-tarafı: anchor_id bağını pür sha256 ile doğrula."""
    try:
        if anchor.get("type") != "external_anchor" or anchor.get("source") != "sikke":
            return False, "zarf-tipi/kaynak uyuşmuyor"
        expect = hashlib.sha256(
            f"{anchor['head']}|{anchor['merkle_root']}|{int(anchor['event_count'])}".encode()
        ).hexdigest()[:32]
        if expect != anchor.get("anchor_id"):
            return False, "anchor_id bağı kopuk (veri-değişikliği)"
        return True, f"çıpa-SAĞLAM: {anchor['anchor_id']}"
    except (KeyError, TypeError, ValueError) as e:
        return False, f"zarf-bozuk: {e}"


# -------------------------------------------------------------- K2 · Veridict

def _claim_id(task_id: str, summary: str) -> str:
    """Veridict kuralı: sha256(task_id|summary|verifiability)[:16]."""
    return hashlib.sha256(f"{task_id}|{summary}|reproducible".encode()).hexdigest()[:16]


def _payload_counts(bundle: dict[str, Any]) -> tuple[int, int, int]:
    """(quota_denies, replay_denies, receipts) — payload JSON'u çözülerek sayılır
    (ledger compact-separator yazar; substring-fragil değil, parse-robust)."""
    quota = replay = receipts = 0
    for e in bundle.get("events", []):
        if e.get("event_type") == "charge_receipt":
            receipts += 1
            continue
        if e.get("event_type") != "permission_decision":
            continue
        try:
            p = json.loads(e.get("payload") or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if p.get("decision") != "deny":
            continue
        if p.get("rule_id") == "quota_exceeded":
            quota += 1
        elif p.get("rule_id") == "replay":
            replay += 1
    return quota, replay, receipts


def veridict_claims(bundle: dict[str, Any], *, task_id: str = "sestering") -> dict[str, Any]:
    """SESTER kanıtını Veridict makine-claim'lerine dök.

    Üç reproducible-claim (kanıt: bundle head+merkle — offline-replay edilebilir):
      · quota-enforced  — günlük-kota aşımı 402 ile engellendi
      · replay-denied   — aynı nonce ikinci kez kabul edilmedi
      · chain-integrity — kanıt-zinciri + merkle-kökü bütünlüğü
    Sayısal kanıtlar permission_decision/charge_receipt olaylarından sayılır.
    """
    events = bundle.get("events", [])
    quota_denies, replay_denies, receipts = _payload_counts(bundle)

    def claim(summary: str, subject: str, claim_value: str) -> dict[str, Any]:
        return {
            "claim_id": _claim_id(task_id, summary),
            "task_id": task_id,
            "summary": summary,
            "verifiability": "reproducible",
            "subject": subject,
            "claim": claim_value,
            "evidence": {
                "kind": "pugio_evidence_bundle",   # DONUK kablo-alanı
                "head": bundle.get("head"),
                "merkle_root": bundle.get("merkle_root"),
                "event_count": bundle.get("event_count"),
            },
        }

    return {
        "bridge_version": BRIDGE_VERSION,
        "source": "sikke",   # DONUK kablo-alanı (alıcı-uyumu)
        "claims": [
            claim(
                f"Günlük-kota politikası uygulandı: {quota_denies} aşım-engeli, "
                f"{receipts} ücretli-işlem kaydı",
                subject="sikke",
                claim_value="quota_enforced",
            ),
            claim(
                f"Replay-koruması canlı: {replay_denies} tekrar-nonce reddi",
                subject="sikke",
                claim_value="replay_denied",
            ),
            claim(
                "Kanıt-zinciri + Merkle-kökü bütünlüğü: harici-sha256 ile "
                "yeniden-hesaplanabilir",
                subject="sikke-ledger",
                claim_value="chain_integrity",
            ),
        ],
    }


def veridict_claims_json(bundle: dict[str, Any], **kw) -> str:
    return json.dumps(veridict_claims(bundle, **kw), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)
