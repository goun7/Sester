"""SESTER backend-parite testleri — SQLite-Ledger ↔ PgLedger.

Aynı davranış-senaryoları her iki backend'de koşar; özdeş sonuçlar şart:
aynı zincir-hash'leri, sayaçlar, nonce-claim'leri, kanıt-bundle'ı ve
harici-dogrulayıcı kararı. PG yoksa (Docker/dsn) PG-bacakları atlanır —
SQLite-bacağı her zaman koşar (regresyon-kalkanı).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from sester.evidence import produce_bundle, verify_bundle
from sester.ledger import Ledger
from sester.pg_ledger import PgLedger

PG_DSN = os.environ.get("SESTER_PG_DSN", "")
PG_AVAILABLE = bool(PG_DSN)

S1 = "parity-secret"


# ---------------------------------------------------------------- senaryolar

def _scenario(led):
    """Ortak davranış-senaryosu: append/refund/kota/replay/karar."""
    led.append("permission_decision", "ag-p", "/weather",
               payload={"decision": "deny", "rule_id": "quota_exceeded"})
    led.append("charge_receipt", "ag-p", "/weather", 0.05,
               payload={"nonce": "n1", "paid": 0.05, "scheme": "pugio0"})
    led.append("charge_receipt", "ag-p", "/weather", 0.10,
               payload={"nonce": "n2", "paid": 0.10, "scheme": "ap2"})
    led.append("refund", "ag-p", "/weather", 0.05, payload={"why": "sla"})
    led.append("permission_decision", "ag-p", "/weather",
               payload={"decision": "deny", "rule_id": "replay"})
    assert led.claim_nonce("ag-p", "n1") is True
    assert led.claim_nonce("ag-p", "n1") is False


# ---------------------------------------------------------------- fixtures

@pytest.fixture()
def sqlite_led(tmp_path):
    led = Ledger(tmp_path / "p.sqlite3", secret=S1)
    yield led
    led.close()


@pytest.fixture()
def pg_led():
    if not PG_AVAILABLE:
        pytest.skip("SESTER_PG_DSN yok — PG-bacağı atlanır")
    led = PgLedger(secret=S1, dsn=PG_DSN)
    # PG kalıcıdır (restart'lar-arası): parite seq-alignment için temiz-başlangıç
    with led.conn().cursor() as cur:
        cur.execute("TRUNCATE events RESTART IDENTITY")
        cur.execute("TRUNCATE seen_nonces")
    led.conn().commit()
    yield led
    led.close()


# ---------------------------------------------------------------- parite

def _freeze_time(monkeypatch):
    """Zincir-paritesi için deterministik saat: canonical satır ts içerir — iki
    backend farklı gerçek-anlarda yazarsa hash'ler *haklı olarak* farklıdır.
    Aynı zaman-dizisini verince aynı secret+olaylar → özdez zincir.
    Döndürdüğü reset() sayaç sıfırlar — her iki senaryo aynı ts-dizisini alır
    (gerçek-şimdi tabanlı: spent_today/count_today bugün-sınırları da çalışır)."""
    import time as _time_mod

    base = {"t": _time_mod.time()}
    state = {"n": 0}

    def fake():
        state["n"] += 1
        return base["t"] + state["n"] * 0.001

    def reset():
        state["n"] = 0

    monkeypatch.setattr(_time_mod, "time", fake)
    return reset


def test_141_identical_chain_hashes(sqlite_led, pg_led, monkeypatch):
    """Aynı secret + aynı olaylar (ts dizisi dahil) → özdez zincir."""
    reset = _freeze_time(monkeypatch)
    reset(); _scenario(sqlite_led)
    reset(); _scenario(pg_led)
    a = [e["hash"] for e in sqlite_led.export_events()]
    b = [e["hash"] for e in pg_led.export_events()]
    assert a == b, "aynı secret+olaylar farklı zincir üretti"
    assert sqlite_led.verify_chain() and pg_led.verify_chain()


def test_142_parity_spent_and_count(sqlite_led, pg_led, monkeypatch):
    reset = _freeze_time(monkeypatch)
    reset(); _scenario(sqlite_led)
    reset(); _scenario(pg_led)
    assert abs(sqlite_led.spent_today("ag-p") - 0.10) < 1e-9
    assert abs(pg_led.spent_today("ag-p") - 0.10) < 1e-9
    assert sqlite_led.count_today("ag-p") == pg_led.count_today("ag-p") == 2
    assert sqlite_led.nonce_count() == pg_led.nonce_count() == 1


def test_143_parity_bundle_and_external_verifier(sqlite_led, pg_led, tmp_path,
                                                 monkeypatch):
    reset = _freeze_time(monkeypatch)
    reset(); _scenario(sqlite_led)
    reset(); _scenario(pg_led)
    ba = produce_bundle(sqlite_led, agent_id="ag-p")
    bb = produce_bundle(pg_led, agent_id="ag-p")
    # kanıt-bundle'ları backend'den bağımsız özdeş (seq dahil — temiz PG)
    assert ba["head"] == bb["head"] and ba["merkle_root"] == bb["merkle_root"]
    assert verify_bundle(ba)[0] and verify_bundle(bb)[0]
    # harici-dogrulayıcı (pür-stdlib) PG-bundle'ını da SAĞLAM der
    path = tmp_path / "pg-bundle.json"
    path.write_text(json.dumps(bb, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8")
    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "dogrula.py")
    r = subprocess.run([sys.executable, script, str(path)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "SAĞLAM" in r.stdout


def test_144_parity_pane_reads(sqlite_led, pg_led, monkeypatch):
    reset = _freeze_time(monkeypatch)
    reset(); _scenario(sqlite_led)
    reset(); _scenario(pg_led)
    sa, sb = sqlite_led.per_agent_summary(), pg_led.per_agent_summary()
    assert sa == sb
    ra, rb = sqlite_led.recent_events(5), pg_led.recent_events(5)
    assert [(r["seq"], r["event_type"], r["agent_id"]) for r in ra] \
        == [(r["seq"], r["event_type"], r["agent_id"]) for r in rb]


def test_145_pg_requires_dsn(monkeypatch):
    monkeypatch.delenv("SESTER_PG_DSN", raising=False)
    with pytest.raises(RuntimeError, match="SESTER_PG_DSN"):
        PgLedger(secret=S1)


# ---------------------------------------------------------------- docker yardımcı

def _pg_container_up() -> str | None:
    """Ephemeral PG kaldırıp DSN üretir; başarısızsa None."""
    import subprocess as sp

    name = "sester-pg-parity"
    sp.run(["docker", "rm", "-f", name], capture_output=True)
    r = sp.run(["docker", "run", "-d", "--name", name, "-e",
                "POSTGRES_PASSWORD=sester", "-p", "5499:5432", "postgres:16-alpine"],
               capture_output=True, text=True)
    if r.returncode != 0:
        return None
    import time

    dsn = "host=127.0.0.1 port=5499 dbname=postgres user=postgres password=sester"
    for _ in range(30):
        try:
            probe = PgLedger(secret="probe", dsn=dsn)
            probe.conn()
            probe.close()
            return dsn
        except Exception:
            time.sleep(1)
    return None


if __name__ == "__main__":
    dsn = _pg_container_up()
    print("PG DSN:" if dsn else "PG yok", dsn or "")
    if dsn:
        os.environ["SESTER_PG_DSN"] = dsn
        sys.exit(pytest.main([__file__, "-q"]))
