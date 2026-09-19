"""SESTER ledger — hash-chain'li SQLite usage kaydı (tamga-uyumlu olay şeması).

Her olay bir öncekinin hash'ine bağlı (prev_hash); zincir kırılması tespit
edilebilir (verify_chain). v0 HMAC-imza; tamga-protocol göçü olay-tipi şeması
korunarak yapılır (architecture decision record §bilinçli-sınırlar).

v0.4: amount_minor yardımcı-kolonu (tam-sayı sayaç). K0 kuralı korunur:
canonical_line donmuştur — kolon hash'e girmez; eski-kayıtlar NULL kalır ve
spent_today_minor major-değerden türetir (dual-read, tek-yaz).
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
    event_type TEXT NOT NULL,          -- ERRATUM-K0.2: taksonomi = ledger.EVENT_TYPES
    -- usage_event | charge_receipt | refund | permission_decision | policy_denied
    -- settlement | protocol_intent | webhook_delivery | escalation_parked |
    -- escalation_approved | escalation_denied | escalation_consumed |
    -- facilitator_{verify,settle,metering,refund,batch} — bilinmeyen tip
    -- append()'te RED (fail-closed)
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

-- v0.4: tam-sayı küçük-birim kolonu (yardımcı; NULL = eski-kayıt).
-- K0 notu: canonical_line DONMUŞTUR — bu kolon zincir-hash'lerine girmez;
-- mevcut zincirler hash-koruyan migrasyonla taşınmaya devam eder.
-- ALTER'da idempotent-değil; kolon Ledger.__init__'te PRAGMA-korumalı eklenir.
"""

GENESIS = "0" * 64

MINOR = 1_000_000  # USDC 6-dec — v0.4: tam-sayı sayaç-kolonu (middleware bundan yönlendirilir)

# Olay-tipi taksonomisi — ERRATUM-K0.2 (docs/K0_SHARED_ENVELOPE_SPEC.md §1).
# events tablosuna yazılabilen tek küme; zarf (bundle) bu tipleri taşır ve
# bağımsız doğrulayıcılar event_type'ı anlamsal olarak yorumluyorsa bu kümeyi
# bilmek zorundadır. SCHEMA yorumu ile BİREBİTİR (test_208 ile senkron-kilit).
#
# DÜZELTME (2026-09-19): ilk enumerasyon EKSİKTİ — escalation_consumed,
# protocol_intent, policy_denied, webhook_delivery ve facilitator_* ailesi
# (batch dahil) atlanmıştı. append() artık bilinmeyen tipi REDDEDiyor
# (fail-closed); bu listede bir eksiklik varsa kendi test takımımız kırılır —
# tükenmezlik sözle değil suite ile kanıtlanır (test_208 + tüm suite).
EVENT_TYPES = frozenset({
    "usage_event",           # ölçüm: çağrı-başına ücretlendirme
    "charge_receipt",        # harcama (+) — spent_today'e pozitif girer
    "refund",                # iade (−) — spent_today'den negatif düşer
    "permission_decision",   # K0 §6 watch-feed yalnızca bu tipi taşır
    "policy_denied",         # red kararı (fleet-lane üretim şablonu)
    "escalation_parked",     # insan-onay: bilet açıldı (istek 402'de park)
    "escalation_approved",   # onaylandı
    "escalation_denied",     # reddedildi
    "escalation_consumed",   # onay-biletinin tek-seferlik tüketimi (demo_api)
    "protocol_intent",       # adapter sözleşmesi: ChargeIntent → zarf (adapters)
    "settlement",            # on-chain batch ayağı (sester/settlement.py)
    "webhook_delivery",      # çağıran disiplini: başarısız tesimat ledger'a düşer
})

# Dinamik ön-ek aileleri: "{ön-ek}{kind}" biçiminde üretilir; kind kümesi kapalı.
# Bağımsız doğrulayıcı ön-eke bakarak aileyi tanır, kind'ı ise kümeden doğrular.
EVENT_TYPE_FAMILIES: dict[str, frozenset[str]] = {
    "facilitator_": frozenset(
        {"verify", "settle", "metering", "refund", "batch"}),
}


def is_known_event_type(event_type: str) -> bool:
    """ERRATUM-K0.2 üyelik-testi — statik küme veya kapalı kind'lı aile."""
    if event_type in EVENT_TYPES:
        return True
    for prefix, kinds in EVENT_TYPE_FAMILIES.items():
        if event_type.startswith(prefix):
            return event_type[len(prefix):] in kinds
    return False


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
    def __init__(self, db_path: str | os.PathLike[str] = "sester.sqlite3", secret: str = "dev-secret"):
        self.db_path = str(db_path)
        self.secret = secret.encode()
        # check_same_thread=False: FastAPI/uvicorn threadpool'larından gelen append'ler
        # için gerekli; zincir-bütünlüğü _lock ile serileştirilir (test_27 kanıtı).
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.executescript(SCHEMA)
        # v0.4: yardımcı-kolon idempotent-ekle (mevcut DB'lerde bir kez)
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(events)")}
        if "amount_minor" not in cols:
            self.conn.execute("ALTER TABLE events ADD COLUMN amount_minor INTEGER")

    # ---------- zincir-çekirdeği ----------

    def _canonical(self, ts: float, event_type: str, agent_id: str, host: str,
                   amount: float, payload: str, prev_hash: str) -> str:
        return canonical_line(ts, event_type, agent_id, host, amount, payload, prev_hash)

    def _seal(self, canonical: str) -> str:
        return seal(self.secret, canonical)

    def append(self, event_type: str, agent_id: str, host: str = "",
               amount: float = 0.0, payload: dict[str, Any] | None = None,
               amount_minor: int | None = None) -> dict[str, Any]:
        # ERRATUM-K0.2 (fail-closed): bilinmeyen event_type YAZILMAMALI —
        # taksonomi dışı değer bağımsız doğrulayıcıları sessiz ayrıştırır.
        # Eğer bu satır bir production yolunu kırıyorsa, taksonomi eksiktir:
        # EVENT_TYPES'ı güncelle, K0 §1'i güncelle, test_208'i koş.
        if not is_known_event_type(event_type):
            raise ValueError(
                f"bilinmeyen event_type: {event_type!r} — ERRATUM-K0.2 "
                "taksonomisi dışı (Ledger.EVENT_TYPES / EVENT_TYPE_FAMILIES); "
                "yeni tip eklemek önce taksonomi + K0 §1 güncellemini gerektirir"
            )
        payload_s = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
        if amount_minor is None:
            # geri-uyum: major-unit'ten türet (0.0 → 0; major-kayan nokta uçları
            # ancak çağıran tam-sayıyı bilirse birebir — middleware v0.4'te öyle)
            amount_minor = int(round(float(amount) * MINOR))
        with self._lock:  # prev_hash oku→yaz atomik: paralel append'te zincir kopmaz
            row = self.conn.execute(
                "SELECT hash FROM events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            prev_hash = row[0] if row else GENESIS
            ts = time.time()
            h = self._seal(self._canonical(ts, event_type, agent_id, host, amount, payload_s, prev_hash))
            cur = self.conn.execute(
                "INSERT INTO events (ts, event_type, agent_id, host, amount,"
                " payload, prev_hash, hash, amount_minor) VALUES (?,?,?,?,?,?,?,?,?)",
                (ts, event_type, agent_id, host, amount, payload_s, prev_hash, h,
                 int(amount_minor)),
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

    def spent_today_minor(self, agent_id: str, *, day: str | None = None) -> int:
        """v0.4 tam-sayı sayaç: amount_minor kolonundan; eski-kayıtlar (NULL)
        major-değerden türetilir. charge_receipt pozitif, refund negatif.
        round-akümülasyonu YOK — tam-sayı okuma, tam-sayı kota-kararı."""
        day = day or time.strftime("%Y-%m-%d")
        lo = time.mktime(time.strptime(day, "%Y-%m-%d"))
        hi = lo + 86400
        rows = self.conn.execute(
            "SELECT event_type, amount, amount_minor FROM events"
            " WHERE agent_id=? AND event_type IN ('charge_receipt','refund') AND ts>=? AND ts<?",
            (agent_id, lo, hi),
        ).fetchall()
        total = 0
        for et, am, am_minor in rows:
            v = int(am_minor) if am_minor is not None else int(round(float(am) * MINOR))
            total += v if et == "charge_receipt" else -v
        return total

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
        sql = ("SELECT seq, ts, event_type, agent_id, host, amount, payload,"
               " prev_hash, hash, amount_minor FROM events")
        if agent_id:
            rows = self.conn.execute(sql + " WHERE agent_id=? ORDER BY seq",
                                     (agent_id,)).fetchall()
        else:
            rows = self.conn.execute(sql + " ORDER BY seq").fetchall()
        return [
            {"seq": s, "ts": t, "event_type": et, "agent_id": a, "host": h,
             "amount": am, "payload": p, "prev_hash": ph, "hash": ha,
             "amount_minor": amn}
            for (s, t, et, a, h, am, p, ph, ha, amn) in rows
        ]

    def backfill_amount_minor(self) -> int:
        """v0.4 backfill: NULL amount_minor'ları major-değerden türet (tek-seferlik).
        Kolon hash'e girmez → zincir-hash'leri değişmez (K0 korunur); idempotent."""
        with self._lock:
            cur = self.conn.execute(
                "UPDATE events SET amount_minor = CAST(ROUND(amount * ?) AS INTEGER)"
                " WHERE amount_minor IS NULL",
                (MINOR,),
            )
        return cur.rowcount

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
                " amount, payload, prev_hash, hash, amount_minor)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (int(ev["seq"]), float(ev["ts"]), ev["event_type"],
                 ev["agent_id"], ev["host"], float(ev["amount"]),
                 ev["payload"], ev["prev_hash"], ev["hash"],
                 ev.get("amount_minor")),
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

    def __del__(self):
        # Güvenlik-ağı: close() çağrılmadan çöp-toplanırsa bağlantıyı sessizce
        # kapat — aksi hâlde GC-sonrası ResourceWarning doğar (ve pyproject
        # disiplinimizde test-düşürür). Double-close güvenli (no-op).
        try:
            self.conn.close()
        except Exception:
            pass
