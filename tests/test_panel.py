"""SESTER onay-paneli testleri — HTML render + XSS güvenliği.

Kapsanan modül: sester/panel.py (_ApprovalsPage.render).
Panel, insan-onay katmanının çıktısıdır: bekleyen escalation biletlerini
listeler ve tek-tık ONAYLA/REDDET sunar.

Güvenlik açısından KRİTİK: tüm ajan-kaynaklı alanlar html.escape'den
geçmelidir — ajan_adı/kaynak/bilet kimliği bir HTML injection vektörü
olamaz.
"""

from __future__ import annotations

import html
import time
import unittest

from sester.panel import APPROVALS_PAGE, _ApprovalsPage


def _pending(**over) -> dict:
    base = {
        "esc_id": "esc-001",
        "agent": "agent-a",
        "resource": "svc-payments",
        "amount": 1.2345,
        "rule_id": "r1",
        "expires_at": time.time() + 300,
    }
    base.update(over)
    return base


class TestApprovalsPageRender(unittest.TestCase):
    """_ApprovalsPage.render — boş ve dolu kuyruk çıktıları."""

    def test_empty_queue_renders_note(self):
        html_out = _ApprovalsPage.render([], ttl=900.0)
        self.assertIn("kuyruk boş", html_out)
        self.assertNotIn("<table>", html_out)

    def test_empty_queue_still_full_page(self):
        html_out = _ApprovalsPage.render([], ttl=900.0)
        self.assertIn("<html", html_out)
        self.assertIn("</html>", html_out)

    def test_pending_ticket_appears(self):
        html_out = _ApprovalsPage.render([_pending()], ttl=900.0)
        self.assertIn("esc-001", html_out)
        self.assertIn("svc-payments", html_out)
        self.assertIn("ONAYLA", html_out)
        self.assertIn("REDDET", html_out)

    def test_amount_formatted_4dp(self):
        html_out = _ApprovalsPage.render([_pending(amount=1.23450001)], ttl=900.0)
        self.assertIn("1.2345", html_out)

    def test_table_headers_present(self):
        html_out = _ApprovalsPage.render([_pending()], ttl=900.0)
        for h in ("Bilet", "Ajan", "Kaynak", "Tutar", "Kural", "Kalan", "Karar"):
            self.assertIn(h, html_out)

    def test_ttl_in_page(self):
        html_out = _ApprovalsPage.render([], ttl=900.0)
        self.assertIn("900", html_out)

    def test_time_left_shows_seconds(self):
        html_out = _ApprovalsPage.render(
            [_pending(expires_at=time.time() + 42)], ttl=900.0)
        # render sirasinda time.time() 41-42 arasi olur; ya 41 ya 42
        self.assertTrue(("41 sn" in html_out) or ("42 sn" in html_out),
                        "kalan sure saniye olarak render edilmeli")

    def test_expired_ticket_shows_zero(self):
        html_out = _ApprovalsPage.render(
            [_pending(expires_at=time.time() - 10)], ttl=900.0)
        self.assertIn("0 sn", html_out)

    def test_multiple_tickets_all_rendered(self):
        tickets = [_pending(esc_id=f"esc-{i:03d}") for i in range(5)]
        html_out = _ApprovalsPage.render(tickets, ttl=900.0)
        for i in range(5):
            self.assertIn(f"esc-{i:03d}", html_out)

    def test_decide_buttons_bound_to_ticket_id(self):
        html_out = _ApprovalsPage.render([_pending()], ttl=900.0)
        self.assertIn("decide('esc-001', true)", html_out)
        self.assertIn("decide('esc-001', false)", html_out)


class TestApprovalsPageXSS(unittest.TestCase):
    """XSS güvenliği — ajan-kaynaklı alanlar escape edilmelidir."""

    def test_agent_name_escaped(self):
        html_out = _ApprovalsPage.render(
            [_pending(agent="<script>alert(1)</script>")], ttl=900.0)
        self.assertNotIn("<script>alert(1)</script>", html_out)
        self.assertIn("&lt;script&gt;", html_out)

    def test_resource_escaped(self):
        html_out = _ApprovalsPage.render(
            [_pending(resource="<img src=x onerror=alert(1)>")], ttl=900.0)
        self.assertNotIn("<img src=x", html_out)
        self.assertIn("&lt;img", html_out)

    def test_esc_id_escaped_in_row(self):
        html_out = _ApprovalsPage.render(
            [_pending(esc_id="a'><script>alert(1)</script>")], ttl=900.0)
        # template'in kendi script bloklari vardir; veri kaynakli olan
        # escape edilmis olmali: "&lt;script&gt;" gecmeli
        self.assertIn("&lt;script&gt;", html_out)
        # veri kaynakli KOD calismamali: onclick icinde ham > gecemez
        self.assertNotIn("a'><script>alert(1)</script>", html_out)

    def test_esc_id_escaped_in_onclick(self):
        """onclick attribute içinde quote-escape ile sınırlandırma."""
        raw = "a');alert(1);('"
        html_out = _ApprovalsPage.render([_pending(esc_id=raw)], ttl=900.0)
        # template'in kendi decide() JS'i "alert" icerir; veri kaynakli
        # cikinti olmamali: ham "');alert(1);(" gecmemeli
        self.assertNotIn("');alert(1);(", html_out)
        self.assertIn(html.escape(raw, quote=True), html_out)

    def test_rule_id_escaped(self):
        html_out = _ApprovalsPage.render(
            [_pending(rule_id='"><script>alert(1)</script>')], ttl=900.0)
        self.assertIn("&lt;script&gt;", html_out)
        # veri kaynakli script tag'i attribute kirmamali
        self.assertNotIn('"><script>', html_out)

    def test_no_raw_script_tag_from_data(self):
        """Hiçbir veri alanı raw <script> üretememeli."""
        evil = "<script>alert('xss')</script>"
        for field in ("agent", "resource", "esc_id", "rule_id"):
            html_out = _ApprovalsPage.render([_pending(**{field: evil})],
                                             ttl=900.0)
            # veri kaynakli script tag'i olmamali (template'in kendi JS'i disinda)
            # template'in script bloklari tek yerde, veri satirlarinda olmamali
            self.assertIn("&lt;script&gt;", html_out)


class TestApprovalsPageInstance(unittest.TestCase):
    """APPROVALS_PAGE singleton — modul-level instance."""

    def test_singleton_is_page(self):
        self.assertIsInstance(APPROVALS_PAGE, _ApprovalsPage)

    def test_singleton_render_works(self):
        html_out = APPROVALS_PAGE.render([_pending()], ttl=900.0)
        self.assertIn("esc-001", html_out)


if __name__ == "__main__":
    unittest.main()
