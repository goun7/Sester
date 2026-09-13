#!/usr/bin/env python3
"""SESTER pre-commit guard — mesh sözleşme-deneticisi (AGENT_MESH_PROTOCOLU.md).

Kontroller (fail-loud; RED commit'i bloklar):
  1) sürüm-senkronu: pyproject.toml == sester/__init__.__version__
  2) DONUK kablo-alanı: sester/bridges.py `source: "sikke"` üretmeye devam
Gözlem (WARN; bloklamaz — kendi-taraf-kusuru değildir):
  3) kardeş Tamga-alıcısı çift-ad-okuyor mu (sikke|pugio)? drift → HAT DEFTERİ'ne
     drift-satırı düşer (sahibi Tamga; mesaj-taşıyıcı gerekmez).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = Path("/home/gokun/projects/01_unicorn/HAT_DEFTERI.md")
SIBLING_K1 = Path(
    "/home/gokun/projects/05_acik_kaynak/TamgaProtocol/tamga_pugio_receiver.py"
)


def red(msg: str) -> int:
    print(f"\033[1;31m[SESTER-guard] RED: {msg}\033[0m")
    return 1


def ok(msg: str) -> None:
    print(f"\033[1;32m[SESTER-guard] {msg}\033[0m")


def check_version_sync() -> int:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    init = (ROOT / "sester" / "__init__.py").read_text(encoding="utf-8")
    n = re.search(r'__version__\s*=\s*"([^"]+)"', init)
    if not m or not n:
        return red("sürüm-alanı bulunamadı (pyproject/__init__)")
    if m.group(1) != n.group(1):
        return red(f"sürüm-senkronu kırık: pyproject={m.group(1)} "
                   f"!= __init__={n.group(1)}")
    ok(f"sürüm-senkronu: {m.group(1)}")
    return 0


def check_frozen_fields() -> int:
    src = (ROOT / "sester" / "bridges.py").read_text(encoding="utf-8")
    if '"source": "sikke"' not in src:
        return red('DONUK kablo-alanı kayboldu: bridges.py `source: "sikke"` '
                   "(ESKI_KIMLIK.md — v2'ye kadar üretici hep sikke basar)")
    ok('DONUK alan: bridges.py `source: "sikke"` yerinde')
    return 0


def _synthetic_anchor(source: str) -> str:
    head = hashlib.sha256(b"guard-head").hexdigest()
    merkle = hashlib.sha256(b"guard-merkle").hexdigest()
    anchor = {
        "type": "external_anchor", "bridge_version": 1, "source": source,
        "agent": "guard", "event_count": 3,
        "anchor_id": hashlib.sha256(f"{head}|{merkle}|3".encode()).hexdigest()[:32],
        "head": head, "merkle_root": merkle,
    }
    return json.dumps(anchor, sort_keys=True, separators=(",", ":"))


def note_ledger(line: str) -> None:
    try:
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(f"| {time.strftime('%Y-%m-%d %H:%M')} | 63-Sester(guard) "
                     f"| — | {line} |\n")
    except OSError:
        pass  # defter yoksa sessiz-geç (gözlem-katmanı bloklayamaz)


def observe_sibling_k1() -> int:
    """Kardeş-alıcı drift-gözlemi — bloklamaz, defter-e yazar (sahibi Tamga)."""
    if not SIBLING_K1.is_file():
        return 0  # kardeş makinede yok — gözlem-yok
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(_synthetic_anchor("sikke") + "\n")
        probe = fh.name
    try:
        r = subprocess.run([sys.executable, str(SIBLING_K1), probe],
                           capture_output=True, text=True, timeout=30)
    finally:
        Path(probe).unlink(missing_ok=True)
    if r.returncode == 0:
        ok("kardeş K1-alıcısı: DONUK `sikke` kabul ediyor (çift-ad-okuma canlı)")
        return 0
    note_ledger("DRIFT: Tamga K1-alıcısı `sikke` kabul etmiyor (test_74 RED "
                "eder) — Tamga-tarafı guard'ı kendi commit'inde bloklamalı; "
                "K0 §5 çift-ad-okuma kuralı ihlal edildi")
    print("\033[1;33m[SESTER-guard] WARN: kardeş K1-alıcısı driftli "
          "(sikke-RED) — HAT DEFTERİ'ne yazıldı; commit bloklanmıyor "
          "(kusur 63'te değil)\033[0m")
    return 0


def main() -> int:
    print("\033[1;36m== SESTER pre-commit guard ==\033[0m")
    for check in (check_version_sync, check_frozen_fields, observe_sibling_k1):
        rc = check()
        if rc:
            print("\033[1;31mcommit BLOKLANDI — --no-verify KULLANMAYIN "
                  "(bkz. AGENT_MESH_PROTOCOLU.md drift-playbook)\033[0m")
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
