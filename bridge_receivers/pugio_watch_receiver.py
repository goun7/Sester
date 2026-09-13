#!/usr/bin/env python3
"""Veridict-tarafı SESTER watch-feed alıcısı — K3 (K0_SHARED_ENVELOPE_SPEC §6).

KARDEŞ-REPO ARTİFAKTIDIR: SESTER kütüphanesini IMPORT ETMEZ (pür stdlib:
json + hashlib + sys). Veridict deposunun `scripts/` altına kopyalanır;
SESTER'nun `sester.watchfeed.watch_feed_jsonl` çıktısını alır.

Sözleşme (DONUK kablo-alanları — ESKI_KIMLIK.md):
  manifest: type=watch_manifest · source == "sikke" · bridge_version == 1
  entry_sha = SHA256("{prev}|{seq}|{ts:.6f}|{agent}|{host}|{rule_id}|{decision}")
  close: entries == event-sayısı · watch_head == son entry_sha (boşsa prev)

Doğrulama fail-loud'dur: her uyuşmazlık exit 1 (RED) — sessiz-geçiş yoktur.

Kullanım:
    python pugio_watch_receiver.py <watch_feed.jsonl>   # akışı uçtan-uca doğrula
    python pugio_watch_receiver.py --selftest           # temiz+bozuk senaryo içsel
"""

from __future__ import annotations

import hashlib
import json
import sys

BRIDGE_VERSION = 1
GENESIS = "0" * 64


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def verify_feed(lines: list[str]) -> tuple[bool, str]:
    """JSONL satır-listesini zincir-boyunca doğrula (SESTER'suz)."""
    manifest = close = None
    count = 0
    prev = GENESIS
    for i, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            e = json.loads(raw)
        except json.JSONDecodeError as ex:
            return False, f"satır {i}: JSON bozuk: {ex}"
        t = e.get("type")
        if int(e.get("bridge_version", -1)) != BRIDGE_VERSION:
            return False, f"satır {i}: bridge_version uyuşmuyor"
        if t == "watch_manifest":
            if manifest is not None:
                return False, f"satır {i}: ikinci manifest"
            if e.get("source") != "sikke":  # DONUK kablo-alanı
                return False, f"satır {i}: kaynak DONUK değeriyle uyuşmuyor"
            manifest = e
        elif t == "watch_event":
            if manifest is None:
                return False, f"satır {i}: manifest'siz olay"
            if close is not None:
                return False, f"satır {i}: close'tan sonra olay"
            exp = _sha(
                f"{prev}|{int(e.get('seq', -1))}|{e.get('ts', '')}|"
                f"{e.get('agent', '')}|{e.get('host', '')}|"
                f"{e.get('rule_id', '')}|{e.get('decision', '')}"
            )
            if exp != e.get("entry_sha") or e.get("prev_entry_sha") != prev:
                return False, f"satır {i}: zincir bağı kopuk (seq {e.get('seq')})"
            prev = exp
            count += 1
        elif t == "watch_close":
            if close is not None:
                return False, f"satır {i}: ikinci close"
            if int(e.get("entries", -1)) != count:
                return False, f"satır {i}: entries ({e.get('entries')}) ≠ olay-sayısı ({count})"
            if e.get("watch_head") != prev:
                return False, f"satır {i}: watch_head uyuşmuyor"
            close = e
        else:
            return False, f"satır {i}: bilinmeyen tip {t!r}"
    if manifest is None or close is None:
        return False, "manifest/close eksik"
    return True, f"akış-SAĞLAM: {count} olay, head={prev[:16]}…"


def _selftest() -> int:
    """Temiz-akış KABUL + kurcalanmış-akış RED — ikisi de içsel üretim."""
    base = {
        "bridge_version": BRIDGE_VERSION, "source": "sikke",
        "watcher_id": "selftest", "bundle_head": "a" * 64,
        "bundle_merkle_root": "b" * 64, "bundle_event_count": 2,
    }
    prev = GENESIS
    events = []
    for i, (host, rule, dec) in enumerate([
        ("/weather", "quota_exceeded", "deny"),
        ("/weather", "replay", "deny"),
    ], start=1):
        ts = f"{1700000000.0 + i:.6f}"
        sha = _sha(f"{prev}|{i}|{ts}|ag-w|{host}|{rule}|{dec}")
        events.append({
            "type": "watch_event", "bridge_version": BRIDGE_VERSION,
            "seq": i, "ts": ts, "agent": "ag-w", "host": host,
            "rule_id": rule, "decision": dec,
            "prev_entry_sha": prev, "entry_sha": sha,
        })
        prev = sha
    lines = [json.dumps({"type": "watch_manifest", **base},
                        sort_keys=True, separators=(",", ":")),
             *(json.dumps(e, sort_keys=True, separators=(",", ":")) for e in events),
             json.dumps({"type": "watch_close", "bridge_version": BRIDGE_VERSION,
                         "entries": 2, "watch_head": prev},
                        sort_keys=True, separators=(",", ":"))]
    ok, msg = verify_feed(lines)
    print(("OK  " if ok else "RED ") + msg)
    bad = list(lines)
    bad[1] = bad[1].replace('"decision":"deny"', '"decision":"allow"')
    ok2, msg2 = verify_feed(bad)
    print(("OK  " if not ok2 else "RED ") + "kurcalanmış-akış reddi: " + msg2)
    return 0 if (ok and not ok2) else 1


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--selftest":
        return _selftest()
    if len(argv) != 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        ok, msg = verify_feed(f.readlines())
    print(("OK  " if ok else "RED ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
