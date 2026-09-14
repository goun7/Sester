"""SESTER panel — basit HTML tablo: kim, kaç çağrı, ne kadar + zincir-durumu.

PRD sürüm-tablosu hafta-2 çıktısı. Marka: brand/sester-mark-v2.svg gömülü (Chain-S, 2026-09-14).
"""

from __future__ import annotations

import base64
import html
import time
from typing import Any

# brand/sester-mark-v2.svg'nin gömülü kopyası (tek-dosya dağıtım kültürü):
# Chain-S markası — S harfi + hash-chain bağı (aday-E; potrace tek-path).
# gradient/parlama yasak — MARKA_NOTU.md §4; kablo-alanlarından bağımsızdır.
# Marka-yolu tek-tanımlıdır: MARK_SVG (30px panel) + FAVICON_HREF (sekme-ikonu)
# aynı path'ten türetilir — brand/sester-mark-v2.svg gömülü kopyası (Chain-S).
_MARK_PATH = (
    "M2940 10210 c-63 -15 -140 -38 -170 -50 -30 -12 -71 -28 -90 -35 -19 -8 -55 -25 -80 -39 -25 -14 -63 -35 -85 -47 -22 -12 -137 -117 -255 -233 -118 -116 -338 -332 -490 -481 -437 -428 -1191 -1185 -1240 -1245 -45 -55 -53 -67 -97 -150 -30 -55 -46 -98 -81 -215 l-27 -90 0 -675 c1 -665 1 -676 23 -753 22 -81 115 -280 164 -354 36 -53 2562 -2575 2647 -2643 71 -56 169 -106 276 -140 106 -34 310 -40 424 -11 164 41 270 109 459 295 142 139 153 156 203 311 17 55 19 93 19 446 l0 385 -25 50 c-16 31 -86 116 -184 220 -193 207 -274 284 -297 284 -45 0 -434 -378 -434 -422 1 -13 21 -48 45 -78 127 -156 147 -213 105 -289 -26 -45 -43 -55 -68 -42 -18 10 -518 512 -802 806 -507 524 -670 694 -696 725 -30 37 -424 449 -510 535 -28 27 -85 83 -127 122 -118 113 -111 80 -117 503 -7 479 -12 461 149 615 52 50 142 138 200 196 58 59 268 266 466 460 592 582 757 745 809 799 55 58 110 96 153 105 15 4 45 13 66 21 31 12 187 14 946 14 l909 0 48 -32 c93 -63 89 -39 89 -574 0 -316 -3 -475 -11 -487 -11 -19 -382 -395 -527 -534 -47 -46 -93 -83 -101 -83 -8 0 -54 43 -103 95 -48 53 -112 114 -141 136 -60 46 -183 93 -219 84 -14 -3 -60 9 -125 35 -57 22 -132 46 -168 54 -36 8 -105 24 -155 36 -108 26 -377 38 -467 22 -70 -14 -298 -123 -358 -173 -25 -20 -70 -50 -100 -66 -114 -60 -127 -71 -334 -267 -186 -176 -233 -245 -261 -377 -12 -60 -15 -152 -15 -474 0 -454 -7 -411 90 -520 166 -185 433 -460 461 -476 18 -9 36 5 161 128 255 251 308 308 308 332 0 15 -26 51 -71 99 -127 136 -156 197 -130 275 16 48 40 67 97 73 l49 6 45 -68 c57 -87 121 -163 200 -239 34 -33 105 -114 158 -180 148 -186 211 -256 405 -454 98 -101 212 -225 252 -275 39 -50 157 -180 261 -289 104 -109 263 -280 354 -381 91 -101 219 -240 285 -310 175 -184 166 -153 164 -596 -1 -270 -5 -368 -16 -408 -14 -52 -33 -72 -857 -893 -691 -689 -852 -845 -897 -867 l-54 -27 -923 -3 c-635 -2 -936 1 -963 8 -59 16 -116 72 -126 123 -4 23 -6 249 -3 503 l5 461 36 44 c21 24 125 133 232 243 l195 198 64 -11 c41 -7 75 -8 96 -1 77 21 294 208 368 316 37 53 37 56 24 92 -7 20 -12 55 -11 78 3 57 -12 73 -422 486 -324 327 -347 348 -381 348 -31 0 -49 -13 -148 -105 -173 -162 -235 -222 -333 -325 -50 -52 -196 -198 -324 -325 -366 -361 -411 -425 -488 -705 -16 -59 -18 -129 -21 -792 -2 -407 1 -755 6 -790 28 -186 110 -370 235 -521 114 -138 155 -174 272 -248 175 -110 310 -162 483 -188 100 -15 2279 -15 2371 0 126 20 251 61 361 118 134 70 184 115 731 658 1423 1413 1367 1354 1461 1509 29 46 66 135 91 219 35 114 39 207 35 850 l-4 630 -26 82 c-37 113 -98 242 -154 321 -26 37 -111 130 -188 207 -245 243 -524 535 -578 602 -25 32 -28 44 -28 108 0 83 -29 233 -60 315 -41 106 -135 280 -160 295 -5 3 -10 15 -10 26 0 49 110 166 673 713 197 191 352 351 371 380 45 73 103 195 126 268 38 122 41 197 38 948 l-3 725 -24 70 c-68 197 -103 265 -207 396 -122 156 -260 272 -419 352 -130 66 -154 74 -291 102 l-123 25 -1123 -1 -1123 -1 -115 -28z m749 -2807 c54 -37 57 -38 135 -35 l81 3 90 -73 c50 -39 115 -99 145 -131 30 -33 87 -94 126 -136 39 -42 88 -101 109 -131 21 -30 99 -115 172 -187 76 -75 140 -148 148 -168 8 -19 15 -65 15 -102 0 -37 7 -86 15 -108 18 -51 18 -65 2 -65 -34 0 -329 263 -409 365 -49 61 -280 308 -444 472 -104 104 -216 229 -262 294 -15 19 -9 39 11 39 7 0 36 -17 66 -37z M3158 5586 c-214 -202 -245 -238 -232 -272 20 -51 483 -524 513 -524 11 0 34 12 53 27 51 43 169 146 208 182 19 18 72 59 118 92 61 45 82 66 82 83 0 14 -24 50 -57 89 -217 250 -456 497 -482 497 -11 0 -98 -74 -203 -174z"
)
_MARK_TRANSFORM = "translate(65.6,0) scale(0.1894) translate(0,1056) scale(0.1,-0.1)"
MARK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" '
    'width="30" height="30">'
    '<g transform="' + _MARK_TRANSFORM + '" fill="#171717" stroke="none">'
    '<path d="' + _MARK_PATH + '"/></g>'
    "</svg>"
)
# Favicon: 64-kare parşömen-zemin + mürekkep marka (data-URI — ek-route yok)
_FAV_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
    '<rect width="200" height="200" rx="28" fill="#F5F0E4"/>'
    '<g transform="' + _MARK_TRANSFORM + '" fill="#171717" stroke="none">'
    '<path d="' + _MARK_PATH + '"/></g>'
    "</svg>"
)
FAVICON_HREF = "data:image/svg+xml;base64," + base64.b64encode(
    _FAV_SVG.encode()).decode()


PAGE = """<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<title>SESTER · Panel</title>
<link rel="icon" type="image/svg+xml" href="{favicon}">
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
<link rel="icon" type="image/svg+xml" href="{favicon}">
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
                                     ttl=ttl, content=content, favicon=FAVICON_HREF)


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
        favicon=FAVICON_HREF,
        agent_rows="".join(agent_rows),
        event_rows="".join(event_rows),
        chain_status=('<span class="ok">SAĞLAM ✓</span>' if chain_ok
                      else '<span class="bad">KIRILMIŞ — müdahale!</span>'),
        total_events=events[0]["seq"] if events else 0,
    )
