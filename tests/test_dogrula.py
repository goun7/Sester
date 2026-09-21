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
import re
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


# ---------------- K0 §4 şema-paritesi (Tamga AT-061 aynası: alan-çıkarımı) ----

SPEC = Path(__file__).resolve().parents[1] / "docs" / "K0_SHARED_ENVELOPE_SPEC.md"


def _k0_bundle_schema() -> tuple[set, set]:
    """K0 §4'ün-donmuş-JSON-bloğundan-alanları-ÇIKARIR (elle-liste-değil —
    Tamga AT-061'in-ilklesi: sabit-liste-kirlenir, dokümandan-çıkarmaz).
    (top-alanlar, event-alanlar) döner. Doküman-yapısı-değişirse-test-RED."""
    spec = SPEC.read_text(encoding="utf-8")
    sec = spec[spec.find("## 4) Bundle"):spec.find("## 5) Anchor")]
    m = re.search(r'```json\n(.*?)```', sec, re.S)
    assert m, "K0 §4-JSON-bloğu-bulunamadı (spec-yapısı-değişmiş)"
    block = m.group(1)
    # top-alanlar: "anahtar": değer (tırnaklı-anahtar)
    top = set(re.findall(r'"([a-z_0-9]+)"\s*:', block))
    # event-alanlar: {seq, ts, ...} — küme-içindekiler
    ev = set()
    em = re.search(r'\{([^{}]*)\}', block)
    if em:
        ev = set(re.findall(r'\b([a-z_0-9]+)\b', em.group(1)))
    return top, ev


def test_real_bundle_matches_k0_schema_by_extraction(tmp_path):
    """Tamga AT-061-aynası: donmuş-tasarım-vs-gerçek-çıkı, ALAN-ÇIKARIMIYLA.
    K0-§4'ten-çıkarılan-alanlar == produce_bundle'ın-gerçek-alanları. İki-yön:
    (a) gerçek-alanların-hepsi-K0'da-belgeli (uydurma-alan-yok),
    (b) K0'da-belgeli-alanların-hepsi-gerçekte-var (belge-arkasında-yok)."""
    led = Ledger(tmp_path / "sp.sqlite3", secret="sp")
    led.append("charge_receipt", "a1", "/w", 0.05, payload={"nonce": "n1"})
    b = produce_bundle(led)
    led.close()

    k0_top, k0_ev = _k0_bundle_schema()
    real_top = set(b.keys())
    real_ev = set(b["events"][0].keys())

    # (a) uydurma-alan-yok — gerçek-bundle-dağıtım-alan-getirmez
    extra_top = real_top - k0_top
    extra_ev = real_ev - k0_ev
    assert not extra_top, f"K0-§4'te-yok-ama-bundle'da-var: {extra_top}"
    assert not extra_ev, f"K0-§4-event'inde-yok: {extra_ev}"
    # (b) belge-arkasında-yok — K0-her-alanı-gerçek-üretimde-var
    assert k0_top <= real_top, f"K0'da-var-ama-bundle'da-yok: {k0_top - real_top}"
    assert k0_ev <= real_ev, f"K0-event'inde-var: {k0_ev - real_ev}"


def test_k0_schema_extraction_is_stable():
    """Çıkarım-tutarlı: tekrar-çağırma-aynı-sonucu-verer (non-flaky) ve
    boş-değil (spec-değiştiyse-boş-dönerse-bu-test-yakalar)."""
    top, ev = _k0_bundle_schema()
    assert top and ev, "şema-çıkarımı-boş-döndü (K0-§4-yapısı-bozulmuş)"
    assert "pugio_bundle_version" in top
    assert "merkle_root" in top
    assert "prev_proof" in ev
