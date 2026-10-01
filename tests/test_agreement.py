"""AgreementSession testleri — x402 #3646 terms-bound lifecycle.

LEAD 2026-10-01: Terms degismezligi, budget, expiry, crash-safe baglama.
Ledger ile GERCEK entegrasyon (mock'suz).
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from sester.agreement import (  # noqa: E402
    AGREEMENT_KEY,
    AgreementSession,
    Terms,
    agreement_filter,
)
from sester.ledger import Ledger  # noqa: E402


class TestTerms:
    def test_bos_id_reddedilir(self):
        with pytest.raises(ValueError, match="bos agreement_id"):
            Terms(agreement_id="", budget_minor=100, expires_at=0)

    def test_negatif_budget_reddedilir(self):
        with pytest.raises(ValueError, match="negatif budget"):
            Terms(agreement_id="a1", budget_minor=-1, expires_at=0)

    def test_suresiz_hic_suzmez(self):
        t = Terms(agreement_id="a1", budget_minor=100, expires_at=0)
        assert t.expired(now=1e12) is False

    def test_sure_dolmus(self):
        t = Terms(agreement_id="a1", budget_minor=100, expires_at=1000)
        assert t.expired(now=2000) is True
        assert t.expired(now=500) is False

    def test_sifir_budget_kalinti_yok(self):
        t = Terms(agreement_id="a1", budget_minor=0, expires_at=0)
        assert t.is_active is True  # suresiz, budget disinda


class TestAgreementSession:
    def make(self, budget=100_000, expiry=0):
        terms = Terms(agreement_id="agr-1", budget_minor=budget,
                      expires_at=expiry, description="test anlasma")
        return AgreementSession(terms)

    def test_aktif_agreement_odeme_baglar(self):
        s = self.make()
        p = s.bind_payment("agent-a", "/api/x")
        assert p[AGREEMENT_KEY] == "agr-1"
        assert p["decision"] == "allow"

    def test_suresi_dolmus_baglama_reddedilir(self):
        # expired True → bind_payment reddetmeli
        import sester.agreement as A
        orig = A.time.time
        A.time.time = lambda: 2000.0
        try:
            terms = Terms(agreement_id="agr-2", budget_minor=100,
                          expires_at=1000)
            s = AgreementSession(terms)
            assert s.terms.expired() is True
            with pytest.raises(ValueError, match="suresi dolmus"):
                s.bind_payment("a", "/x")
        finally:
            A.time.time = orig

    def test_budget_dolu_baglama_reddedilir(self):
        terms = Terms(agreement_id="agr-3", budget_minor=100, expires_at=0)
        s = AgreementSession(terms)
        # 100 harcadi → exhausted
        st = s.state_from(spent_minor=100, payments=5)
        assert st.budget_exhausted is True
        assert st.is_active is False

    def test_remaining_hesabi(self):
        terms = Terms(agreement_id="agr-4", budget_minor=1000, expires_at=0)
        s = AgreementSession(terms)
        st = s.state_from(spent_minor=300, payments=3)
        assert st.remaining == 700
        assert st.is_active is True

    def test_remaining_negatif_olmaz(self):
        terms = Terms(agreement_id="agr-5", budget_minor=100, expires_at=0)
        s = AgreementSession(terms)
        st = s.state_from(spent_minor=9999, payments=1)
        assert st.remaining == 0


class TestAgreementFilter:
    def test_eslesen_agreement(self):
        assert agreement_filter(
            {AGREEMENT_KEY: "a1", "decision": "allow"}, "a1") is True

    def test_eslesmeyen(self):
        assert agreement_filter(
            {AGREEMENT_KEY: "baska"}, "a1") is False

    def test_bosluk_payload(self):
        assert agreement_filter(None, "a1") is False
        assert agreement_filter({}, "a1") is False


class TestLedgerEntegrasyon:
    """GERCEK ledger ile: agreement bagli odeme + sayim."""

    def test_agreement_bagli_odeme_sayilir(self, tmp_path):
        led = Ledger(str(tmp_path / "agr.sqlite3"), secret="k")
        try:
            terms = Terms(agreement_id="agr-L", budget_minor=10_000_000,
                          expires_at=0)
            s = AgreementSession(terms)
            p = s.bind_payment("agent-L", "/api/paid")
            led.append("permission_decision", "agent-L", "/api/paid", 0.05,
                       payload=p)
            # ledger'dan agreement'a gore filtrele
            import sqlite3
            conn = sqlite3.connect(str(tmp_path / "agr.sqlite3"))
            try:
                rows = conn.execute(
                    "SELECT payload FROM events WHERE agent_id='agent-L'"
                ).fetchall()
            finally:
                conn.close()
            eslesen = [r for r in rows
                       if agreement_filter(json_loads(r[0]), "agr-L")]
            assert len(eslesen) == 1
        finally:
            led.close()


def json_loads(s):
    import json
    return json.loads(s)
