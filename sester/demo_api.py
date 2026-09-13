"""SESTER demo — F1-botları dogfood senaryosu: politika + ücretli API tek süreç.

Çalıştır:  uvicorn sester.demo_api:app --port 8402
Deneyin:   curl http://127.0.0.1:8402/weather?sehir=istanbul         → 402 + challenge

EVM-imzalı (önerilen, eth-account gerekir):
           python -m sester.demo_api --evm n1 /weather
           curl -H "X-Payment: <üstteki satır>" "http://127.0.0.1:8402/weather"  → 200 + kanıt

HMAC geri-uyum (test/dogfood):
           python -m sester.demo_api --mac f1-telemetri:n1:0.05 /weather
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from .escalation import EscalationQueue
from .ledger import Ledger
from .middleware import SesterMeter
from .panel import APPROVALS_PAGE, render_panel
from .policy import DenyAll, Policy, PolicyCorruptError

SECRET = "sester-demo-secret-v0"
PRICE = 0.05
DAILY_QUOTA = 0.20  # demo-kotası bilinçli düşük: 5. çağrıda kota-aşımı görülür
POLICY_PATH = Path("examples/f1_policy.json")
# DB-yolları env ile taşınabilir (test-izolasyonu: conftest tmp-yola alır)
ESC_DB = os.environ.get("SESTER_ESCALATION_DB", "sester-escalation.sqlite3")
DEMO_DB = os.environ.get("SESTER_DEMO_LEDGER_DB", "sester-demo.sqlite3")

ledger = Ledger(DEMO_DB, secret=SECRET)
esc_queue = EscalationQueue(ESC_DB, ledger=ledger)


class _PolicyState:
    """Fail-closed politika-durumu: dosya her istekte mtime ile izlenir;
    değişimde yeniden doğrulanır; bozuk/eksik → DenyAll (tüm harcama durur).
    KURAL_DSL_V0 §4 'kural dosyası bozuksa → harcama durur' canlı-semantiği."""

    def __init__(self) -> None:
        self.mtime: float | None = self._stat()
        self.engine: Policy | DenyAll = self._load()

    @staticmethod
    def _stat() -> float | None:
        try:
            return POLICY_PATH.stat().st_mtime
        except OSError:
            return None  # dosya yok

    @staticmethod
    def _load() -> Policy | DenyAll:
        try:
            return Policy.load(POLICY_PATH)
        except PolicyCorruptError:
            return DenyAll()

    def current(self) -> Policy | DenyAll:
        m = self._stat()
        if m != self.mtime:
            self.mtime = m
            self.engine = self._load()
        return self.engine


_policy_state = _PolicyState()


def policy_guard(agent: str, path: str, amount: float) -> tuple[str, str]:
    """KURAL_DSL kapısı: per-request üst-sınırı + kural-semantiği; karar ledger'a.
    Politika dosyası her istekte izlenir: bozuk/eksik → DenyAll → hepsi reddedilir.
    Döner: (verdict, rule_id) — verdict allow/deny/escalate."""
    policy = _policy_state.current()
    d = policy.evaluate(amount, path)
    if amount > policy.per_request_max + 1e-9:  # DenyAll.per_request_max=0 → her şey reddedilir
        if d.verdict == "escalate":
            # politika bilinçli olarak insan-onayına gönderiyor: üst-sınırı
            # biletle aşabilir (her harcama tek-kezlik onay ister)
            verdict, rule = "escalate", d.rule_id
        else:
            verdict, rule = "deny", f"per_request_max({d.rule_id})"
    else:
        verdict, rule = d.verdict, d.rule_id
    ledger.append("permission_decision", agent, path,
                  payload={"decision": verdict, "rule_id": rule, "reason": d.reason})
    return verdict, rule


def _agent_of(payment: str, resource: str = "") -> str | None:
    """Ödeme-başlığından ajan-kimliği (politika-kararı için): EVM → adres, HMAC → etiket.
    EVM-imza kaynağa-bağlıdır — resource=gerçek istek-yolu OLMADAN doğrulama
    imkânsızdır; v0.4-düzeltmesi: ön-çözüm gerçek path'le yapılır (doğru
    atıf) ve dict-sonuçtan agent-dizgesi çıkarılır."""
    prefix = payment.strip().split(" ", 1)[0]
    if prefix == "Sester-EVM":
        from .schemes import PaymentError, verify_exact_sester

        try:
            d = verify_exact_sester(payment, resource)
            return str(d.get("agent"))
        except PaymentError:
            return None
    if prefix == "pugio0":
        rest = payment.strip()[len("pugio0 "):]
        return rest.split(":")[0] or None
    return None


class SesterPolicyMeter(SesterMeter):
    """Demo sarımı: x402 kapısına KURAL_DSL politikasını da bağlar (host=kaynak-yolu).
    v0.4: AP2/ACP/UCP adaptörleri de kurulu — dört-protokol canlı-akış; satıcı-
    sırrı/merchant env-override'lı (SESTER_UCP_SECRET / SESTER_UCP_MERCHANT);
    SESTER_DEMO_STRICT=1 → imzasız ACP/UCP zarfları fail-closed ret edilir."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        from .adapters import install_adapters

        ucp_secret = os.environ.get("SESTER_UCP_SECRET", "sester-demo-ucp").encode()
        ap2_secret = os.environ.get("SESTER_AP2_SECRET", "sester-demo-ap2").encode()
        strict = os.environ.get("SESTER_DEMO_STRICT", "") == "1"
        self._demo_secrets = {"sester-demo-ap2-1": ap2_secret,
                              "sester-demo-ucp-1": ucp_secret}
        install_adapters(
            self.register_scheme, price_minor=self.price_minor,
            key_resolver=lambda kid, alg: self._demo_secrets.get(kid),
            ucp_merchant=os.environ.get("SESTER_UCP_MERCHANT", "sester-demo"),
            require_ucp_signature=strict, require_acp_signature=strict,
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and not any(
            scope.get("path", "").startswith(p) for p in self.exempt_prefixes
        ):
            payment = self._header(scope, "X-Payment")
            if payment and payment.strip().split(" ", 1)[0] in ("Sester-EVM", "pugio0"):
                path = scope.get("path", "")
                agent = _agent_of(payment, path) or "bilinmeyen"
                verdict, rule = policy_guard(agent, path, self.price)
                if verdict == "escalate":
                    # insan-onay kuyruğu (KARAR_63B madde-3): onaylı bilet varsa
                    # bir-kezlik tüket → ödeme akışı; yoksa park + 402 escalate
                    approved = esc_queue.approved_for(agent, path)
                    if approved and esc_queue.consume(approved["esc_id"]):
                        ledger.append("escalation_consumed", agent, path, 0.0,
                                      payload={"esc_id": approved["esc_id"],
                                               "rule_id": rule})
                    else:
                        ticket = esc_queue.park(agent, path, self.price, rule)
                        return await self._challenge(
                            send, scope, f"escalation_required:{ticket['esc_id']}")
                elif verdict != "allow":
                    return await self._challenge(send, scope, f"policy_denied:{rule}")
        return await super().__call__(scope, receive, send)


app = FastAPI(title="SESTER demo API", version="0.5.0",
              description="x402-simülasyonlu ücretli endpoint — B-katmanı vitrini")
app.add_middleware(SesterPolicyMeter, ledger=ledger, price=PRICE,
                   daily_quota=DAILY_QUOTA, secret=SECRET,
                   exempt_prefixes=("/panel", "/healthz", "/agents.json", "/docs",
                                    "/openapi.json", "/redoc", "/favicon.ico",
                                    "/approvals", "/escalations", "/ucp/issue"))


@app.get("/healthz")
def healthz():
    return {"status": "ok", "chain_valid": ledger.verify_chain(), "version": "0.5.0"}


@app.get("/ucp/issue")
def ucp_issue(agent: str, resource: str = "/weather"):
    """Satıcı-ucu UCP-checkout üretimi (v0.4 dogfood): /.well-known/ucp akışının
    SESTER karşılığı — satıcı-mühürlü zarf döndürür; X-Payment'e koyup tekrar
    istek atın (merchant-bağı + [SESTER_DEMO_STRICT=1]'de imza-zorunlu)."""
    from .adapters import issue_ucp_checkout

    header = issue_ucp_checkout(
        intent_id=f"ucp-{os.urandom(4).hex()}", buyer=agent,
        merchant=os.environ.get("SESTER_UCP_MERCHANT", "sester-demo"),
        resource=resource, amount_minor=int(round(PRICE * 1_000_000)),
        key=os.environ.get("SESTER_UCP_SECRET", "sester-demo-ucp").encode(),
        kid="sester-demo-ucp-1")
    return {"payment_header": header,
            "usage": "X-Payment başlığına koyup aynı kaynağa tekrar istek atın"}


@app.get("/agents.json")
def agents_json():
    """64-agents.txt ile hizalı keşif-dosyası."""
    return {
        "agents": [{
            "id": "sester-demo",
            "protocol": "pugio0/x402-sim",
            "price": f"{PRICE} USDC-sim / istek",
            "quota": f"{DAILY_QUOTA} / ajan / gün",
            "policy": str(POLICY_PATH),
        }]
    }


@app.get("/escalations")
def escalations():
    """Bekleyen insan-onay biletleri (fail-closed TTL'li)."""
    return {"pending": esc_queue.pending(), "ttl_seconds": esc_queue.ttl}


@app.get("/approvals", response_class=HTMLResponse)
def approvals_page():
    """İnsan-onay paneli: bekleyen biletler + onayla/reddet butonları."""
    return HTMLResponse(APPROVALS_PAGE.render(
        esc_queue.pending(), esc_queue.ttl))


@app.post("/escalations/{esc_id}/decide")
def decide_escalation(esc_id: str, body: dict):
    """Onay/ret: {"approve": bool, "by": "...", "note": "..."}.
    Hata: 404 (bilet yok) / 409 (durum uygun değil) — fail-loud."""
    approve = body.get("approve")
    if not isinstance(approve, bool):
        return JSONResponse({"error": "approve boolean olmalı"}, status_code=400)
    try:
        ticket = esc_queue.decide(esc_id, approve=approve,
                                  by=str(body.get("by") or "panel"),
                                  note=str(body.get("note") or ""))
    except KeyError:
        return JSONResponse({"error": f"bilet yok: {esc_id}"}, status_code=404)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    return {"ok": True, "ticket": ticket}


@app.get("/weather")
def weather(sehir: str = "istanbul"):
    return {"sehir": sehir, "sicaklik": 24, "kaynak": "SESTER demo — ücretli veri"}


@app.get("/panel", response_class=HTMLResponse)
def panel():
    return HTMLResponse(render_panel(ledger, DAILY_QUOTA))


def _cli() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--mac":
        fields = sys.argv[2].split(":")
        if len(fields) != 3:
            print("kullanım: --mac <agent>:<nonce>:<amount> [path]")
            return 2
        agent, nonce, amount = fields
        path = sys.argv[3] if len(sys.argv) > 3 else "/weather"
        mac = hmac.new(SECRET.encode(), f"{agent}|{nonce}|{amount}|{path}".encode(),
                       hashlib.sha256).hexdigest()
        payment = f"pugio0 {agent}:{nonce}:{amount}:{mac}"
        print(payment)
        print(f"\n# curl şablonu:")
        print(f'curl -H "X-Sester-Agent: {agent}" -H "X-Payment: {payment}" \\')
        print(f'  "http://127.0.0.1:8402{path}"')
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] == "--evm":
        # --evm <nonce> [path] — demo EVM-anahtarıyla Sester-EVM başlığı üret
        from eth_account import Account

        from .schemes import sign_exact_sester

        nonce = sys.argv[2]
        path = sys.argv[3] if len(sys.argv) > 3 else "/weather"
        sk = "0x" + "d3" * 32  # SADECE demo — gerçek ajan kendi anahtarını kullanır
        agent = Account.from_key(sk).address.lower()
        print(sign_exact_sester(sk, agent, nonce, f"{PRICE:.2f}", path))
        print(f"\n# curl şablonu:")
        print(f'curl -H "X-Payment: <üstteki satır>" "http://127.0.0.1:8402{path}"')
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
