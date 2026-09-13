"""PUGIO migrasyon testleri — SQLite→PG hash-koruyan replay (v0.3.1).

Kapsam: taşınan zincirin hash-dizisi birebir aynı, verify_chain hedefte
geçer, nonce-penceresi korunur (replay-hâlâ-yakalanır), tekrar-çalıştırma
idempotent, bozuk-kaynak ret edilir, plan/dry-run/verify modları.
"""

from __future__ import annotations

import pytest

from pugio.ledger import Ledger
from pugio.migrate_pg import main as migrate_main
from pugio.pg_ledger import PgLedger

S1 = "migrate-secret"

PG_DSN = __import__("os").environ.get("PUGIO_PG_DSN", "")


@pytest.fixture()
def sqlite_led(tmp_path):
    led = Ledger(tmp_path / "src.sqlite3", secret=S1)
    led.append("permission_decision", "ag-m", "/weather",
               payload={"decision": "deny", "rule_id": "quota_exceeded"})
    led.append("charge_receipt", "ag-m", "/weather", 0.05,
               payload={"nonce": "m1", "paid": 0.05, "scheme": "pugio0"})
    led.append("charge_receipt", "ag-m", "/weather", 0.10,
               payload={"nonce": "m2", "paid": 0.10, "scheme": "acp"})
    led.claim_nonce("ag-m", "m1")
    led.claim_nonce("ag-m", "m2")
    yield led, tmp_path / "src.sqlite3"
    led.close()


@pytest.fixture()
def pg_led():
    if not PG_DSN:
        pytest.skip("PUGIO_PG_DSN yok — PG-bacağı atlanır")
    led = PgLedger(secret=S1, dsn=PG_DSN)
    with led.conn().cursor() as cur:
        cur.execute("TRUNCATE events RESTART IDENTITY")
        cur.execute("TRUNCATE seen_nonces")
    led.conn().commit()
    yield led
    led.close()


def test_153_migration_preserves_chain_hashes(sqlite_led, pg_led):
    _, path = sqlite_led
    assert migrate_main(["--sqlite", str(path), "--secret", S1]) == 0
    src_hashes = [e["hash"] for e in Ledger(path, secret=S1).export_events(None)]
    dst_hashes = [e["hash"] for e in pg_led.export_events(None)]
    assert src_hashes == dst_hashes, "migrasyon hash'leri değiştirdi!"
    assert pg_led.verify_chain()


def test_154_nonce_window_survives_migration(sqlite_led, pg_led):
    _, path = sqlite_led
    migrate_main(["--sqlite", str(path), "--secret", S1])
    # taşınan nonce tekrar claim edilemez (replay-penceresi korunur)
    assert pg_led.claim_nonce("ag-m", "m1") is False
    assert pg_led.claim_nonce("ag-m", "m2") is False
    # taze nonce claim edilir
    assert pg_led.claim_nonce("ag-m", "m3") is True


def test_155_migration_is_idempotent(sqlite_led, pg_led):
    _, path = sqlite_led
    assert migrate_main(["--sqlite", str(path), "--secret", S1]) == 0
    # ikinci koşu: mevcut seq'ler atlanır — çift-kayıt yok
    assert migrate_main(["--sqlite", str(path), "--secret", S1]) == 0
    assert len(pg_led.export_events(None)) == 3


def test_156_verify_mode_reports_parity(sqlite_led, pg_led):
    _, path = sqlite_led
    migrate_main(["--sqlite", str(path), "--secret", S1])
    assert migrate_main(["--sqlite", str(path), "--secret", S1,
                         "--verify"]) == 0


def test_157_plan_and_dry_run_modes(sqlite_led):
    led, path = sqlite_led
    assert migrate_main(["--sqlite", str(path), "--secret", S1,
                         "--plan"]) == 0
    assert migrate_main(["--sqlite", str(path), "--secret", S1,
                         "--dry-run"]) == 0
    # dry-run yazmadı
    assert led.nonce_count() == 2


def test_158_corrupt_source_refused(sqlite_led):
    _, path = sqlite_led
    # kaynak zincirini boz (sqlite-doğrudan): amount kazı
    led = Ledger(path, secret=S1)
    led.conn.execute("UPDATE events SET amount=0.01 WHERE seq=2")
    led.conn.commit()
    led.close()
    assert migrate_main(["--sqlite", str(path), "--secret", S1]) == 1
