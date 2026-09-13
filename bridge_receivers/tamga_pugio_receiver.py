#!/usr/bin/env python3
"""Tamga-tarafı SESTER-çıpa alıcısı — K1 (K0_SHARED_ENVELOPE_SPEC).

KARDEŞ-REPO ARTİFAKTIDIR: SESTER kütüphanesini IMPORT ETMEZ (pür stdlib:
json + hashlib + sys). Tamga deposunun köküne kopyalanır; SESTER'nun
`sester/bridges.tamga_anchor_json` çıktısını (tek JSONL satırı) alır.

Sözleşme (DONUK kablo-alanları — ESKI_KIMLIK.md):
  type == "external_anchor" · source == "sikke" · bridge_version == 1
  anchor_id = sha256("{head}|{merkle_root}|{event_count}")[:32]

Doğrulama fail-loud'dur: her uyuşmazlık exit 1 (RED) — sessiz-geçiş yoktur.

Kullanım:
    python tamga_pugio_receiver.py <cipa.jsonl>   # dosyadaki her satırı doğrula
    python tamga_pugio_receiver.py --selftest     # temiz+bozuk senaryo içsel
"""

from __future__ import annotations

import hashlib
import json
import sys

BRIDGE_VERSION = 1
GENESIS_HEAD_LEN = 64


def verify_anchor(line: str) -> tuple[bool, str]:
    """Tek JSONL-satırını pür sha256 ile doğrula (SESTER'suz)."""
    try:
        a = json.loads(line)
    except json.JSONDecodeError as e:
        return False, f"JSON bozuk: {e}"
    if a.get("type") != "external_anchor":
        return False, "zarf-tipi external_anchor değil"
    if a.get("source") not in ("sikke", "pugio"):
        # K0 §5 read-compat (2026-09-13 SESTER-göçü): DONUK birincil "sikke";
        # eski "pugio" çıktıları geri-uyum için okunur (bridge_version kapısı
        # ayrıca denetlenir — v1). Sessiz-geçiş yok — bilinmeyen-kaynak RED.
        return False, "kaynak uyuşmuyor (beklenen: sikke|pugio)"
    if int(a.get("bridge_version", -1)) != BRIDGE_VERSION:
        return False, "bridge_version uyuşmuyor"
    head = str(a.get("head", ""))
    merkle = str(a.get("merkle_root", ""))
    try:
        count = int(a.get("event_count", -1))
    except (TypeError, ValueError):
        return False, "event_count tam-sayı değil"
    if len(head) != GENESIS_HEAD_LEN or len(merkle) != GENESIS_HEAD_LEN:
        return False, "head/merkle_root 64-hex değil"
    expect = hashlib.sha256(f"{head}|{merkle}|{count}".encode()).hexdigest()[:32]
    if expect != a.get("anchor_id"):
        return False, "anchor_id bağı kopuk (veri-değişikliği)"
    return True, f"çıpa-SAĞLAM: {a.get('anchor_id')} agent={a.get('agent')}"


def _selftest() -> int:
    """Temiz-çıpa KABUL + kurcalanmış-çıpa RED — ikisi de içsel üretim."""
    head = hashlib.sha256(b"selftest-chain").hexdigest()
    merkle = hashlib.sha256(b"selftest-merkle").hexdigest()
    anchor = {
        "type": "external_anchor", "bridge_version": BRIDGE_VERSION,
        "source": "sikke", "pugio_bundle_version": 1,
        "agent": "selftest-agent", "event_count": 3,
        "anchor_id": hashlib.sha256(f"{head}|{merkle}|3".encode()).hexdigest()[:32],
        "head": head, "merkle_root": merkle,
    }
    line = json.dumps(anchor, sort_keys=True, separators=(",", ":"))
    ok, msg = verify_anchor(line)
    print(("OK  " if ok else "RED ") + msg)
    bad = dict(anchor, event_count=4)  # kurcalama: sayı değişti, bağ kopmalı
    ok2, msg2 = verify_anchor(json.dumps(bad, sort_keys=True, separators=(",", ":")))
    print(("OK  " if not ok2 else "RED ") + "kurcalanmış-çıpa reddi: " + msg2)
    return 0 if (ok and not ok2) else 1


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--selftest":
        return _selftest()
    if len(argv) != 2:
        print(__doc__)
        return 2
    fails = 0
    with open(argv[1], encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            if not line.strip():
                continue
            ok, msg = verify_anchor(line)
            print(f"satır {i}: " + ("OK  " if ok else "RED ") + msg)
            fails += 0 if ok else 1
    if fails:
        print(f"SONUÇ: RED — {fails} satır kırık")
        return 1
    print("SONUÇ: SAĞLAM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
