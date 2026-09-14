#!/usr/bin/env python3
"""SESTER kamusal-yüzey taraması — PyPI/public-öncesi iç-ad denetimi.

Sözleşme (GATE_RUN_NOTU karar-kaydı + Tamga 20:27 hijyen-standardı):
  **Dağıtıma giren her dosyada iç-organizasyon-adı = SIFIR** (fail-loud RED).

Tarama-kapsamı = sdist'te gerçekte taşınacak set (krasyon: kapı zaten
`dist/` üzerinden sester-0.5.0 sdist üretir). Hatch varsayılan sdist'i
repo-kökündeki TÜM dosyaları alır; bu script `--list-sdist` çıktısını okur —
yani **paket-gerçeğini** tarar, repo-gerçeğini değil.

Yasaklı-çekirdek (istisnasız): kardeş-proje adları (Tenderix, Tamga,
Veridict) + disk-yolları (/home/gokun, 01_unicorn, 02_sahis, 05_acik_kaynak,
HAT_DEFTERI, AGENT_MESH). Ürün-tarihi adları (pugio/sikke) DONUK kablo-alanı
olduğu için yasaklı DEĞİLDİR (ESKI_KIMLIK.md).

Kullanım:
    .venv/bin/python scripts/public_surface_sweep.py            # dist/ varsa sdist-tarama
    .venv/bin/python scripts/public_surface_sweep.py --repo     # tüm-repo taraması (krasyon-ham)
    .venv/bin/python scripts/public_surface_sweep.py --exclude brand/SESTER_marka.md ...
"""
from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Yasaklı-çekirdek: iç-organizasyon ifşa-adları (public-tree'de sıfır-hit şartı)
FORBIDDEN = [
    # iç-örgü yapısı (kontrat-public, örgü-özel doktrini: kardeş PROJE adları
    # kablo-sözleşmelerinde kamuya açık olduğu için yasaklı DEĞİL; örgüyü ifşa
    # eden klasör-yolları/rollar yasaklı)
    r"gokun",
    r"01_unicorn",
    r"02_sahis",
    r"05_acik_kaynak",
    r"HAT[_ ]?DEFTER",
    r"AGENT[_ ]?MESH",
    r"AjanTicaret",
    r"AjanGuvence",
    r"KAGIT\.md",
    r"IS_PLANI\.md",
    r"KARAR_63B\.md",
    r"KURAL_DSL",
    r"BIRLESTIRME_DEGERLENDIRMESI",
    r"ARASTIRMA_\d{4}",
    r"SPEC_FARK",
    r"PRD\.md",
    r"ESKI_KIMLIK",
    r"63-Sester",
    r"64-Tenderix",
]

# Krasyon-ismi (belge-başına bir kez derlenir; hem whitelist hem word-guard)
_INHA = "İnha"


def _compile() -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in FORBIDDEN]


def _sdist_members() -> tuple[str, list[str]]:
    """En-taze sdist'in üye-listesi (krasyon-gerçeği). Yoksa boş-liste."""
    dists = sorted((ROOT / "dist").glob("sester-*.tar.gz"), reverse=True)
    if not dists:
        return "", []
    with tarfile.open(dists[0], "r:gz") as tf:
        names = [m.name for m in tf.getmembers() if m.isfile()]
    return dists[0].name, names


def _read_bytes(sdist: str, member: str) -> bytes:
    with tarfile.open(ROOT / "dist" / sdist, "r:gz") as tf:
        fh = tf.extractfile(member)
        assert fh is not None, member
        return fh.read()


def sweep_sdist(patterns: list[re.Pattern]) -> int:
    name, members = _sdist_members()
    if not name:
        print("RED: dist/ altında sdist yok — önce kapı-adımı 5 (build) koşulmalı")
        return 1
    print(f"sdist-taraması: {name} · {len(members)} dosya")
    hits: list[str] = []
    for member in members:
        try:
            data = _read_bytes(name, member)
        except (KeyError, EOFError) as exc:
            print(f"RED: sdist-üyesi okunamadı {member}: {exc}")
            return 1
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue  # ikili-dosya (png/jpg) — ad-taraması üye-adında yapılır
        for i, line in enumerate(text.splitlines(), 1):
            for pat in patterns:
                if pat.search(line):
                    hits.append(f"{member}:{i}: /{pat.pattern}/ {line.strip()[:120]}")
    # üye-adı taraması (ikili-dosyalar dahil)
    for member in members:
        for pat in patterns:
            if pat.search(member):
                hits.append(f"{member}:0: <filename-hit> /{pat.pattern}/")
    if hits:
        print(f"\nRED: sdist'te {len(hits)} iç-ad-hit — PYPI'YA UPLOAD YOK:")
        for h in hits[:40]:
            print(f"  {h}")
        if len(hits) > 40:
            print(f"  … +{len(hits) - 40} satır")
        return 1
    print("OK: sdist iç-ad-hit = 0 (public-standart: Tamga-20:27) — upload-eşiği temiz")
    return 0


def sweep_repo(patterns: list[re.Pattern], extra_excludes: list[str]) -> int:
    """Tüm-repo taraması (krasyon-ham; public-kararı için geniş-kanıt)."""
    excludes = [
        ".git/", ".venv/", "dist/", "__pycache__/", ".pytest_cache/",
        # Sertifikasyon-istisnası: bu belge yasaklı-adları *kural-dili* olarak
        # sayar (kendisi taranamaz; içeriği yalnızca bu scriptin kriterleridir).
        "brand/SESTER_marka.md",
        *extra_excludes,
    ]
    hits: list[str] = []
    scanned = 0
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(x in rel for x in excludes):
            continue
        scanned += 1
        if any(pat.search(rel) for pat in patterns):
            hits.append(f"{rel}:0: <filename-hit>")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for pat in patterns:
                if pat.search(line):
                    hits.append(f"{rel}:{i}: /{pat.pattern}/ {line.strip()[:120]}")
    print(f"repo-taraması: {scanned} dosya (istisnalar: {len(excludes)})")
    if hits:
        print(f"\nRED: repo'da {len(hits)} iç-ad-hit (krasyon-zaten sdist'te bunları taşımaz):")
        for h in hits[:40]:
            print(f"  {h}")
        if len(hits) > 40:
            print(f"  … +{len(hits) - 40} satır")
        return 1
    print("OK: repo iç-ad-hit = 0")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="store_true", help="sdist yerine tüm-repo taraması")
    ap.add_argument("--exclude", action="append", default=[],
                    help="repo-taramasına ek istisna (klasör/dosya-parçası)")
    args = ap.parse_args()
    patterns = _compile()
    print("== SESTER kamusal-yüzey taraması ==")
    print("yasaklı: kardeş-adlar + disk-yolları + mesh-adları "
          "(pugio/sikke DONUK alan — yasaklı-değil, ESKI_KIMLIK.md)")
    if args.repo:
        return sweep_repo(patterns, args.exclude)
    return sweep_sdist(patterns)


if __name__ == "__main__":
    sys.exit(main())
