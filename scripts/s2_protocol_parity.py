"""S2 kabul-senaryosu (IS_PLANI §7): aynı işlem dört-protokol-yolundan
e geçer → aynı ChargeReceipt çekirdeği.

Senaryo: TEK mantıksal işlem (ajan-cüzdan, /weather, 0.05) dört protokol-yolundan
geçirilir:
  1) pugio0        — SESTER HMAC şeması (x402-uyum el sıkışma; DONUK ad)
  2) AP2           — mandate-simülatörü (AP2-Mandate zarfı)
  3) ACP           — checkout-session-simülatörü (ACP-Session zarfı)
  4) UCP           — satıcı-mühürlü web-monetization (UCP-Checkout zarfı)

Kabul: dördü de 200; ChargeReceipt çekirdek-alanları birebir aynı
(agent, resource, amount); tek ledger'da tek sayaç (spent 0.20);
zincir SAĞLAM. Fark yalnız şema-adı ve nonce'ta (kanıt-takip için).

Çalıştır:  .venv/bin/python scripts/s2_protocol_parity.py
Çıkış:     0 = KABUL, 1 = RED (fail-loud)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac as hmac_mod
import json
import secrets
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sester.adapters import (install_adapters, issue_ucp_checkout,
                            protocol_intent_event, sign_mandate_jws)
from sester.ledger import Ledger
from sester.middleware import MINOR, SesterMeter

SECRET = "s2-parity-secret"
PRICE = 0.05
QUOTA = 25.0
WALLET = "0xs200000000000000000000000000000000000000"
RESOURCE = "/weather"


AP2_SECRET = b"s2-ap2"


def _ap2_header(amount_minor: int) -> str:
    t = time.time()
    mandate = {
        "mandate_id": f"man-{secrets.token_hex(6)}",
        "agent": WALLET,
        "principal": "did:user:gokun",
        "valid_from": t - 10,
        "valid_to": t + 3600,
        "scope": {"resource_prefixes": [RESOURCE],
                  "per_request_max_minor": 100_000, "currency": "USDC"},
    }
    mandate["signature"] = sign_mandate_jws(mandate, alg="HS256",
                                            key=AP2_SECRET, kid="s2-ap2")
    raw = base64.urlsafe_b64encode(json.dumps(mandate).encode()).decode().rstrip("=")
    return f"AP2-Mandate {raw}", mandate["mandate_id"]


def _acp_header(amount_minor: int) -> str:
    session = {
        "session_id": f"sess-{secrets.token_hex(6)}",
        "buyer": WALLET,
        "valid_to": time.time() + 3600,
        "line_item": {"resource": RESOURCE, "amount_minor": amount_minor,
                      "currency": "USDC"},
    }
    raw = base64.urlsafe_b64encode(json.dumps(session).encode()).decode().rstrip("=")
    return f"ACP-Session {raw}", session["session_id"]


UCP_MERCHANT_SECRET = b"s2-ucp-merchant"
UCP_MERCHANT_ID = "s2-merchant"


def _ucp_header() -> tuple[str, str]:
    header = issue_ucp_checkout(
        intent_id=f"ucp-{secrets.token_hex(6)}", buyer=WALLET,
        merchant=UCP_MERCHANT_ID, resource=RESOURCE,
        amount_minor=int(round(PRICE * MINOR)), key=UCP_MERCHANT_SECRET,
        kid="s2-merchant-1")
    return header, header.split(" ", 1)[1]  # nonce = intent_id (zarf-içi)


def _hmac_header(nonce: str) -> str:
    amount_s = f"{PRICE:.2f}"
    mac = hmac_mod.new(SECRET.encode(), f"{WALLET}|{nonce}|{amount_s}|{RESOURCE}".encode(),
                       hashlib.sha256).hexdigest()
    return f"pugio0 {WALLET}:{nonce}:{amount_s}:{mac}", nonce


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="s2-"))
    led = Ledger(tmp / "s2.sqlite3", secret=SECRET)
    meter = SesterMeter(None, led, price=PRICE, daily_quota=QUOTA, secret=SECRET)
    install_adapters(meter.register_scheme, price_minor=meter.price_minor,
                     on_intent=lambda it: led.append(
                         "protocol_intent", it.agent, it.resource, 0.0,
                         payload=protocol_intent_event(it)),
                     key_resolver=lambda kid, alg: {
                         "s2-ap2": AP2_SECRET,
                         "s2-merchant-1": UCP_MERCHANT_SECRET}[kid],
                     ucp_merchant=UCP_MERCHANT_ID, require_ucp_signature=True)

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})

    meter.app = app

    async def call(payment: str):
        out = []
        scope = {"type": "http", "path": RESOURCE,
                 "headers": [(b"x-payment", payment.encode())]}

        async def send_fn(m):
            out.append(m)

        await meter(scope, None, send_fn)
        hdrs = {k.decode().lower(): v.decode() for k, v in out[0].get("headers", [])}
        return out[0]["status"], hdrs

    amount_minor = int(round(PRICE * MINOR))
    flows = [
        ("x402/pugio0", *_hmac_header(f"s2-{secrets.token_hex(4)}")),
        ("AP2-mandate", *_ap2_header(amount_minor)),
        ("ACP-session", *_acp_header(amount_minor)),
        ("UCP-checkout", *_ucp_header()),
    ]

    results = []
    for name, header, nonce in flows:
        status, hdrs = asyncio.run(call(header))
        results.append((name, status, hdrs))
        rec = hdrs.get("x-sester-receipt", "-")
        amt = hdrs.get("x-sester-amount", "-")
        print(f"{name:12s} → {status}  receipt={rec}  amount={amt}")

    ok = all(s == 200 for _, s, _ in results)
    receipts = [h.get("x-sester-receipt") for _, _, h in results]
    amounts = {h.get("x-sester-amount") for _, _, h in results}
    ok = ok and all(receipts) and len(set(receipts)) == 4 and amounts == {f"{PRICE:.6f}"}

    # Çekirdek-parite: ledger'da aynı ajan+host+tutar, dört charge_receipt
    rows = [r for r in led.recent_events(30) if r["event_type"] == "charge_receipt"]
    core = {(r["agent_id"], r["host"], round(r["amount"], 6)) for r in rows}
    ok = ok and len(rows) == 4 and core == {(WALLET, RESOURCE, PRICE)}

    spent = led.spent_today(WALLET)
    print(f"\nOrtak sayaç: {spent:.2f} (beklenen {4 * PRICE:.2f}) — "
          f"{'OK' if abs(spent - 4 * PRICE) < 1e-9 else 'HATA'}")
    print(f"Zincir: {'SAĞLAM' if led.verify_chain() else 'KIRIK'}")
    ok = ok and abs(spent - 4 * PRICE) < 1e-9 and led.verify_chain()

    print(f"\nS2 KABUL: dört protokol → aynı ChargeReceipt çekirdeği "
          f"(agent={WALLET[:10]}…, host={RESOURCE}, amount={PRICE})" if ok
          else "\nS2 RED: parite bozuk — yukarıdaki satırlara bak")
    led.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
