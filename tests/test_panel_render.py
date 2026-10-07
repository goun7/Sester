"""Panel render testleri — sester.panel (tarama-5).

Kapsanan kritik fonksiyonlar (40+ satır):
  - render_panel         (60 satır) — ajan/olay tabloları + zincir-durumu
  - _ApprovalsPage.render            — insan-onay kuyruğu + tek-tık karar

GÜVENLİK İNVARYANLARI (XSS/regresyon yakalamak için):
  1. Ledger'dan gelen TÜM diziler (agent_id, host, hash, esc_id, resource,
     rule_id) HTML-escape edilir — ham <script> enjeksiyonu mümkün değil.
  2. quota=0 bölme hatasına yol açmaz (pct=0 korunur).
  3. Boş ledger render edilir (tablo yer-tutucusu ile), traceback yok.
  4. Zincir kırık ise 'KIRILMIŞ' rozeti gösterilir (sağlık için kritik).
  5. Olay-tipi etiket haritası bilinmeyen tipe düşer (boşluk yok).

DIŞ çağrı YOK: ledger bir fake ile değiştirilir — gerçek SQLite yok.
"""

from __future__ import annotations

import html
import time

import pytest

from sester.panel import APPROVALS_PAGE, FAVICON_HREF, MARK_SVG, render_panel


class FakeLedger:
    """Ledger sorgu-yüzeyinin saf bir hatırası (gerçek DB yok)."""

    def __init__(self, agents=None, events=None, chain_ok=True, minor=0, today=0):
        self._agents = agents if agents is not None else []
        self._events = events if events is not None else []
        self._chain_ok = chain_ok
        self._minor = minor
        self._today = today
        self.exported = False

    def per_agent_summary(self, limit):
        return self._agents[:limit]

    def recent_events(self, limit):
        return self._events[:limit]

    def spent_today_minor(self, agent_id, *, day=None):
        return self._minor

    def count_today(self, agent_id):
        return self._today

    def verify_chain(self):
        return self._chain_ok

    def export_events(self, agent_id=None):
        self.exported = True
        return list(self._events)


def _agent(agent_id="<safe-agent>", spent=1.5, last_ts=None):
    return {
        "agent_id": agent_id,
        "calls": 3,
        "spent": spent,
        "last_ts": last_ts if last_ts is not None else time.time(),
    }


def _event(seq=1, et="charge_receipt", agent_id="agent-1", host="example.com",
           amount=0.05, minor=None, ts=None):
    d = {
        "seq": seq,
        "ts": ts if ts is not None else time.time(),
        "event_type": et,
        "agent_id": agent_id,
        "host": host,
        "amount": amount,
        "hash": "abcdef0123456789abcd",
    }
    if minor is not None:
        d["amount_minor"] = minor
    return d


# ---------------------------------------------------------------------------
# render_panel — yapısal çıktı
# ---------------------------------------------------------------------------

class TestRenderPanelStructure:
    def test_returns_html_document(self):
        out = render_panel(FakeLedger(), quota=10.0)
        assert out.strip().startswith("<!DOCTYPE html>")
        assert "</html>" in out

    def test_embeds_brand_mark_and_favicon(self):
        out = render_panel(FakeLedger(), quota=10.0)
        assert MARK_SVG in out
        assert FAVICON_HREF in out

    def test_renders_agent_row(self):
        ledger = FakeLedger(agents=[_agent("alpha-agent")], minor=50_000, today=2)
        out = render_panel(ledger, quota=10.0)
        assert "alpha-agent" in out
        assert "0.0500" in out  # 50_000 minor / 1_000_000
        assert ledger.exported is True

    def test_renders_event_row(self):
        ledger = FakeLedger(events=[_event(seq=42, agent_id="beta-agent")])
        out = render_panel(ledger, quota=10.0)
        assert "42" in out
        assert "beta-agent" in out
        assert "example.com" in out
        assert "abcdef0123456789" in out  # hash gösterilir

    def test_total_events_uses_last_event_seq(self):
        ledger = FakeLedger(events=[_event(seq=5), _event(seq=9)])
        out = render_panel(ledger, quota=10.0)
        assert "9" in out


# ---------------------------------------------------------------------------
# render_panel — güvenlik: XSS
# ---------------------------------------------------------------------------

class TestRenderPanelEscaping:
    @pytest.mark.parametrize("field,payload", [
        ("agent_id", "<script>alert(1)</script>"),
        ("agent_id", "<img src=x onerror=alert(2)>"),
    ])
    def test_agent_id_is_escaped(self, field, payload):
        ledger = FakeLedger(agents=[_agent(payload)], minor=1000, today=1)
        out = render_panel(ledger, quota=10.0)
        assert html.escape(payload) in out
        assert payload not in out

    def test_event_agent_and_host_are_escaped(self):
        evil = "<svg onload=alert(3)>"
        ledger = FakeLedger(events=[
            _event(agent_id=evil, host="<b>h</b>"),
        ])
        out = render_panel(ledger, quota=10.0)
        assert html.escape(evil) in out
        assert html.escape("<b>h</b>") in out
        assert evil not in out

    def test_event_hash_is_escaped(self):
        evil_hash = '"><script>alert(4)</script>'
        ledger = FakeLedger(events=[_event()])
        ledger._events[0]["hash"] = evil_hash
        out = render_panel(ledger, quota=10.0)
        assert evil_hash not in out


# ---------------------------------------------------------------------------
# render_panel — kota ve sınır değerler
# ---------------------------------------------------------------------------

class TestRenderPanelQuota:
    def test_quota_zero_does_not_raise(self):
        out = render_panel(FakeLedger(agents=[_agent()], minor=5000), quota=0.0)
        assert "</html>" in out  # ZeroDivisionError yok

    def test_spending_capped_at_100_percent(self):
        # 60_000 minor = 0.06 USDC; quota=0.01 → %600 → %100'de durur (10/10)
        out = render_panel(FakeLedger(agents=[_agent()], minor=60_000), quota=0.01)
        assert "▮" * 10 in out

    def test_spending_bar_full_when_at_quota(self):
        out = render_panel(FakeLedger(agents=[_agent()], minor=100_000), quota=0.1)
        assert "▮" * 10 in out

    def test_quota_bar_ratio(self):
        # 20_000 minor = 0.02; quota=0.08 → %25 → 2/10 dolu
        out = render_panel(FakeLedger(agents=[_agent()], minor=20_000), quota=0.08)
        assert "▮▮" in out

    def test_negative_quota_does_not_raise(self):
        out = render_panel(FakeLedger(), quota=-5.0)
        assert "</html>" in out


# ---------------------------------------------------------------------------
# render_panel — zincir-durumu ve boş durumlar
# ---------------------------------------------------------------------------

class TestRenderPanelChainAndEmpty:
    def test_chain_ok_shows_saglam(self):
        out = render_panel(FakeLedger(chain_ok=True), quota=10.0)
        assert "SAĞLAM" in out
        assert "KIRILMIŞ" not in out

    def test_chain_broken_shows_kirilmis(self):
        out = render_panel(FakeLedger(chain_ok=False), quota=10.0)
        assert "KIRILMIŞ" in out
        assert "SAĞLAM" not in out

    def test_empty_ledger_renders_placeholder(self):
        out = render_panel(FakeLedger(), quota=10.0)
        assert "Henüz" in out
        assert "</html>" in out

    def test_no_events_total_is_zero(self):
        out = render_panel(FakeLedger(), quota=10.0)
        assert "Toplam olay: 0" in out


# ---------------------------------------------------------------------------
# render_panel — olay-tipi etiket haritası
# ---------------------------------------------------------------------------

class TestRenderPanelEventLabels:
    @pytest.mark.parametrize("et,expected", [
        ("charge_receipt", "ödeme"),
        ("permission_decision", "karar"),
        ("refund", "iade"),
        ("settlement", "tahsilat"),
        ("protocol_intent", "niyet"),
        ("escalation_parked", "onay-bekliyor"),
        ("escalation_approved", "onaylandı"),
        ("escalation_denied", "onay-red"),
        ("escalation_consumed", "onay-kullanıldı"),
        ("totally_unknown_type", "totally_unknown_type"),
    ])
    def test_event_type_label(self, et, expected):
        ledger = FakeLedger(events=[_event(et=et)])
        out = render_panel(ledger, quota=10.0)
        assert expected in out


# ---------------------------------------------------------------------------
# render_panel — günlük özet sayaçları
# ---------------------------------------------------------------------------

class TestRenderPanelDailyTotals:
    def test_daily_total_counts_today_charges(self):
        now = time.time()
        events = [
            _event(et="charge_receipt", minor=30_000, seq=1, ts=now),
            _event(et="charge_receipt", minor=20_000, seq=2, ts=now),
            _event(et="refund", minor=10_000, seq=3, ts=now),
        ]
        out = render_panel(FakeLedger(events=events), quota=10.0)
        # yalnızca charge_receipt toplanır: 50_000 minor = 0.05
        assert "0.0500" in out
        assert "Ücretli-işlem (bugün): <span class=\"gold\">2</span>" in out

    def test_old_day_charges_excluded(self):
        old = time.time() - 2 * 86400
        events = [
            _event(et="charge_receipt", minor=99_000_000, seq=9, ts=old),
        ]
        out = render_panel(FakeLedger(events=events), quota=10.0)
        assert "99.0000" not in out

    def test_missing_amount_minor_treated_as_zero(self):
        now = time.time()
        events = [_event(et="charge_receipt", seq=4, ts=now)]
        out = render_panel(FakeLedger(events=events), quota=10.0)
        assert "</html>" in out  # KeyError/TypeError yok


# ---------------------------------------------------------------------------
# _ApprovalsPage.render — insan-onay paneli
# ---------------------------------------------------------------------------

class TestApprovalsPageRender:
    def test_empty_queue_message(self):
        out = APPROVALS_PAGE.render([], ttl=300)
        assert "kuyruk boş" in out
        assert "<!DOCTYPE html>" in out

    def test_pending_ticket_rendered(self):
        now = time.time()
        out = APPROVALS_PAGE.render([
            {"esc_id": "ESC-42", "agent": "agent-seven", "resource": "/premium",
             "amount": 0.75, "rule_id": "RULE-9", "expires_at": now + 120},
        ], ttl=300)
        assert "ESC-42" in out
        assert "agent-seven" in out
        assert "/premium" in out
        assert "RULE-9" in out
        assert "ONAYLA" in out
        assert "REDDET" in out

    def test_ttl_shown(self):
        out = APPROVALS_PAGE.render([], ttl=256)
        assert "256" in out

    def test_expired_ticket_shows_zero_seconds(self):
        now = time.time()
        out = APPROVALS_PAGE.render([
            {"esc_id": "ESC-1", "agent": "a", "resource": "/r", "amount": 0.1,
             "rule_id": "R", "expires_at": now - 50},
        ], ttl=300)
        assert "0 sn" in out  # max(0, ...) negatif süreyi engeller

    @pytest.mark.parametrize("field", ["esc_id", "agent", "resource", "rule_id"])
    def test_ticket_fields_are_escaped(self, field):
        evil = "<script>alert(5)</script>"
        now = time.time()
        ticket = {
            "esc_id": evil, "agent": evil, "resource": evil, "amount": 0.1,
            "rule_id": evil, "expires_at": now + 60,
        }
        out = APPROVALS_PAGE.render([ticket], ttl=300)
        assert evil not in out
        assert html.escape(evil) in out

    def test_amount_formatted_to_four_decimals(self):
        now = time.time()
        out = APPROVALS_PAGE.render([
            {"esc_id": "E", "agent": "a", "resource": "/r", "amount": 1.23456,
             "rule_id": "R", "expires_at": now + 60},
        ], ttl=300)
        assert "1.2346" in out

    def test_decide_endpoint_per_ticket(self):
        now = time.time()
        out = APPROVALS_PAGE.render([
            {"esc_id": "ESC-A", "agent": "a", "resource": "/r", "amount": 0.5,
             "rule_id": "R", "expires_at": now + 60},
        ], ttl=300)
        # buton tıklaması decide('<esc_id>', approve) çağırır
        assert "decide('ESC-A', true)" in out
        assert "decide('ESC-A', false)" in out
        # JS fetch yolu encodeURIComponent ile inşa edilir
        assert "/escalations/" in out
        assert "encodeURIComponent" in out
