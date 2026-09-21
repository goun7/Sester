"""Ortak-test-yardımcıları + geliştirici-otomatik-keşif.

Kardeş-repo-yolları (Tamga/Veridict) CI'da env-ile-set-edilir; yerelde-bırakın
testler-skip-olsun-diye-beklemek-yerine, bu-conftest-yaygın-yerel-klon-
düzenlerini-deneyip-otomatik-set-ediyor (SESTER_TAMGA_PATH/SESTER_VERIDICT_PATH
henüz-set-edilmemişse-ve-bir-aday-bulunursa).

Neden: 5-s4-ingest-testi + 2-sovereign-testi-yalnızca-bu-env-yüzünden-skip-
oluyordu; CI-yeşil-olduğu-için-yerelde-eksiklik-görünmüyordu (gizli-boşluk).
"""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Yaygın-yerel-klon-düzenleri: ../05_acik_kaynak/ (bu-makinenin-düzeni),
# ../<sibling>/, ./siblings/ (CI-checkout-düzeni), ve-projeler-kökünde-tarama.
_SIBLING_CANDIDATES = [
    REPO.parent / "05_acik_kaynak" / "TamgaProtocol",
    REPO.parent / "TamgaProtocol",
    REPO / "siblings" / "tamga",
    REPO.parent / "siblings" / "tamga",
    # projeler-kökünde-tarama: ../../*/*/TamgaProtocol (bu-makine: 05_acik_kaynak)
    *[p / "TamgaProtocol" for p in (REPO.parents[1]).glob("*") if p.is_dir()],
]
_VERIDICT_CANDIDATES = [
    REPO.parent / "05_acik_kaynak" / "Veridict",
    REPO.parent / "Veridict",
    REPO / "siblings" / "veridict",
    REPO.parent / "siblings" / "veridict",
    *[p / "Veridict" for p in (REPO.parents[1]).glob("*") if p.is_dir()],
]


def _maybe_set(var: str, candidates: list[Path], marker: str) -> None:
    """Env-henüz-set-değilse-ve-bir-aday-geçerliyse-set-et (sessizce-atla)."""
    if os.environ.get(var):
        return
    for c in candidates:
        if (c / marker).is_file():
            os.environ[var] = str(c)
            return


_maybe_set("SESTER_TAMGA_PATH", _SIBLING_CANDIDATES, "tamga_pugio_ingest.py")
_maybe_set("SESTER_VERIDICT_PATH", _VERIDICT_CANDIDATES,
           "scripts/pugio_watch_receiver.py")
