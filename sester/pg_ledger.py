"""SESTER pg_ledger — Postgres backend (v0.3): SQLite-Ledger ile birebir arayüz.

Aynı hash-chain çekirdeği (sester.ledger.canonical_line + seal) — zincir,
backend-değişiminden etkilenmez: SQLite'ta başlayan zincir PG'ye olay-olay
taşınabilir (aynı secret → aynı hash'ler). Arayüz sözleşmesi (parity-set):
  append · verify_chain · spent_today · count_today · per_agent_summary ·
  recent_events · export_events · chain_head · claim_nonce · nonce_count ·
  close

Farklar (bilinçli):
  · BIGSERIAL seq, DOUBLE PRECISION ts/amount; payload TEXT (compact-JSON)
  · claim_nonce: INSERT … ON CONFLICT DO NOTHING → rowcount (atomik, tek SQL)
  · bağlantı: SESTER_PG_DSN env ya da dsn argümanı (lazy — ilk sorguda bağlanır)
Sürücü: psycopg (v3) — `pip install "sester[pg]"`. psycopg2 fallback.

v0.4: amount_minor yardımcı-kolonu — SQLite-Ledger ile birebir (dual-read,
tek-yaz; canonical_line donmuş, kolon hash'e girmez). Kolon conn() içinde
information_schema-korumalı idempotent-eklenir.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

from .ledger import GENESIS, MINOR, canonical_line, seal

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq        BIGSERIAL PRIMARY KEY,
    ts         DOUBLE PRECISION NOT NULL,
    event_type TEXT NOT NULL,
    agent_id   TEXT NOT NULL,
    host       TEXT NOT NULL DEFAULT '',
    amount     DOUBLE PRECISION NOT NULL DEFAULT 0,
    payload    TEXT NOT NULL DEFAULT '{}',
    prev_hash  TEXT NOT NULL,
    hash       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_agent ON events(agent_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_type  ON events(event_type, ts);
CREATE TABLE IF NOT EXISTS seen_nonces (
    nonce_key TEXT PRIMARY KEY,
    ts        DOUBLE PRECISION NOT NULL
);
"""


def _connect(dsn: str):
    try:
        import psycopg

        return psycopg.connect(dsn)
    except ImportError:
        try:
            import psycopg2

            return psycopg2.connect(dsn)
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "Postgres backend için psycopg gerekir: "
                "pip install 'sester[pg]'") from e


class PgLedger:
    """Ledger-arayüzünün Postgres karşılığı — parity-set ile sınanır."""

    def __init__(self, db_path: str | os.PathLike[str] | None = None, *,
                 secret: str = "dev-secret", dsn: str | None = None):
        # db_path kabul edilir (Ledger-parite) ama DSN asıl kaynaktır
        self.secret = secret.encode()
        self.dsn = dsn or os.environ.get("SESTER_PG_DSN")
        if not self.dsn:
            raise RuntimeError("SESTER_PG_DSN yok: dsn argümanı ya da env şart")
        self._lock = threading.Lock()
        self._conn = None

    # ------------------------------------------------ bağlantı (lazy)

    def conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = _connect(self.dsn)
            with self._conn.cursor() as cur:
                cur.execute(SCHEMA)
                # v0.4: yardımcı-kolon idempotent-ekle (mevcut DB'lerde bir kez)
                cur.execute("SELECT column_name FROM information_schema.columns"
                            " WHERE table_name='events'")
                cols = {r[0] for r in cur.fetchall()}
                if "amount_minor" not in cols:
                    cur.execute("ALTER TABLE events ADD COLUMN amount_minor INTEGER")
            self._conn.commit()
        return self._conn

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()

    # ------------------------------------------------ zincir-çekirdeği

    def append(self, event_type: str, agent_id: str, host: str = "",
               amount: float = 0.0,
               payload: dict[str, Any] | None = None,
               amount_minor: int | None = None) -> dict[str, Any]:
        payload_s = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
        if amount_minor is None:
            amount_minor = int(round(float(amount) * MINOR))  # geri-uyum türetim
        with self._lock:  # prev_hash oku→yaz atomik (SQLite-Ledger disiplini)
            conn = self.conn()
            with conn.cursor() as cur:
                cur.execute("SELECT hash FROM events ORDER BY seq DESC LIMIT 1")
                row = cur.fetchone()
                prev_hash = row[0] if row else GENESIS
                ts = time.time()
                h = seal(self.secret, canonical_line(
                    ts, event_type, agent_id, host, amount, payload_s, prev_hash))
                cur.execute(
                    "INSERT INTO events (ts, event_type, agent_id, host, amount,"
                    " payload, prev_hash, hash, amount_minor)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING seq",
                    (ts, event_type, agent_id, host, amount, payload_s,
                     prev_hash, h, int(amount_minor)),
                )
                seq = cur.fetchone()[0]
            conn.commit()
        return {"seq": seq, "ts": ts, "hash": h, "prev_hash": prev_hash}

    def verify_chain(self) -> bool:
        with self.conn().cursor() as cur:
            cur.execute(
                "SELECT seq, ts, event_type, agent_id, host, amount, payload,"
                " prev_hash, hash FROM events ORDER BY seq")
            rows = cur.fetchall()
        prev = GENESIS
        for (_, ts, et, agent, host, amount, payload, prev_hash, h) in rows:
            if prev_hash != prev:
                return False
            expect = seal(self.secret, canonical_line(
                ts, et, agent, host, amount, payload, prev_hash))
            import hmac as _hmac

            if not _hmac.compare_digest(expect, h):
                return False
            prev = h
        return True

    # ------------------------------------------------ sayaç / kota

    def spent_today(self, agent_id: str, *, day: str | None = None) -> float:
        day = day or time.strftime("%Y-%m-%d")
        lo = time.mktime(time.strptime(day, "%Y-%m-%d"))
        hi = lo + 86400
        with self.conn().cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(CASE event_type WHEN 'charge_receipt'"
                " THEN amount WHEN 'refund' THEN -amount ELSE 0 END),0)"
                " FROM events WHERE agent_id=%s AND event_type IN"
                " ('charge_receipt','refund') AND ts>=%s AND ts<%s",
                (agent_id, lo, hi))
            return float(cur.fetchone()[0])

    def spent_today_minor(self, agent_id: str, *, day: str | None = None) -> int:
        """v0.4 tam-sayı sayaç — SQLite-Ledger ile birebir (dual-read)."""
        day = day or time.strftime("%Y-%m-%d")
        lo = time.mktime(time.strptime(day, "%Y-%m-%d"))
        hi = lo + 86400
        with self.conn().cursor() as cur:
            cur.execute(
                "SELECT event_type, amount, amount_minor FROM events"
                " WHERE agent_id=%s AND event_type IN"
                " ('charge_receipt','refund') AND ts>=%s AND ts<%s",
                (agent_id, lo, hi))
            rows = cur.fetchall()
        total = 0
        for et, am, am_minor in rows:
            v = int(am_minor) if am_minor is not None else int(round(float(am) * MINOR))
            total += v if et == "charge_receipt" else -v
        return total

    def count_today(self, agent_id: str) -> int:
        day = time.strftime("%Y-%m-%d")
        lo = time.mktime(time.strptime(day, "%Y-%m-%d"))
        with self.conn().cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM events WHERE agent_id=%s AND"
                " event_type='charge_receipt' AND ts>=%s",
                (agent_id, lo))
            return int(cur.fetchone()[0])

    # ------------------------------------------------ panel/rapor okumaları

    def per_agent_summary(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.conn().cursor() as cur:
            cur.execute(
                "SELECT agent_id, COUNT(*), SUM(amount), MAX(ts) FROM events"
                " WHERE event_type='charge_receipt' GROUP BY agent_id"
                " ORDER BY MAX(ts) DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [{"agent_id": a, "calls": c, "spent": round(s or 0.0, 6),
                 "last_ts": t} for (a, c, s, t) in rows]

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.conn().cursor() as cur:
            cur.execute(
                "SELECT seq, ts, event_type, agent_id, host, amount, hash"
                " FROM events ORDER BY seq DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [{"seq": s, "ts": t, "event_type": et, "agent_id": a,
                 "host": h, "amount": am, "hash": ha[:12] + "…"}
                for (s, t, et, a, h, am, ha) in rows]

    def export_events(self, agent_id: str | None = None) -> list[dict[str, Any]]:
        sql = ("SELECT seq, ts, event_type, agent_id, host, amount, payload,"
               " prev_hash, hash, amount_minor FROM events")
        params: tuple = ()
        if agent_id:
            sql += " WHERE agent_id=%s"
            params = (agent_id,)
        sql += " ORDER BY seq"
        with self.conn().cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [{"seq": s, "ts": t, "event_type": et, "agent_id": a,
                 "host": h, "amount": am, "payload": p, "prev_hash": ph,
                 "hash": ha, "amount_minor": amn}
                for (s, t, et, a, h, am, p, ph, ha, amn) in rows]

    def backfill_amount_minor(self) -> int:
        """v0.4 backfill — SQLite-Ledger ile birebir (idempotent, hash-koruyan)."""
        with self._lock:
            conn = self.conn()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE events SET amount_minor = ROUND(amount * %s)::BIGINT"
                    " WHERE amount_minor IS NULL",
                    (MINOR,),
                )
                n = cur.rowcount
            conn.commit()
        return n

    def chain_head(self) -> str:
        with self.conn().cursor() as cur:
            cur.execute("SELECT hash FROM events ORDER BY seq DESC LIMIT 1")
            row = cur.fetchone()
            return row[0] if row else GENESIS

    # ------------------------------------------------ kalıcı replay-koruması

    def claim_nonce(self, agent_id: str, nonce: str) -> bool:
        with self._lock:
            with self.conn().cursor() as cur:
                cur.execute(
                    "INSERT INTO seen_nonces (nonce_key, ts) VALUES (%s, %s)"
                    " ON CONFLICT (nonce_key) DO NOTHING",
                    (f"{agent_id}|{nonce}", time.time()))
                inserted = cur.rowcount == 1
            self.conn().commit()
            return inserted

    def nonce_count(self) -> int:
        with self.conn().cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM seen_nonces")
            return int(cur.fetchone()[0])

    # ------------------------------------------------ migrasyon (hash-koruyan)

    def insert_event(self, ev: dict[str, Any]) -> None:
        """Mevcut bir olayı hash'leriyle aynen yazar (migrasyon/restore)."""
        with self._lock:
            with self.conn().cursor() as cur:
                cur.execute(
                    "INSERT INTO events (seq, ts, event_type, agent_id, host,"
                    " amount, payload, prev_hash, hash, amount_minor) VALUES"
                    " (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (int(ev["seq"]), float(ev["ts"]), ev["event_type"],
                     ev["agent_id"], ev["host"], float(ev["amount"]),
                     ev["payload"], ev["prev_hash"], ev["hash"],
                     ev.get("amount_minor")),
                )
            self.conn().commit()

    def insert_nonce(self, agent_id: str, nonce: str, ts: float) -> None:
        """Claim'li nonce'u aynen yazar (replay-penceresi korunur)."""
        with self._lock:
            with self.conn().cursor() as cur:
                cur.execute(
                    "INSERT INTO seen_nonces (nonce_key, ts) VALUES (%s, %s)"
                    " ON CONFLICT (nonce_key) DO NOTHING",
                    (f"{agent_id}|{nonce}", float(ts)),
                )
            self.conn().commit()

    def export_nonces(self) -> list[dict[str, Any]]:
        with self.conn().cursor() as cur:
            cur.execute("SELECT nonce_key, ts FROM seen_nonces ORDER BY ts")
            rows = cur.fetchall()
        return [{"nonce_key": k, "ts": t} for (k, t) in rows]
