"""Gömülü ayna-alıcı testleri — donuk K1/K3 zarf-sözleşmesi kardeşsiz-kanıt.

`bridge_receivers/` altındaki pür-stdlib alıcılar (kardeş-repoya kopyalanmaya
hazır artefaktlar) subprocess ile koşar; SESTER üreticileriyle uçtan-uca
çember kurulur:
  K1: produce_bundle → tamga_anchor_json → tamga_pugio_receiver (KABUL)
      + kurcalanmış-çıpa (RED)
  K3: produce_bundle → watch_feed_jsonl → pugio_watch_receiver (KABUL)
      + kurcalanmış-akış (RED)
  + iki alıcının kendi selftest'i (temiz+bozuk içsel senaryo).

Böylece donuk kablo-alanları (`source: "sikke"`, `pugio_evidence_bundle`,
anchor_id/entry_sha formülleri) kardeş-repo makinede OLMASA bile her
koşumda regresyona karşı sabitlenir.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sester.bridges import tamga_anchor_json, verify_tamga_anchor, veridict_claims_json
from sester.evidence import produce_bundle
from sester.ledger import Ledger
from sester.watchfeed import watch_feed_jsonl

ROOT = Path(__file__).resolve().parent.parent
K1 = ROOT / "bridge_receivers" / "tamga_pugio_receiver.py"
K3 = ROOT / "bridge_receivers" / "pugio_watch_receiver.py"


def _bundle(tmp_path: Path) -> dict:
    led = Ledger(tmp_path / "m.sqlite3", secret="mirror")
    try:
        led.append("permission_decision", "ag-m", "/weather",
                   payload={"decision": "deny", "rule_id": "quota_exceeded"})
        led.append("charge_receipt", "ag-m", "/weather", 0.05,
                   payload={"nonce": "mn1", "paid": 0.05, "scheme": "pugio0"})
        led.append("permission_decision", "ag-m", "/weather",
                   payload={"decision": "deny", "rule_id": "replay"})
        return produce_bundle(led, agent_id="ag-m")
    finally:
        led.close()


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, timeout=60)


# ------------------------------------------------------------------ selftest

@pytest.mark.parametrize("script", [K1, K3], ids=["K1-tamga", "K3-veridict"])
def test_receiver_selftest(script: Path):
    r = _run(script, "--selftest")
    assert r.returncode == 0, f"{script.name} selftest RED: {r.stdout} {r.stderr}"
    assert r.stdout.count("OK") >= 2  # temiz-KABUL + kurcalanmış-RED


# ------------------------------------------------------------------ K1 çemberi

def test_k1_producer_to_embedded_receiver(tmp_path):
    b = _bundle(tmp_path)
    anchor_file = tmp_path / "cipa.jsonl"
    anchor_file.write_text(tamga_anchor_json(b, agent_label="ag-m") + "\n",
                           encoding="utf-8")
    r = _run(K1, str(anchor_file))
    assert r.returncode == 0, f"temiz-çıpa RED: {r.stdout} {r.stderr}"
    assert "SAĞLAM" in r.stdout

    # kurcalama: event_count değişir → alıcı RED (fail-loud)
    tampered = json.loads(anchor_file.read_text(encoding="utf-8"))
    tampered["event_count"] = 99
    anchor_file.write_text(json.dumps(tampered, sort_keys=True,
                                      separators=(",", ":")) + "\n", encoding="utf-8")
    r2 = _run(K1, str(anchor_file))
    assert r2.returncode == 1, "kurcalanmış-çıpa kabul edildi (fail-loud kırıldı)"
    assert "anchor_id" in r2.stdout


def test_k1_library_verifier_agrees_with_embedded_receiver(tmp_path):
    b = _bundle(tmp_path)
    line = tamga_anchor_json(b, agent_label="ag-m")
    ok_lib, _ = verify_tamga_anchor(json.loads(line))
    anchor_file = tmp_path / "a.jsonl"
    anchor_file.write_text(line + "\n", encoding="utf-8")
    r = _run(K1, str(anchor_file))
    assert ok_lib and r.returncode == 0


# ------------------------------------------------------------------ K3 çemberi

def test_k3_producer_to_embedded_receiver(tmp_path):
    b = _bundle(tmp_path)
    feed = tmp_path / "watch.jsonl"
    feed.write_text(watch_feed_jsonl(b, watcher_id="mirror-test") + "\n",
                    encoding="utf-8")
    r = _run(K3, str(feed))
    assert r.returncode == 0, f"temiz-akış RED: {r.stdout} {r.stderr}"
    assert "SAĞLAM" in r.stdout

    # kurcalama: bir karar 'deny' → 'allow' döndürülür → zincir-bağı kopmalı
    lines = feed.read_text(encoding="utf-8").splitlines()
    victim = next(i for i, l in enumerate(lines)
                  if '"watch_event"' in l or '"type":"watch_event"' in l)
    obj = json.loads(lines[victim])
    obj["decision"] = "allow"
    lines[victim] = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    feed.write_text("\n".join(lines) + "\n", encoding="utf-8")
    r2 = _run(K3, str(feed))
    assert r2.returncode == 1, "kurcalanmış-akış kabul edildi (fail-loud kırıldı)"


def test_k2_claims_shape_frozen(tmp_path):
    """K2 claim-zarfı: donuk kimlik-alanları + reproducible + evidence-bağı."""
    b = _bundle(tmp_path)
    doc = json.loads(veridict_claims_json(b))
    assert doc["source"] == "sikke"          # DONUK
    assert doc["bridge_version"] == 1
    values = [c["claim"] for c in doc["claims"]]
    assert values == ["quota_enforced", "replay_denied", "chain_integrity"]
    for c in doc["claims"]:
        assert c["verifiability"] == "reproducible"
        assert c["evidence"]["kind"] == "pugio_evidence_bundle"   # DONUK
        assert c["evidence"]["head"] == b["head"]
        assert c["evidence"]["merkle_root"] == b["merkle_root"]
