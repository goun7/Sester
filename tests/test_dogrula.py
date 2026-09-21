"""dogrula.py okuma-kapısı — K0 §7 rule-9'un-alıcı-tarafı-makine-kilidi
(Tamga AT-060-aynası: AT-059-sadece-YAZMA'yı-kilitlemiş, okuma-yolunda-ihlal
GREEN-geçiyordu; burada-da-aynı-boşluk-vardı: dogrula.py zincir/proof/head/
merkle'yi-doğruluyor-AMA-event_type'ları-doğrulamıyordu → operatör-bilinmeyen-
tip-yazarsa 'SAĞLAM'-geçiyordu).

Üç-mod-ölçülür: default=WARN (exit-3), --strict=RED (exit-1),
--known-types=... ile-alıcının-kümesi. Sessiz-geçiş-yasak (kural-9)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from sester.evidence import produce_bundle
from sester.ledger import Ledger

REPO = Path(__file__).resolve().parents[1]
DOGRULA = REPO / "scripts" / "dogrula.py"
GENESIS_REF = "0" * 64


def _merkle(leaves: list[str]) -> str:
    """dogrula.py'nin-aynı-merkle-algoritması (test-yardımcısı-kopyası)."""
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    layer = leaves
    while len(layer) > 1:
        nxt = [hashlib.sha256((layer[i] + layer[i + 1]).encode()).hexdigest()
               for i in range(0, len(layer) - 1, 2)]
        if len(layer) % 2:
            nxt.append(layer[-1])
        layer = nxt
    return layer[0]


def _bundle_path(tmp_path: Path, *, inject_type: str | None = None) -> Path:
    """Sistem-ledger'ından-gerçek-bundle-üret; inject_type verilirse bundle-
    JSON'undaki son-event'in-tipi-değiştirilip-proof/head/merkle-yeniden-
    hesaplanır — operatör-DOĞRUDAN-YAZMA simülasyonu (Ledger.append'in-yazma-
    kapısını-atlar; zincir-hâlâ-geçerli, tip-bilinmiyor)."""
    led = Ledger(tmp_path / "dg.sqlite3", secret="dg")
    led.append("charge_receipt", "a1", "/w", 0.05, payload={"nonce": "n1"})
    led.append("charge_receipt", "a1", "/w", 0.05, payload={"nonce": "n2"})
    b = produce_bundle(led)
    led.close()
    if inject_type:
        evs = b["events"]
        evs[-1]["event_type"] = inject_type
        # kanonik-proof'u-yeniden-hesapla (zincir-kopmasın-diye) — bu-tam-
        # operatörün-doğrudan-SQL/COPY-ile-yazdığı-satırın-yaptığı-şey
        prev = evs[-2]["proof"] if len(evs) > 1 else GENESIS_REF
        evs[-1]["prev_proof"] = prev
        canon = "|".join([
            f"{evs[-1]['ts']:.6f}", evs[-1]["event_type"],
            evs[-1]["agent_id"], evs[-1]["host"],
            f"{evs[-1]['amount']:.6f}", evs[-1]["payload"], prev])
        evs[-1]["proof"] = hashlib.sha256(canon.encode()).hexdigest()
        b["head"] = evs[-1]["proof"]
        b["merkle_root"] = _merkle([e["proof"] for e in evs])
        b["event_count"] = len(evs)
    p = tmp_path / "b.json"
    p.write_text(json.dumps(b), encoding="utf-8")
    return p


def _run(path: Path, *flags: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(DOGRULA), str(path), *flags],
                       capture_output=True, text=True, cwd=str(REPO))
    return r.returncode, r.stdout + r.stderr


def test_clean_bundle_passes_silently(tmp_path):
    """Bilinen-tipler → SAĞLAM + exit-0 + uyarı-yok."""
    rc, out = _run(_bundle_path(tmp_path))
    assert rc == 0
    assert "SAĞLAM" in out
    assert "bilinmeyen" not in out


def test_unknown_type_warns_by_default(tmp_path):
    """Kural-9 varsayılan: bilinmeyen-tip → WARN + exit-3 (sessiz-geçiş-yok).
    Zincir-hâlâ-GREEN-olduğu-için-SAĞLAM-basılmakta — uyarı-eklenti."""
    rc, out = _run(_bundle_path(tmp_path, inject_type="operator_wrote_this"))
    assert rc == 3, f"warn-expected-exit-3, got {rc}: {out}"
    assert "bilinmeyen-event_type" in out
    assert "SAĞLAM" in out


def test_unknown_type_strict_is_red(tmp_path):
    """--strict: bilinmeyen-tip → RED (exit-1). Alıcının-reject-seçimi."""
    rc, out = _run(_bundle_path(tmp_path, inject_type="operator_wrote_this"),
                   "--strict")
    assert rc == 1
    assert "RED" in out


def test_known_types_override_accepts_custom(tmp_path):
    """--known-types: alıcı kendi-kapalı-kümesini-tanımlar (kural-9: karar-
    alıcıda). Kümesinde-olmayan-RED, olan-WARN-olarak-kalmaz → SAĞLAM."""
    rc, out = _run(
        _bundle_path(tmp_path, inject_type="custom_ok"),
        "--known-types=charge_receipt,custom_ok")
    assert rc == 0, out
    assert "SAĞLAM" in out


def test_family_prefix_is_known(tmp_path):
    """facilitator_-ön-eki-bilinen-aile → uyarı-yok (K0 §2 dinamik-aileler)."""
    rc, out = _run(_bundle_path(tmp_path, inject_type="facilitator_verify"))
    assert rc == 0
    assert "bilinmeyen" not in out
