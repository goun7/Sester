"""PUGIO ledger — hash-chain'li SQLite usage kaydı (tamga-uyumlu olay şeması).

Her olay bir öncekinin hash'ine bağlı (prev_hash); zincir kırılması tespit
edilebilir (verify_chain). v0 HMAC-imza; tamga-protocol göçü olay-tipi şeması
korunarak yapılır (KARAR_63B §bilinçli-sınırlar).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL NOT NULL,
    event_type TEXT NOT NULL,          -- usage_event | charge_receipt | permission_decision | refund
    agent_id   TEXT NOT NULL,
    host       TEXT NOT NULL DEFAULT '',
    amount     REAL NOT NULL DEFAULT 0,
    payload    TEXT NOT NULL DEFAULT '{}',
    prev_hash  TEXT NOT NULL,
    hash       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_agent ON events(agent_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_type  ON events(event_type, ts);

-- v0.2: kalıcı nonce (replay-koruması restart'ı atlamaz)
CREATE TABLE IF NOT EXISTS seen_nonces (
    nonce_key TEXT PRIMARY KEY,
    ts        REAL NOT NULL
);
"""

GENESIS = "0" * 64


def canonical_line(ts: float, event_type: str, agent_id: str, host: str,
                   amount: float, payload: str, prev_hash: str) -> str:
    """K0-uyumlu canonical ön-görüntü — backend-bağımsız (SQLite/PG aynı zincir)."""
    return "|".join([
        f"{ts:.6f}", event_type, agent_id, host, f"{amount:.6f}", payload, prev_hash,
    ])


def seal(secret: bytes, canonical: str) -> str:
    """HMAC-mühür + sha256 — zincir-atomu; yalnız sahibi yazabilir."""
    mac = hmac.new(secret, canonical.encode(), hashlib.sha256).hexdigest()
    return hashlib.sha256((mac + canonical).encode()).hexdigest()


class Ledger:
    def __init__(self, db_path: str | os.PathLike[str] = "pugio.sqlite3", secret: str = "dev-secret"):
        self.db_path = str(db_path)
        self.secret = secret.encode()
        # check_same_thread=False: FastAPI/uvicorn threadpool'larından gelen append'ler
        # için gerekli; zincir-bütünlüğü _lock ile serileştirilir (test_27 kanıtı).
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.executescript(SCHEMA)

    # ---------- zincir-çekirdeği ----------

    def _canonical(self, ts: float, event_type: str, agent_id: str, host: str,
                   amount: float, payload: str, prev_hash: str) -> str:
        return canonical_line(ts, event_type, agent_id, host, amount, payload, prev_hash)

    def _seal(self, canonical: str) -> str:
        return seal(self.secret, canonical)

    def append(self, event_type: str, agent_id: str, host: str = "",
               amount: float = 0.0, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload_s = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
        with self._lock:  # prev_hash oku→yaz atomik: paralel append'te zincir kopmaz
            row = self.conn.execute(
                "SELECT hash FROM events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            prev_hash = row[0] if row else GENESIS
            ts = time.time()
            h = self._seal(self._canonical(ts, event_type, agent_id, host, amount, payload_s, prev_hash))
            cur = self.conn.execute(
                "INSERT INTO events (ts, event_type, agent_id, host, amount, payload, prev_hash, hash)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (ts, event_type, agent_id, host, amount, payload_s, prev_hash, h),
            )
        return {"seq": cur.lastrowid, "ts": ts, "hash": h, "prev_hash": prev_hash}

    def verify_chain(self) -> bool:
        rows = self.conn.execute(
            "SELECT seq, ts, event_type, agent_id, host, amount, payload, prev_hash, hash"
            " FROM events ORDER BY seq"
        ).fetchall()
        prev = GENESIS
        for (seq, ts, et, agent, host, amount, payload, prev_hash, h) in rows:
            if prev_hash != prev:
                return False
            expect = self._seal(self._canonical(ts, et, agent, host, amount, payload, prev_hash))
            if not hmac.compare_digest(expect, h):
                return False
            prev = h
        return True

    # ---------- sayaç / kota ----------

    def spent_today(self, agent_id: str, *, day: str | None = None) -> float:
        """Net harcama: charge_receipt pozitif, refund negatif (iade, harcamadan düşer)."""
        day = day or time.strftime("%Y-%m-%d")
        lo = time.mktime(time.strptime(day, "%Y-%m-%d"))
        hi = lo + 86400
        row = self.conn.execute(
            "SELECT COALESCE(SUM(CASE event_type WHEN 'charge_receipt' THEN amount"
            " WHEN 'refund' THEN -amount ELSE 0 END),0) FROM events"
            " WHERE agent_id=? AND event_type IN ('charge_receipt','refund') AND ts>=? AND ts<?",
            (agent_id, lo, hi),
        ).fetchone()
        return float(row[0])

    def count_today(self, agent_id: str) -> int:
        day = time.strftime("%Y-%m-%d")
        lo = time.mktime(time.strptime(day, "%Y-%m-%d"))
        row = self.conn.execute(
            "SELECT COUNT(*) FROM events"
            " WHERE agent_id=? AND event_type='charge_receipt' AND ts>=?",
            (agent_id, lo),
        ).fetchone()
        return int(row[0])

    # ---------- panel/rapor okumaları ----------

    def per_agent_summary(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT agent_id, COUNT(*), SUM(amount), MAX(ts) FROM events"
            " WHERE event_type='charge_receipt' GROUP BY agent_id ORDER BY MAX(ts) DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"agent_id": a, "calls": c, "spent": round(s or 0.0, 6), "last_ts": t}
            for (a, c, s, t) in rows
        ]

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT seq, ts, event_type, agent_id, host, amount, hash FROM events"
            " ORDER BY seq DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"seq": s, "ts": t, "event_type": et, "agent_id": a, "host": h,
             "amount": am, "hash": ha[:12] + "…"}
            for (s, t, et, a, h, am, ha) in rows
        ]

    def export_events(self, agent_id: str | None = None) -> list[dict[str, Any]]:
        """Tam-satır ihracı (kanıt-bundle'ı için): hash'ler tam uzunlukta."""
        if agent_id:
            rows = self.conn.execute(
                "SELECT seq, ts, event_type, agent_id, host, amount, payload,"
                " prev_hash, hash FROM events WHERE agent_id=? ORDER BY seq",
                (agent_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT seq, ts, event_type, agent_id, host, amount, payload,"
                " prev_hash, hash FROM events ORDER BY seq"
            ).fetchall()
        return [
            {"seq": s, "ts": t, "event_type": et, "agent_id": a, "host": h,
             "amount": am, "payload": p, "prev_hash": ph, "hash": ha}
            for (s, t, et, a, h, am, p, ph, ha) in rows
        ]

    def chain_head(self) -> str:
        row = self.conn.execute(
            "SELECT hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else GENESIS

    # ---------- kalıcı replay-koruması (v0.2) ----------

    def claim_nonce(self, agent_id: str, nonce: str) -> bool:
        """Atomik first-writer-wins: True = bu nonce ilk kez görüldü (kabul),
        False = tekrar (replay). Satır tabloda kalıcıdır — süreç-restart'ı
        replay-penceresini sıfırlamaz. Append-kilidi paylaşılır (tek-yazıcı).
        Not: 'kabul edilen' ödeme zincirde charge_receipt olarak zaten kanıtlıdır;
        ret-bilgisi permission_decision olaylarında yaşar."""
        with self._lock:
            try:
                self.conn.execute(
                    "INSERT INTO seen_nonces (nonce_key, ts) VALUES (?, ?)",
                    (f"{agent_id}|{nonce}", time.time()),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def nonce_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM seen_nonces").fetchone()
        return int(row[0])

    # ------------------------------------------------ migrasyon (hash-koruyan)

    def insert_event(self, ev: dict[str, Any]) -> None:
        """Mevcut bir olayı hash'leriyle aynen yazar (migrasyon/restore).
        Yeniden-mühürlemez — zincir olduğu gibi taşınır (verify_chain geçmeli)."""
        with self._lock:
            self.conn.execute(
                "INSERT INTO events (seq, ts, event_type, agent_id, host,"
                " amount, payload, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?)",
                (int(ev["seq"]), float(ev["ts"]), ev["event_type"],
                 ev["agent_id"], ev["host"], float(ev["amount"]),
                 ev["payload"], ev["prev_hash"], ev["hash"]),
            )

    def insert_nonce(self, agent_id: str, nonce: str, ts: float) -> None:
        """Claim'li nonce'u aynen yazar (replay-penceresi korunur)."""
        with self._lock:
            self.conn.execute(
                "INSERT OR IGNORE INTO seen_nonces (nonce_key, ts) VALUES (?, ?)",
                (f"{agent_id}|{nonce}", float(ts)),
            )

    def export_nonces(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT nonce_key, ts FROM seen_nonces ORDER BY ts").fetchall()
        return [{"nonce_key": k, "ts": t} for (k, t) in rows]

    def close(self) -> None:
        self.conn.close()
