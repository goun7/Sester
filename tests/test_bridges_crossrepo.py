"""Cross-repo köprü testleri — K1 (Tamga alıcısı) + K3 (Veridict alıcısı).

Kardeş-repo alıcıları SESTER kütüphanesini import ETMEDEN, pür stdlib ile
çalışır; bu testler üretici (sester.bridges / sester.watchfeed) ile alıcıyı
subprocess üzerinden uçtan-uca bağlar. Kardeş-repo yoksa testler atlanır
(CI'da yalnızca SESTER-seti koşar).

Kural (K0 §7): üretici çıktısı deterministik; alıcı fail-loud (RED → exit 1).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from sester.bridges import tamga_anchor_json, veridict_claims_json
from sester.evidence import produce_bundle
from sester.ledger import Ledger
from sester.watchfeed import produce_watch_feed, watch_feed_jsonl

# Kardeş-repolar 2026-09-13'te yeniden konumlandı (02_sahis → 05_acik_kaynak;
# boşluk-klasör adları kaldırıldı: TamgaProtocol, Veridict).
TAMGA = os.environ.get(
    "SESTER_TAMGA_PATH",
    "/home/gokun/projects/05_acik_kaynak/TamgaProtocol",
)
VERIDICT = os.environ.get(
    "SESTER_VERIDICT_PATH",
    "/home/gokun/projects/05_acik_kaynak/Veridict",
)
K1_RECEIVER = os.path.join(TAMGA, "tamga_pugio_receiver.py")
K3_RECEIVER = os.path.join(VERIDICT, "scripts", "pugio_watch_receiver.py")

pytestmark = pytest.mark.skipif(
    not (os.path.isfile(K1_RECEIVER) and os.path.isfile(K3_RECEIVER)),
    reason="kardeş-repo alıcıları bu makinede yok",
)


def _py() -> str:
    """Kardeş-repo alıcılarını koşturan yorumlayıcı (venv varsa venv)."""
    return sys.executable


def _bundle(tmp_path) -> tuple[Ledger, dict]:
    """Gerçek ledger'dan gerçek kanıt-bundle'ı (quota + replay olayları dahil)."""
    led = Ledger(tmp_path / "x.sqlite3", secret="cross")
    led.append("permission_decision", "ag-x", "/weather",
               payload={"decision": "deny", "rule_id": "quota_exceeded"})
    led.append("charge_receipt", "ag-x", "/weather", 0.05,
               payload={"nonce": "n1", "paid": 0.05, "scheme": "pugio0"})
    led.append("permission_decision", "ag-x", "/weather",
               payload={"decision": "deny", "rule_id": "replay"})
    led.append("charge_receipt", "ag-x", "/weather", 0.05,
               payload={"nonce": "n2", "paid": 0.05, "scheme": "pugio0"})
    b = produce_bundle(led, agent_id="ag-x")
    return led, b


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_py(), script, *args], capture_output=True, text=True, timeout=60
    )


# ---------------------------------------------------------------- K1 · Tamga

def test_74_k1_tamga_receiver_accepts_clean_anchor(tmp_path):
    led, b = _bundle(tmp_path)
    try:
        anchor_file = tmp_path / "cipa.jsonl"
        anchor_file.write_text(tamga_anchor_json(b, agent_label="ag-x") + "\n",
                               encoding="utf-8")
        r = _run(K1_RECEIVER, str(anchor_file))
        assert r.returncode == 0, f"temiz-çıpa RED: {r.stdout} {r.stderr}"
        assert "SAĞLAM" in r.stdout
    finally:
        led.close()


def test_75_k1_tamga_receiver_rejects_tampered_anchor(tmp_path):
    led, b = _bundle(tmp_path)
    try:
        anchor = json.loads(tamga_anchor_json(b, agent_label="ag-x"))
        anchor["event_count"] = int(anchor["event_count"]) + 1  # tek-sayı yalanı
        anchor_file = tmp_path / "cipa.jsonl"
        anchor_file.write_text(json.dumps(anchor, sort_keys=True,
                                          separators=(",", ":")) + "\n", encoding="utf-8")
        r = _run(K1_RECEIVER, str(anchor_file))
        assert r.returncode == 1, "bozuk-çıpa sessiz-geçti — fail-loud bozuk"
        assert "RED" in r.stdout
    finally:
        led.close()


def test_76_k1_receiver_selftest_standalone():
    r = _run(K1_RECEIVER, "--selftest")
    assert r.returncode == 0, f"K1 selftest: {r.stdout} {r.stderr}"
    assert "SAĞLAM" in r.stdout


# -------------------------------------------------------------- K3 · Veridict

def test_77_k3_veridict_receiver_accepts_clean_feed(tmp_path):
    led, b = _bundle(tmp_path)
    try:
        feed_file = tmp_path / "akis.jsonl"
        feed_file.write_text(watch_feed_jsonl(b, watcher_id="sester-ci") + "\n",
                             encoding="utf-8")
        r = _run(K3_RECEIVER, str(feed_file))
        assert r.returncode == 0, f"temiz-akış RED: {r.stdout} {r.stderr}"
        assert "SAĞLAM" in r.stdout
        assert "quota_exceeded/deny: 1" in r.stdout
        assert "replay/deny: 1" in r.stdout
    finally:
        led.close()


def test_78_k3_veridict_receiver_rejects_tampered_feed(tmp_path):
    led, b = _bundle(tmp_path)
    try:
        lines = watch_feed_jsonl(b, watcher_id="sester-ci").splitlines()
        obj = json.loads(lines[1])  # ilk watch_event: deny → allow kazıması
        obj["decision"] = "allow"
        lines[1] = json.dumps(obj, sort_keys=True, separators=(",", ":"))
        feed_file = tmp_path / "akis.jsonl"
        feed_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = _run(K3_RECEIVER, str(feed_file))
        assert r.returncode == 1, "kazınmış akış sessiz-geçti — fail-loud bozuk"
        assert "RED" in r.stdout
    finally:
        led.close()


def test_79_k3_receiver_selftest_standalone():
    r = _run(K3_RECEIVER, "--selftest")
    assert r.returncode == 0, f"K3 selftest: {r.stdout} {r.stderr}"
    assert "SAĞLAM" in r.stdout


# --------------------------------------------------- üretici tarafı (sester-ici)

def test_80_watchfeed_producer_deterministic(tmp_path):
    led, b = _bundle(tmp_path)
    try:
        a = watch_feed_jsonl(b, watcher_id="det")
        bb = dict(b)
        bb["events"] = list(b["events"])  # kopya-uzerinden tekrar uretim
        c = watch_feed_jsonl(bb, watcher_id="det")
        assert a == c, "üretici deterministik değil"
        kinds = [json.loads(l)["type"] for l in a.splitlines()]
        assert kinds[0] == "watch_manifest" and kinds[-1] == "watch_close"
    finally:
        led.close()


def test_81_claims_json_matches_veridict_claim_id_rule(tmp_path):
    """K2: claim_id = sha256(task_id|summary|verifiability)[:16] — alıcı-tarafı
    yeniden-hesaplama için format-kuralı testi (Veridict import'u YOK)."""
    led, b = _bundle(tmp_path)
    try:
        doc = json.loads(veridict_claims_json(b))
        import hashlib
        for c in doc["claims"]:
            expect = hashlib.sha256(
                f"{c['task_id']}|{c['summary']}|{c['verifiability']}".encode()
            ).hexdigest()[:16]
            assert c["claim_id"] == expect
            assert c["verifiability"] == "reproducible"
    finally:
        led.close()
