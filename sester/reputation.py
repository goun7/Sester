"""SESTER reputation ledgeri — x402 `reputation` extension (issue #1024).

2026-10-01 — x402 vakfinin en aktif extension tartismalarindan
[#1024](https://github.com/x402-foundation/x402/issues/1024) ile
paralel modül: ödeme islemlerine bagli ajan-itibari.

Tasarim notu (architecture decision):
    Reputation, policy-motorundan *bagimsizdir* — kararlar DENY/ALLOW
    icin kullanilmaz. Kasit budur: itibar, piyasa sinyali ve
    denetim katmanidir; fail-closed politika yalniz kural-tabanli kalir.
    Kararlari reputation'a baglamak, zengin ajanlara otomatik onay
    demektir (v0 güvenlik kontrati bozar).

Hesap (x402 #1024 §3'e paralel):
    - her **service delivery** icin agent imzasi gerekir (proof of delivery)
    - her ödeme basarili ise +1 tamamlanan, basarisiz/iptal ise 0
    - score = tamamlanan / (tamamlanan + reddedilen) — Laplace yumusatma
      ile: (tamam+1)/(tamam+reddet+2), böylece 0 islemde score 0.5
      olur (aşırı güven degil, nötr baslangiç)

x402 uyumluluk notu:
    Spesifikasyon hala taslakta; bu modül sadece ledger'dan OK yapar
    ve yeni event-tipleri eklemez (EVENT_TYPES taksonomisini
    genisletmedigi icin fail-closed kontrati korunur).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Reputation:
    """Tek bir ajan icin itibar özeti (read-only view)."""

    agent: str
    completed: int = 0
    denied: int = 0
    total_spent: float = 0.0
    unique_resources: int = 0  # #2833: wash-trade direnci

    @property
    def score(self) -> float:
        """Laplace-yumusatilmis tamamlanma orani [0,1].

        0 islem → 0.5 (nötr); her red 0'a, her tamamlama 1'e yaklastirir.
        """
        return (self.completed + 1.0) / (self.completed + self.denied + 2.0)

    @property
    def diversity_ratio(self) -> float:
        """#2833: islem cesitliligi — wash-tradeye karsi anahtar metrik.

        1000 islem TEK resource'ta → ratio 1/1000 ≈ 0.001 (sentetik).
        10 islem 10 farkli resource'ta → ratio 1.0 (gercek aktivite).
        Cuzdan-cifti wash trade bu metrigi yukselemez.
        """
        if self.completed <= 0:
            return 0.0
        return self.unique_resources / self.completed

    @property
    def wash_resistant_score(self) -> float:
        """Cesitlilik-ayarlanmis skor: wash trade ile sismeye karsi.

        score * sqrt(diversity_ratio): sqrt, tek-tek islemleri tam
        sifirlamaz ama coklayarak 1.0'a ulasmayi engeller.
        1000 islem 1 resource → 0.999 * sqrt(0.001) ≈ 0.032
        10 islem 10 resource → 1.0 * 1.0 = 1.0
        """
        import math
        return self.score * math.sqrt(max(0.0, self.diversity_ratio))

    @property
    def total(self) -> int:
        return self.completed + self.denied


class ReputationLedger:
    """Ledger'dan ajan itibari okur — hicbir sey YAZMAZ (append-only korur).

    Fail-safe: ledger'dan yalnizca `permission_decision` olaylarini sayar;
    bilinmeyen satirlar veya bos tablo → nötr Reputation (score 0.5),
    asla exception degil (denetim araci oldugu icin güvenilir olmali).
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def _query(self, agent: str) -> Reputation:
        try:
            conn = sqlite3.connect(self._db_path)
            try:
                # tamamlanan = izin verilen ödeme; reddedilen = deny
                # #2833: COUNT(DISTINCT resource) — wash-trade direnci
                row = conn.execute(
                    """SELECT
                         SUM(CASE WHEN json_extract(payload,'$.decision')='allow' THEN 1 ELSE 0 END),
                         SUM(CASE WHEN json_extract(payload,'$.decision')='deny'  THEN 1 ELSE 0 END),
                         COALESCE(SUM(amount), 0.0),
                         COUNT(DISTINCT host)
                       FROM events
                       WHERE agent_id=? AND event_type='permission_decision'""",
                    (agent,),
                ).fetchone()
            finally:
                conn.close()
        except (sqlite3.Error, OSError):
            # tablo yok / bos → nötr (fail-safe, fail-open DEGIL: okuma araci)
            return Reputation(agent=agent)
        if not row:
            return Reputation(agent=agent)
        return Reputation(
            agent=agent,
            completed=int(row[0] or 0),
            denied=int(row[1] or 0),
            total_spent=float(row[2] or 0.0),
            unique_resources=int(row[3] or 0),
        )

    def reputation(self, agent: str) -> Reputation:
        return self._query(agent)

    def top_agents(self, limit: int = 10) -> list[Reputation]:
        """En cok ödeme yapan ajanlar (itibar siralamasi degil — hacim)."""
        try:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    """SELECT agent_id,
                              SUM(CASE WHEN json_extract(payload,'$.decision')='allow' THEN 1 ELSE 0 END),
                              SUM(CASE WHEN json_extract(payload,'$.decision')='deny'  THEN 1 ELSE 0 END),
                              COALESCE(SUM(amount), 0.0)
                       FROM events
                       WHERE event_type='permission_decision'
                       GROUP BY agent_id
                       ORDER BY 4 DESC
                       LIMIT ?""",
                    (limit,),
                ).fetchall()
            finally:
                conn.close()
        except (sqlite3.Error, OSError):
            return []
        return [
            Reputation(agent=r[0], completed=int(r[1] or 0),
                       denied=int(r[2] or 0), total_spent=float(r[3] or 0.0))
            for r in rows
        ]
