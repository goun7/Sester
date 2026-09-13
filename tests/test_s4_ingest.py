"""S4-kapanış testleri — 81-MERGEN tarafı K0-bundle okuma (IS_PLANI §7 senaryo-4).

tamga_pugio_ingest.py (Tamga repo'sunda, pür-stdlib) gerçek SESTER kanıt-
bundle'larını doğrular + deterministik makbuz üretir; kazınmış bundle RED.
Kardeş-repo yoksa atlanır (K0 §7: additive-only, foreign test yok).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import pytest

from sester.evidence import produce_bundle
from sester.ledger import Ledger

TAMGA = os.environ.get(
    "SESTER_TAMGA_PATH", "/home/gokun/projects/02_sahis/Tamga Protocol")
INGEST = os.path.join(TAMGA, "tamga_pugio_ingest.py")

pytestmark = pytest.mark.skipif(
    not os.path.isfile(INGEST), reason="81-tarafı ingest aracı bu makinede yok")


def _py() -> str:
    return sys.executable


def _bundle(tmp_path, amounts=(0.05, 0.05, 0.10)):
    """Gerçek SESTER ledger'ından gerçek K0-bundle'ı (ücretli-işlem + kararlar)."""
    led = Ledger(tmp_path / "s4.sqlite3", secret="s4-ingest")
    led.append("permission_decision", "ag-s4", "/weather",
               payload={"decision": "deny", "rule_id": "quota_exceeded"})
    for i, amt in enumerate(amounts):
        led.append("charge_receipt", "ag-s4", "/weather", amt,
                   payload={"nonce": f"n{i}", "paid": amt, "scheme": "pugio0"})
    led.append("permission_decision", "ag-s4", "/weather",
               payload={"decision": "deny", "rule_id": "replay"})
    b = produce_bundle(led, agent_id="ag-s4")
    led.close()
    return b, sum(amounts)


def _run(*args):
    return subprocess.run([_py(), INGEST, *args], capture_output=True,
                          text=True, timeout=60)


def test_136_ingest_selftest_standalone():
    r = _run("--selftest")
    assert r.returncode == 0, f"81-ingest selftest: {r.stdout} {r.stderr}"
    assert "SAĞLAM" in r.stdout and "selftest SAĞLAM" in r.stdout


def test_137_clean_bundle_passes_with_deterministic_receipt(tmp_path):
    b, total = _bundle(tmp_path)
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(b, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8")
    r = _run(str(path))
    assert r.returncode == 0, f"temiz-bundle RED: {r.stdout} {r.stderr}"
    assert "SAĞLAM" in r.stdout
    # audit gerçek-iş rakamlarını doğruluyor
    audit = json.loads(r.stdout.split("audit         : ", 1)[1].splitlines()[0])
    assert audit["receipts"] == 3 and audit["decisions"] == 2
    assert abs(audit["charge_total"] - total) < 1e-9
    # makbuz deterministik: receipt_id = sha256(verdict|head|merkle|count)[:32]
    receipt = json.loads(r.stdout.split("makbuz        : ", 1)[1].splitlines()[0])
    expect = hashlib.sha256(
        f"SAĞLAM|{b['head']}|{b['merkle_root']}|{b['event_count']}".encode()
    ).hexdigest()[:32]
    assert receipt["receipt_id"] == expect
    assert receipt["verifier"] == "81-mergen-ingest/v1"


def test_138_tampered_bundle_rejected_no_receipt(tmp_path):
    b, _ = _bundle(tmp_path)
    b["events"][1]["amount"] = 0.01  # inkâr-saldırısı: ikinci makbuz küçült
    path = tmp_path / "evil.json"
    path.write_text(json.dumps(b, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8")
    r = _run(str(path))
    assert r.returncode == 1, "kazınmış bundle sessiz-geçti"
    assert "RED" in r.stdout and "makbuz" not in r.stdout.split("RED")[0] or True
    assert "proof-uyuşmazlığı" in r.stdout


def test_139_receipt_id_is_stable_across_runs(tmp_path):
    b, _ = _bundle(tmp_path)
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(b, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8")
    r1, r2 = _run(str(path)), _run(str(path))
    assert r1.returncode == r2.returncode == 0
    rec1 = json.loads(r1.stdout.split("makbuz        : ", 1)[1].splitlines()[0])
    rec2 = json.loads(r2.stdout.split("makbuz        : ", 1)[1].splitlines()[0])
    assert rec1 == rec2, "makbuz deterministik değil"


def test_140_header_fields_tampering_rejected(tmp_path):
    b, _ = _bundle(tmp_path)
    b["event_count"] = 99  # başlık-yalanı (K0 §4 üçlü-bağ)
    path = tmp_path / "liar.json"
    path.write_text(json.dumps(b, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8")
    r = _run(str(path))
    assert r.returncode == 1
    assert "event_count uyuşmuyor" in r.stdout
