"""PUGIO watch-feed — K3 üreticisi (K0_SHARED_ENVELOPE_SPEC §6).

Bir kanıt-bundle'ındaki HER denetlenen karar (permission_decision) tek bir
`watch_event` satırına düşer; satırlar şu zincirle bağlıdır:

    entry_sha = SHA256(prev_entry_sha|seq|ts|agent|host|rule_id|decision)

`prev_entry_sha` GENESIS ("0"*64) ile başlar; akış `watch_manifest` ile açılır
(watcher kimliği + referans-bundle işaretçileri) ve son `entry_sha`'yı taşıyan
`watch_close` ile kapanır. Alıcı (Veridict tarafı) zinciri yeniden-hash'ler —
pugio'suz, pür sha256 (fail-loud: her uyuşmazlık explicit RED).

Kurallar (K0 §7): yalnız-kamu alanları · sürümlü (bridge_version) ·
deterministik JSON (sort_keys, compact) · alıcı-bağımsız doğrulama.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

BRIDGE_VERSION = 1
GENESIS = "0" * 64


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _j(obj: dict[str, Any]) -> str:
    """K0 kanonik satır-formatı: sort_keys + compact + UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def entry_sha(prev_entry_sha: str, seq: int, ts: float, agent: str,
              host: str, rule_id: str, decision: str) -> str:
    """K0 §6 bağ-formülü — alıcı tarafı birebir aynısını hesaplar."""
    return _sha(f"{prev_entry_sha}|{int(seq)}|{ts:.6f}|{agent}|{host}|{rule_id}|{decision}")


def _decisions(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Bundle'daki permission_decision olaylarını (seq sırasıyla) normalize et."""
    out: list[dict[str, Any]] = []
    for e in bundle.get("events", []):
        if e.get("event_type") != "permission_decision":
            continue
        try:
            p = json.loads(e.get("payload") or "{}")
        except (json.JSONDecodeError, TypeError):
            p = {}
        out.append({
            "ts": float(e.get("ts", 0.0)),
            "agent": str(e.get("agent_id", "")),
            "host": str(e.get("host", "")),
            "rule_id": str(p.get("rule_id", "unknown")),
            "decision": str(p.get("decision", "unknown")),
        })
    return out


def produce_watch_feed(bundle: dict[str, Any], *, watcher_id: str) -> list[dict[str, Any]]:
    """Kanıt-bundle → [manifest, watch_event*, close] satır-listesi (JSONL'e dökülmeye hazır).

    Çıktı deterministiktir: duvar-saati/`generated` bilinçli taşınmaz;
    ts'ler kaynak-olaylardan gelir.
    """
    decisions = _decisions(bundle)
    lines: list[dict[str, Any]] = [{
        "type": "watch_manifest",
        "bridge_version": BRIDGE_VERSION,
        "source": "pugio",
        "watcher_id": watcher_id,
        "bundle_head": bundle.get("head"),
        "bundle_merkle_root": bundle.get("merkle_root"),
        "bundle_event_count": int(bundle.get("event_count", 0)),
    }]
    prev = GENESIS
    for i, d in enumerate(decisions, start=1):
        sha = entry_sha(prev, i, d["ts"], d["agent"], d["host"], d["rule_id"], d["decision"])
        lines.append({
            "type": "watch_event",
            "bridge_version": BRIDGE_VERSION,
            "seq": i,
            "ts": f"{d['ts']:.6f}",
            "agent": d["agent"],
            "host": d["host"],
            "rule_id": d["rule_id"],
            "decision": d["decision"],
            "prev_entry_sha": prev,
            "entry_sha": sha,
        })
        prev = sha
    lines.append({
        "type": "watch_close",
        "bridge_version": BRIDGE_VERSION,
        "entries": len(decisions),
        "watch_head": prev,
    })
    return lines


def watch_feed_jsonl(bundle: dict[str, Any], *, watcher_id: str) -> str:
    return "\n".join(_j(line) for line in produce_watch_feed(bundle, watcher_id=watcher_id))


def verify_watch_feed(lines: list[dict[str, Any]]) -> tuple[bool, str]:
    """Alıcı-tarafı çekirdeği (pür sha256): zincir-yeniden-hash + seq-sürekliliği + kapanış.

    Dönüş: (ok, mesaj). Her uyuşmazlık explicit RED (fail-loud) — sessiz geçiş yok.
    """
    if not lines:
        return False, "FAIL: akış boş"
    m = lines[0]
    if m.get("type") != "watch_manifest":
        return False, f"FAIL: ilk satır manifest değil ({m.get('type')})"
    if m.get("bridge_version") != BRIDGE_VERSION:
        return False, f"FAIL: bilinmeyen bridge_version ({m.get('bridge_version')})"

    prev = GENESIS
    seen = 0
    last_sha = GENESIS
    for line in lines[1:]:
        t = line.get("type")
        if t == "watch_close":
            if line.get("entries") != seen:
                return False, f"FAIL: close.entries={line.get('entries')} ≠ gerçek {seen}"
            if line.get("watch_head") != last_sha:
                return False, "FAIL: watch_head son entry_sha ile uyuşmuyor"
            return True, f"SAĞLAM: {seen} karar · watch_head={last_sha[:16]}…"
        if t != "watch_event":
            return False, f"FAIL: beklenmeyen satır-tipi ({t})"
        if line.get("bridge_version") != BRIDGE_VERSION:
            return False, f"FAIL: bilinmeyen bridge_version ({line.get('bridge_version')})"
        seen += 1
        if int(line.get("seq", -1)) != seen:
            return False, f"FAIL: seq süreksizliği @#{seen}"
        if line.get("prev_entry_sha") != prev:
            return False, f"FAIL: prev_entry_sha kopuk @seq={seen}"
        calc = entry_sha(prev, line["seq"], float(line["ts"]),
                         line.get("agent", ""), line.get("host", ""),
                         line.get("rule_id", ""), line.get("decision", ""))
        if calc != line.get("entry_sha"):
            return False, f"FAIL: entry_sha uyuşmazlığı @seq={seen} (veri-değişikliği)"
        prev = calc
        last_sha = calc
    return False, "FAIL: watch_close yok"
