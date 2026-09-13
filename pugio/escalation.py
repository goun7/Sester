"""PUGIO escalation — KARAR_63B madde-3: insan-onaylı harcama kuyruğu.

KURAL_DSL_V0 `then: escalate` kararı artık "engelle+log" değil:
  park     → istek 402 `escalation_required` ile durur, bilet açılır
             (aynı ajan+kaynak için pending bilet varsa YENİSİ AÇILMAZ —
             tek-bilet disiplini, spam-koruması)
  approve  → insan (CLI/endpoint) biletinizi onaylar; SONRAKİ uyumlu istek
             bileti bir-kezlik tüketir (consume) ve normal ödeme-akışına girer
  deny     → bilet reddedilir; istekler policy_denied olarak devam eder
  expire   → biletin TTL'i (varsayılan 15 dk) dolarsa otomatik-RED
             (fail-closed: sessiz onay yok)

Durum makinesi: pending → approved → consumed (tek-kezlik) veya
pending → denied | expired (tek-yönlü). Kanıt: her geçiş PUGIO ledger'ına
ayrı olay-tipiyle yazılır (escalation_parked / escalation_approved /
escalation_denied) — hash-chain'e girer, tamga/Veridict köprülerinde görünür.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from typing import Any

PENDING, APPROVED, DENIED, EXPIRED = "pending", "approved", "denied", "expired"

SCHEMA = """
CREATE TABLE IF NOT EXISTS escalations (
    esc_id     TEXT PRIMARY KEY,
    agent      TEXT NOT NULL,
    resource   TEXT NOT NULL,
    amount     REAL NOT NULL DEFAULT 0,
    rule_id    TEXT NOT NULL DEFAULT '',
    reason     TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    decided_at REAL,
    decided_by TEXT,
    note       TEXT
);
CREATE INDEX IF NOT EXISTS idx_esc_agent_res ON escalations(agent, resource, status);
"""


class EscalationQueue:
    """İnsan-onay kuyruğu — kendi SQLite dosyası, append-lock'lu, fail-closed."""

    def __init__(self, db_path: str | Any, *, ledger: Any | None = None,
                 ttl_seconds: float = 900.0) -> None:
        self.db_path = str(db_path)
        self.ledger = ledger        # kanıt-olayları için (opsiyonel)
        self.ttl = float(ttl_seconds)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # ledger ile aynı disiplin: WAL (okuyucu-yazıcı çakışması) + busy_timeout
        # (çok-thread'li sunucularda SQLITE_BUSY yerine kısa bekleme)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------- yardımcılar

    def _expire(self) -> None:
        """TTL'i dolan pending'leri otomatik-RED'e çevir (fail-closed)."""
        n = self._conn.execute(
            "UPDATE escalations SET status='expired', decided_at=? "
            "WHERE status='pending' AND expires_at < ?",
            (time.time(), time.time()),
        ).rowcount
        if n:
            self._conn.commit()

    @staticmethod
    def _row(r: sqlite3.Row) -> dict[str, Any]:
        return dict(r)

    # --------------------------------------------------------------- akış-API

    def park(self, agent: str, resource: str, amount: float, rule_id: str,
             reason: str = "") -> dict[str, Any]:
        """İstek-bileti aç; aynı (agent, resource) pending varsa onu döndür."""
        now = time.time()
        with self._lock:
            self._expire()
            row = self._conn.execute(
                "SELECT * FROM escalations WHERE agent=? AND resource=? "
                "AND status='pending' ORDER BY created_at DESC LIMIT 1",
                (agent, resource),
            ).fetchone()
            if row:
                return self._row(row)
            esc_id = f"esc-{uuid.uuid4().hex[:12]}"
            ticket = {
                "esc_id": esc_id, "agent": agent, "resource": resource,
                "amount": float(amount), "rule_id": rule_id, "reason": reason,
                "status": PENDING, "created_at": now,
                "expires_at": now + self.ttl,
                "decided_at": None, "decided_by": None, "note": None,
            }
            self._conn.execute(
                "INSERT INTO escalations (esc_id, agent, resource, amount, "
                "rule_id, reason, status, created_at, expires_at) "
                "VALUES (:esc_id,:agent,:resource,:amount,:rule_id,:reason,"
                ":status,:created_at,:expires_at)",
                ticket,
            )
            self._conn.commit()
        if self.ledger:
            self.ledger.append("escalation_parked", agent, resource, 0.0,
                               payload={"esc_id": esc_id, "rule_id": rule_id,
                                        "amount": float(amount)})
        return ticket

    def pending(self) -> list[dict[str, Any]]:
        with self._lock:
            self._expire()
            rows = self._conn.execute(
                "SELECT * FROM escalations WHERE status='pending' "
                "ORDER BY created_at").fetchall()
            return [self._row(r) for r in rows]

    def get(self, esc_id: str) -> dict[str, Any] | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM escalations WHERE esc_id=?", (esc_id,)).fetchone()
            return self._row(r) if r else None

    def decide(self, esc_id: str, approve: bool, by: str, note: str = ""
               ) -> dict[str, Any]:
        """Tek-yönlü karar: pending → approved/denied. Bozuk-geçiş hata."""
        now = time.time()
        with self._lock:
            self._expire()
            row = self._conn.execute(
                "SELECT * FROM escalations WHERE esc_id=?", (esc_id,)).fetchone()
            if row is None:
                raise KeyError(f"bilet yok: {esc_id}")
            if row["status"] != PENDING:
                raise ValueError(f"bilet {row['status']} — karar verilemez")
            status = APPROVED if approve else DENIED
            self._conn.execute(
                "UPDATE escalations SET status=?, decided_at=?, decided_by=?, "
                "note=? WHERE esc_id=?",
                (status, now, by, note, esc_id),
            )
            self._conn.commit()
            out = self._row(self._conn.execute(
                "SELECT * FROM escalations WHERE esc_id=?", (esc_id,)).fetchone())
        if self.ledger:
            self.ledger.append(f"escalation_{status}", out["agent"],
                               out["resource"], 0.0,
                               payload={"esc_id": esc_id, "by": by, "note": note})
        return out

    def consume(self, esc_id: str) -> bool:
        """Onaylı bileti bir-kezlik tüket (atomik). True = tüketildi."""
        with self._lock:
            self._expire()
            cur = self._conn.execute(
                "UPDATE escalations SET status='consumed' "
                "WHERE esc_id=? AND status='approved'", (esc_id,))
            self._conn.commit()
            return cur.rowcount == 1

    def approved_for(self, agent: str, resource: str) -> dict[str, Any] | None:
        """(agent, resource) çifti için tüketilebilir onaylı bilet — en-eski."""
        with self._lock:
            self._expire()
            row = self._conn.execute(
                "SELECT * FROM escalations WHERE agent=? AND resource=? AND "
                "status='approved' ORDER BY decided_at LIMIT 1",
                (agent, resource),
            ).fetchone()
            return self._row(row) if row else None


def main(argv: list[str]) -> int:
    """CLI: python -m pugio.escalation pending|approve <id>|deny <id> [--by X]"""
    import os

    db = os.environ.get("PUGIO_ESCALATION_DB", "pugio-escalation.sqlite3")
    q = EscalationQueue(db)
    if not argv:
        print("kullanım: pending | approve <esc_id> [--by kim] [--note ...] "
              "| deny <esc_id> [--by kim]")
        return 2
    cmd = argv[0]
    if cmd == "pending":
        rows = q.pending()
        if not rows:
            print("(kuyruk boş — bekleyen onay yok)")
        for r in rows:
            left = max(0, int(r["expires_at"] - time.time()))
            print(f"{r['esc_id']}  {r['agent']}  {r['resource']}  "
                  f"{r['amount']:.2f}  kalan {left}s")
        return 0
    if cmd in ("approve", "deny") and len(argv) >= 2:
        by, note = "cli", ""
        if "--by" in argv:
            by = argv[argv.index("--by") + 1]
        if "--note" in argv:
            note = argv[argv.index("--note") + 1]
        try:
            t = q.decide(argv[1], approve=(cmd == "approve"), by=by, note=note)
        except (KeyError, ValueError) as e:
            print(f"HATA: {e}")
            return 1
        print(f"{t['esc_id']} → {t['status']} (by {t['decided_by']})")
        return 0
    print("kullanım: pending | approve <esc_id> | deny <esc_id>")
    return 2


if __name__ == "__main__":
    import sys as _sys

    raise SystemExit(main(_sys.argv[1:]))
