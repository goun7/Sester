"""Reputation modulu testleri — x402 #1024 reputation extension paralel.

LEAD 2026-10-01: modul ledger'dan OK yapar, hicbir sey YAZMAZ;
testler kendi ledger'ini kurar (gerçek Ledger ile, mock'suz).
"""

import time

from sester.ledger import Ledger  # noqa: E402
from sester.reputation import ReputationLedger, Reputation  # noqa: E402


def _ledger(tmp_path, secret: str = "k") -> Ledger:
    return Ledger(str(tmp_path / f"rep-{time.time_ns()}.sqlite3"), secret=secret)


def test_bos_ajan_nötr_score(tmp_path):
    """0 islem → score 0.5 (asiri guven degil, nötr baslangic)."""
    led = _ledger(tmp_path)
    try:
        rep = ReputationLedger(led.db_path)
        r = rep.reputation("yeni-ajan")
        assert r.completed == 0
        assert r.denied == 0
        assert r.score == 0.5
        assert r.total == 0
    finally:
        led.close()


def test_olusturulmus_izin_ve_red_sayilir(tmp_path):
    """allow → +1 completed, deny → +1 denied; score Laplace ile yumusatilir."""
    led = _ledger(tmp_path)
    try:
        led.append("permission_decision", "a1", "/x", 0.05,
                   payload={"decision": "allow"})
        led.append("permission_decision", "a1", "/y", 0.0,
                   payload={"decision": "deny"})
        rep = ReputationLedger(led.db_path)
        r = rep.reputation("a1")
        assert r.completed == 1
        assert r.denied == 1
        # (1+1)/(1+1+2) = 0.5
        assert r.score == 0.5
    finally:
        led.close()


def test_mukemmel_gecmis_score_1e_yaklasir(tmp_path):
    """Sadece izinler → score 1'e yaklasir ama asla 1 olmaz (Laplace)."""
    led = _ledger(tmp_path)
    try:
        for i in range(9):
            led.append("permission_decision", "a2", f"/e{i}", 0.01,
                       payload={"decision": "allow"})
        rep = ReputationLedger(led.db_path)
        r = rep.reputation("a2")
        assert r.completed == 9
        assert r.denied == 0
        # (9+1)/(9+0+2) = 10/11 ≈ 0.909
        assert abs(r.score - 10 / 11) < 1e-9
        assert r.score < 1.0, "Laplace: sonsuz iyi olsa da 1'e ulasmaz"
    finally:
        led.close()


def test_top_agents_hacme_gore_siralar(tmp_path):
    """top_agents en cok odeme yapani once getirir (itibar siralamasi degil)."""
    led = _ledger(tmp_path)
    try:
        led.append("permission_decision", "kucuk", "/x", 0.01,
                   payload={"decision": "allow"})
        led.append("permission_decision", "buyuk", "/y", 5.0,
                   payload={"decision": "allow"})
        rep = ReputationLedger(led.db_path)
        top = rep.top_agents(limit=10)
        assert len(top) >= 2
        assert top[0].agent == "buyuk"
        assert top[0].total_spent >= 5.0
    finally:
        led.close()


def test_eksik_veritabani_fail_safe_nötr(tmp_path):
    """Olmayan DB → exception degil, nötr Reputation (denetim araci güveni)."""
    rep = ReputationLedger(str(tmp_path / "yok.sqlite3"))
    r = rep.reputation("a3")
    assert r.agent == "a3"
    assert r.score == 0.5
    assert rep.top_agents() == []


# LEAD 2026-10-01 — x402 #2833: "Volume is not trust" wash-trade saldirisi
# Iki cuzdan sonsuz islem uretip reputation'i sisebilir.
# Cozum: diversity_ratio (unique host / islem) ile wash_resistant_score.
def test_wash_trade_tek_host_sisme_engellenir(tmp_path):
    """1000 islem TEK host'ta → wash_resistant cok dusuk (0.032)."""
    led = _ledger(tmp_path)
    try:
        for _ in range(1000):
            led.append("permission_decision", "wash-agent", "/x", 0.001,
                       payload={"decision": "allow"})
        rep = ReputationLedger(led.db_path)
        r = rep.reputation("wash-agent")
        assert r.completed == 1000
        assert r.unique_resources == 1
        assert r.diversity_ratio == 0.001
        # klasik score saldiriya yenik (0.999)
        assert r.score > 0.99
        # wash-resistant skor saldiriyi engeller (< 0.1)
        assert r.wash_resistant_score < 0.1
    finally:
        led.close()


def test_mesru_cesitli_islem_korunur(tmp_path):
    """10 islem 10 farkli host → wash_resistant yuksek (0.9+)."""
    led = _ledger(tmp_path)
    try:
        for i in range(10):
            led.append("permission_decision", "real-agent", f"/srv{i}", 0.01,
                       payload={"decision": "allow"})
        rep = ReputationLedger(led.db_path)
        r = rep.reputation("real-agent")
        assert r.completed == 10
        assert r.unique_resources == 10
        assert r.diversity_ratio == 1.0
        assert r.wash_resistant_score > 0.9
    finally:
        led.close()


def test_cesitlilik_eksik_ortalamada_dusuk(tmp_path):
    """50 islem 5 host → ratio 0.1 → wash_resistant 0.999*sqrt(0.1)."""
    led = _ledger(tmp_path)
    try:
        for i in range(50):
            host = f"/h{i % 5}"
            led.append("permission_decision", "mid-agent", host, 0.01,
                       payload={"decision": "allow"})
        rep = ReputationLedger(led.db_path)
        r = rep.reputation("mid-agent")
        assert r.completed == 50
        assert r.unique_resources == 5
        assert abs(r.diversity_ratio - 0.1) < 1e-9
        # 0.98 * sqrt(0.1) ≈ 0.31
        assert 0.25 < r.wash_resistant_score < 0.4
    finally:
        led.close()


def test_bos_ajanda_diversity_sifir(tmp_path):
    """0 islem → diversity_ratio 0.0 (bolum-sifir guvenli)."""
    led = _ledger(tmp_path)
    try:
        rep = ReputationLedger(led.db_path)
        r = rep.reputation("boss-ajan")
        assert r.diversity_ratio == 0.0
        assert r.wash_resistant_score == 0.0
    finally:
        led.close()
