"""Settlement-vector karşılıklı-pin'leme (Veridict-Q2-çıktısı).

Köprü-kontratını-alıcı-tarafında-da-sabitle: Sester-CI tek-başına-yetersizdi
(Sester-bağı-kopsa-Veridict'te-hiçbir-şey-pin'lemiyordu); Veridict
`docs/standard-test-vectors/settlement/` + sıfır-bağımlı
`verify_settlement_vector.py` ile ikinci-ankor kurdu. Bu-test-onu-çalıştırır
ve-RED-dediği-gerçekten-RED-diye-kanıtlar (fail-loud-doktrini)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_71_veridict_settlement_vectors_are_green():
    """Karşılıklı-pin'leme (Veridict-Q2-çıktısı): köprü-kontratını-alıcı-tarafında
    da-sabitle. Sester-CI tek-başına-yetersizdi (Sester-bağı-kopsa-Veridict'te-
    hiçbir-şey-pin'lemiyordu); Veridict `docs/standard-test-vectors/settlement/`
    + sıfır-bağımlı `verify_settlement_vector.py`-ile-ikinci-ankor-kurdu.
    Burada-onu-çalıştırırız: temiz→PASS, kurcalama→RED. K2/K3-çift-ankor."""
    receiver = os.environ.get("SESTER_VERIDICT_PATH")
    if not receiver or not Path(receiver).is_dir():
        pytest.skip("Veridict checkout bu makinede yok (CI cross-repo job)")
    v = Path(receiver) / "scripts" / "verify_settlement_vector.py"
    if not v.exists():
        pytest.skip("settlement-vector selftest Veridict'te henüz yok")
    r = subprocess.run([sys.executable, str(v)], capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0, f"vector-RED: {r.stdout} {r.stderr}"
    assert "4/4" in (r.stdout + r.stderr), "4 tamper-vakasının-hepsi-rede-edilmeli"


def test_72_settlement_vectors_reject_tamper():
    """Negatif-kontrol: vector-selftest'in-RED-dediği-gerçekten-RED. Bir-tamper
    dosyasını-geçici-olarak-boz → selftest exit-1-vermeli (fail-loud-doktrini)."""
    receiver = os.environ.get("SESTER_VERIDICT_PATH")
    if not receiver or not Path(receiver).is_dir():
        pytest.skip("Veridict checkout bu makinede yok (CI cross-repo job)")
    base = Path(receiver) / "docs" / "standard-test-vectors" / "settlement"
    claim = base / "claim.json"
    if not claim.exists():
        pytest.skip("vector dosyaları yok")
    original = claim.read_text(encoding="utf-8")
    try:
        # accepted_claims-sayısını-şişir (coverage_inflated-saldırı-sınıfı)
        data = json.loads(original)
        data["accepted_claims"] = int(data.get("accepted_claims", 1)) + 100
        claim.write_text(json.dumps(data), encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(Path(receiver) / "scripts"
             / "verify_settlement_vector.py")],
            capture_output=True, text=True, timeout=120)
        assert r.returncode != 0, "şişirilmiş-claim GREEN-geçti — vector-bozuk"
    finally:
        claim.write_text(original, encoding="utf-8")
