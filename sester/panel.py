"""SESTER panel — basit HTML tablo: kim, kaç çağrı, ne kadar + zincir-durumu.

PRD sürüm-tablosu hafta-2 çıktısı. Marka: brand/sester-mark.svg gömülü.
"""

from __future__ import annotations

import html
import time
from typing import Any

# brand/sester-mark.svg'nin gömülü kopyası (tek-dosya dağıtım kültürü):
# Sester-sikkesi — halka + darp-çizgisi + S-monogramı
# hafif sürüklenme bilinçli; gradient/parlama yasak — MARKA_NOTU.md §4)
MARK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="30" height="30">
  <circle cx="100" cy="100" r="78" fill="none" stroke="#171717" stroke-width="14"/>
  <circle cx="100" cy="100" r="56" fill="none" stroke="#B8860B" stroke-width="8"/>
  <path d="M 128 74 C 118 62 82 62 78 82 C 74 100 126 100 122 118 C 118 138 82 138 72 126"
        fill="none" stroke="#171717" stroke-width="14" stroke-linecap="round"/>
</svg>"""

PAGE = """<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<title>SESTER · Panel</title>
<style>
  body {{ font-family: Georgia, serif; background:#F5F0E4; color:#171717; margin:0; padding:32px; }}
  .wrap {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ display:flex; align-items:center; gap:10px; font-size:24px; letter-spacing:1px; }}
  h1 .sub {{ font-size:13px; font-weight:normal; opacity:.6; font-style:italic; }}
  table {{ width:100%; border-collapse:collapse; margin-top:14px; background:#FCFAF3;
          border:2px solid #171717; }}
  th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid rgba(23,23,23,.25); }}
  th {{ background:#171717; color:#F5F0E4; font-size:13px; letter-spacing:1px; }}
  tr:hover td {{ background: rgba(184,134,11,.08); }}
  .gold {{ color:#B8860B; font-weight:bold; }}
  .ok {{ color:#2e7d32; font-weight:bold; }}
  .bad {{ color:#b03030; font-weight:bold; }}
  .muted {{ opacity:.65; font-size:13px; }}
  code {{ font-family:'Courier New',monospace; font-size:12.5px; }}
</style></head><body><div class="wrap">
<h1>{mark} SESTER <span class="sub">· AgentMeter paneli · {ts}</span></h1>

<h2 style="margin-top:26px;font-size:17px;">Ajanlar</h2>
<table>
<tr><th>Ajan</th><th>Çağrı (bugün)</th><th>Harcama (bugün)</th><th>Toplam harcama</th><th>Son işlem</th></tr>
{agent_rows}
</table>

<h2 style="margin-top:26px;font-size:17px;">Zincir (son olaylar)</h2>
<table>
<tr><th>#</th><th>Tip</th><th>Ajan</th><th>Host</th><th>Tutar</th><th>Hash</th></tr>
{event_rows}
</table>

<p class="muted" style="margin-top:18px;">Zincir-bütünlüğü: {chain_status} ·
Toplam olay: {total_events} · <code>GET /healthz</code> makine-okur durum.</p>
</div></body></html>"""


APPROVALS_TMPL = """<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<title>SESTER · Onay Paneli</title>
<style>
  body {{ font-family: Georgia, serif; background:#F5F0E4; color:#171717; margin:0; padding:32px; }}
  .wrap {{ max-width: 860px; margin: 0 auto; }}
  h1 {{ display:flex; align-items:center; gap:10px; font-size:24px; letter-spacing:1px; }}
  h1 .sub {{ font-size:13px; font-weight:normal; opacity:.6; font-style:italic; }}
  table {{ width:100%; border-collapse:collapse; margin-top:14px; background:#FCFAF3;
          border:2px solid #171717; }}
  th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid rgba(23,23,23,.25); }}
  th {{ background:#171717; color:#F5F0E4; font-size:13px; letter-spacing:1px; }}
  tr:hover td {{ background: rgba(184,134,11,.08); }}
  .gold {{ color:#B8860B; font-weight:bold; }}
  .muted {{ opacity:.65; font-size:13px; }}
  code {{ font-family:'Courier New',monospace; font-size:12.5px; }}
  button {{ font-family:inherit; font-size:13px; padding:6px 14px; cursor:pointer;
           border:2px solid #171717; background:#FCFAF3; letter-spacing:1px; }}
  button.approve {{ background:#B8860B; color:#FCFAF3; border-color:#171717; }}
  button:hover {{ opacity:.85; }}
  .empty {{ margin-top:22px; font-style:italic; opacity:.7; }}
</style></head><body><div class="wrap">
<h1>{mark} SESTER <span class="sub">· İnsan-Onay Paneli · {ts}</span></h1>

<h2 style="margin-top:24px;font-size:17px;">Bekleyen harcama-biletleri
<span class="muted">(TTL {ttl:.0f} sn — dolan bilet otomatik-RED, fail-closed)</span></h2>
{content}

<p class="muted" style="margin-top:20px;">Onay <strong>bir-kezlik</strong>: sonraki uyumlu
istek bileti tüketir ve normal ödeme-akışına girer. Her karar
(<code>escalation_approved/denied</code>) hash-chain'li ledger'a yazılır —
<code>/panel</code> zincir-görünümünde izlenebilir.</p>
</div>
<script>
function decide(id, approve) {{
  const verb = approve ? 'ONAYLA' : 'REDDET';
  if (!confirm(id + ' bileti ' + verb + '?')) return;
  fetch('/escalations/' + encodeURIComponent(id) + '/decide', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{approve: approve, by: 'panel'}})
  }}).then(r => r.json()).then(j => {{ if (!j.ok) alert(j.error || 'hata'); location.reload(); }})
    .catch(e => {{ alert('istek başarısız: ' + e); location.reload(); }});
}}
</script>
</body></html>"""


class _ApprovalsPage:
    """İnsan-onay paneli — /approvals; bekleyen biletler + tek-tık karar."""

    @staticmethod
    def render(pending: list[dict[str, Any]], ttl: float) -> str:
        if not pending:
            content = ('<p class="empty">(kuyruk boş — bekleyen onay yok. '
                       'Politika <code>then: escalate</code> kararları burada listelenir.)</p>')
        else:
            rows = []
            now = time.time()
            for t in pending:
                left = max(0, int(t["expires_at"] - now))
                rows.append(
                    f"<tr><td><code>{html.escape(t['esc_id'])}</code></td>"
                    f"<td><code>{html.escape(t['agent'])}</code></td>"
                    f"<td><code>{html.escape(t['resource'])}</code></td>"
                    f"<td>{t['amount']:.4f}</td>"
                    f"<td class='muted'>{html.escape(t['rule_id'])}</td>"
                    f"<td class='gold'>{left} sn</td>"
                    f"<td>"
                    f"<button class='approve' onclick=\"decide('{html.escape(t['esc_id'], quote=True)}', true)\">ONAYLA</button> "
                    f"<button onclick=\"decide('{html.escape(t['esc_id'], quote=True)}', false)\">REDDET</button>"
                    f"</td></tr>")
            content = ("<table><tr><th>Bilet</th><th>Ajan</th><th>Kaynak</th>"
                       "<th>Tutar</th><th>Kural</th><th>Kalan</th><th>Karar</th></tr>"
                       + "".join(rows) + "</table>")
        return APPROVALS_TMPL.format(mark=MARK_SVG, ts=time.strftime("%Y-%m-%d %H:%M:%S"),
                                     ttl=ttl, content=content)


APPROVALS_PAGE = _ApprovalsPage()


def render_panel(ledger: Any, quota: float) -> str:
    day = time.strftime("%Y-%m-%d")
    agents = ledger.per_agent_summary(200)
    events = ledger.recent_events(30)

    agent_rows = []
    for a in agents:
        spent_minor = ledger.spent_today_minor(a["agent_id"])  # v0.4 tam-sayı
        spent_today = spent_minor / 1_000_000
        pct = min(100.0, (spent_today / quota * 100.0) if quota else 0)
        bar = f'<span class="gold">{"▮" * int(pct // 10)}{"▯" * (10 - int(pct // 10))}</span>'
        agent_rows.append(
            f"<tr><td><code>{html.escape(a['agent_id'])}</code></td>"
            f"<td>{ledger.count_today(a['agent_id'])}</td>"
            f"<td>{spent_today:.4f} {bar}</td>"
            f"<td>{a['spent']:.4f}</td>"
            f"<td class='muted'>{time.strftime('%H:%M:%S', time.localtime(a['last_ts']))}</td></tr>"
        )
    if not agent_rows:
        agent_rows.append("<tr><td colspan='5' class='muted'>Henüz ücretli-işlem yok — "
                          "ajan başlığıyla ilk isteği bekleyin.</td></tr>")

    event_rows = []
    for e in events:
        et = {"charge_receipt": "ödeme", "permission_decision": "karar",
              "refund": "iade", "usage_event": "kullanım",
              "settlement": "tahsilat", "protocol_intent": "niyet",
              "escalation_parked": "onay-bekliyor",
              "escalation_approved": "onaylandı",
              "escalation_denied": "onay-red",
              "escalation_consumed": "onay-kullanıldı"}.get(e["event_type"], e["event_type"])
        event_rows.append(
            f"<tr><td>{e['seq']}</td><td>{et}</td>"
            f"<td><code>{html.escape(e['agent_id'])}</code></td>"
            f"<td class='muted'>{html.escape(e['host'])}</td>"
            f"<td>{e['amount']:.4f}</td><td><code>{html.escape(e['hash'])}</code></td></tr>"
        )

    chain_ok = ledger.verify_chain()
    return PAGE.format(
        mark=MARK_SVG,
        ts=time.strftime("%Y-%m-%d %H:%M:%S"),
        agent_rows="".join(agent_rows),
        event_rows="".join(event_rows),
        chain_status=('<span class="ok">SAĞLAM ✓</span>' if chain_ok
                      else '<span class="bad">KIRILMIŞ — müdahale!</span>'),
        total_events=events[0]["seq"] if events else 0,
    )
