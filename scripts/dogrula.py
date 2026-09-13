#!/usr/bin/env python3
"""Alıcı-tarafı kanıt-dogrulayıcı — 81-MERGEN / müşteri-denetçisi perspektifi.

Bu script BİLGİNCE pugio kütüphanesini İÇERMEZ (yalnız stdlib: json + hashlib):
kanıt-bundle'ı üretenden bağımsız doğrulanır — 63↔81 kontratının S4 kabulü.

Kullanım:  python scripts/dogrula.py adoption/s1-kanit-bundle.json
Çıkış:     0 = SAĞLAM, 1 = KIRIK (neden yazılır)
"""

from __future__ import annotations

import hashlib
import json
import sys

GENESIS = "0" * 64


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
    if len(argv) != 2:
        print("kullanım: dogrula.py <bundle.json>")
        return 2
    bundle = json.loads(open(argv[1], encoding="utf-8").read())
    events = bundle["events"]
    prev = GENESIS
    proofs: list[str] = []
    for ev in events:
        if ev["prev_proof"] != prev:
            print(f"✗ zincir-kopması @seq={ev['seq']}")
            return 1
        canonical = "|".join([
            f"{ev['ts']:.6f}", ev["event_type"], ev["agent_id"], ev["host"],
            f"{ev['amount']:.6f}", ev["payload"], prev,
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
    agents = sorted({e["agent_id"] for e in events})
    receipts = sum(1 for e in events if e["event_type"] == "charge_receipt")
    total = sum(e["amount"] for e in events if e["event_type"] == "charge_receipt")
    print(f"✓ SAĞLAM: {len(events)} olay · {receipts} ücretli-işlem · toplam {total:.2f}")
    print(f"  ajanlar: {', '.join(agents)}")
    print(f"  head: {prev}")
    print(f"  merkle-kök: {bundle['merkle_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
