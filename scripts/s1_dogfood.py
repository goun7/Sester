#!/usr/bin/env python3
"""PUGIO S1 kabul senaryosu (IS_PLANI §7): F1-botları dogfood.

Senaryo: f1-telemetri ajanı, günlük-$50-cap + 08:00–22:00 saat-aralığı
politikanın arkasına sokulur. Deterministik saat-enjeksiyonu ile:

  S1.a  10:00 — 5 × $9.99 ücretli çağrı → hepsi 200, kanıt zincire
  S1.b  10:00 — 6. çağrı → 402 quota_exceeded (günlük-$50-cap)
  S1.c  23:30 — saat-dışı ödemeli çağrı → 402 policy_denied (fail-closed)
  S1.d  bilinmeyen-host → 402 policy_denied (catch-all deny)
  S1.e  kanıt-bundle'ı üret → pür-sha256 harici-doğrulama → JSON'a yaz

Çıkış-kodu: tüm beklenen sonuçlar tutarsa 0 (CI-runnable kabul-testi).
Çalıştır: .venv/bin/python scripts/s1_dogfood.py
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pugio.evidence import bundle_json, produce_bundle, verify_bundle
from pugio.ledger import Ledger
from pugio.middleware import PugioMeter
from pugio.policy import Policy
from pugio.schemes import sign_exact_pugio
from eth_account import Account

PRICE = 9.99
DAILY_CAP = 50.0
AGENT_SK = "0x" + "c1" * 32
AGENT = Account.from_key(AGENT_SK).address.lower()

S1_POLICY = {
    "wallet_policy": {
        "id": "wpol-s1-f1-telemetri",
        "owner": "did:agent:kok:f1-treasury",
        "wallet": f"evm:{AGENT}",
        "defaults": {"currency": "USDC", "per_request_max": 10.0,
                     "daily_max": 50.0, "timezone": "Europe/Istanbul"},
        "rules": [
            {"id": "allow-weather-day", "when": {"host_in": ["/weather"],
                                                 "hour_between": ["08:00", "22:00"]},
             "then": "allow"},
            {"id": "deny-unknown", "when": {"host_in": []}, "then": "deny"},
        ],
    }
}


class S1State:
    """Senaryo-saati: politika-değerlendirmesi deterministik zamanla akar."""
    now = _dt.datetime(2026, 9, 12, 10, 0)


class S1Meter(PugioMeter):
    """KURAL_DSL kapısı + enjeksiyonlu saat (demo_api.policy_guard'ın S1 hâli)."""

    def __init__(self, *a, policy: Policy, **kw):
        super().__init__(*a, **kw)
        self.policy = policy

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and not any(
            scope.get("path", "").startswith(p) for p in self.exempt_prefixes
        ):
            payment = self._header(scope, "X-Payment")
            if payment and payment.strip().startswith("Pugio-EVM "):
                d = self.policy.evaluate(PRICE, scope.get("path", ""), now=S1State.now)
                self.ledger.append("permission_decision", "s1-ön-karar", scope.get("path", ""),
                                   payload={"decision": d.verdict, "rule_id": d.rule_id,
                                            "at": S1State.now.isoformat(timespec="minutes")})
                if d.verdict != "allow":
                    return await self._challenge(send, scope, f"policy_denied:{d.rule_id}")
        return await super().__call__(scope, receive, send)


async def dummy_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": b'{"veri": 42}'})


def call(meter, path, headers):
    messages: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        messages.append(m)

    scope = {"type": "http", "method": "GET", "path": path,
             "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    asyncio.run(meter(scope, receive, send))
    body = b"".join(m.get("body", b"") for m in messages[1:] if m["type"] == "http.response.body")
    return messages[0]["status"], (json.loads(body) if body else {})


def pay(nonce: str) -> dict[str, str]:
    return {"X-Payment": sign_exact_pugio(AGENT_SK, AGENT, nonce, f"{PRICE:.2f}", "/weather")}


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="pugio-s1-")
    ledger = Ledger(Path(tmp) / "s1.sqlite3", secret="s1-secret")
    policy = Policy.from_dict(S1_POLICY)
    meter = S1Meter(dummy_app, ledger, price=PRICE, daily_quota=DAILY_CAP,
                    policy=policy, pay_to=f"evm:{AGENT}")

    results: list[tuple[str, bool, str]] = []

    # S1.a — gün-içi 5 çağrı
    ok_a = True
    for i in range(5):
        st, _ = call(meter, "/weather", pay(f"s1-a{i}"))
        ok_a &= st == 200
    results.append(("S1.a  10:00 — 5×$9.99 çağrı → 200 (günlük-$49.95)", ok_a,
                    "kanıt: charge_receipt × 5"))

    # S1.b — 6. çağrı: kota
    st, body = call(meter, "/weather", pay("s1-b"))
    results.append(("S1.b  10:00 — 6. çağrı → 402 quota_exceeded", st == 402,
                    f"spent_today={body.get('spent_today')}"))

    # S1.c — saat-dışı
    S1State.now = _dt.datetime(2026, 9, 12, 23, 30)
    st, body = call(meter, "/weather", pay("s1-c"))
    results.append(("S1.c  23:30 — saat-dışı ödemeli → 402 policy_denied",
                    st == 402 and "policy_denied" in body.get("error", ""),
                    body.get("error", "")))

    # S1.d — bilinmeyen-host (gün-içi)
    S1State.now = _dt.datetime(2026, 9, 12, 12, 0)
    h = sign_exact_pugio(AGENT_SK, AGENT, "s1-d", f"{PRICE:.2f}", "/bilinmeyen")
    messages: list[dict] = []

    async def run_unknown():
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(m):
            messages.append(m)

        scope = {"type": "http", "method": "GET", "path": "/bilinmeyen",
                 "headers": [(b"x-payment", h.encode())]}
        await meter(scope, receive, send)

    asyncio.run(run_unknown())
    ubody = b"".join(m.get("body", b"") for m in messages[1:] if m["type"] == "http.response.body")
    ustatus = messages[0]["status"]
    results.append(("S1.d  bilinmeyen-host → 402 policy_denied (catch-all)",
                    ustatus == 402 and "policy_denied" in json.loads(ubody).get("error", ""),
                    ""))

    # S1.e — kanıt-bundle üret + harici-doğrula + yaz
    bundle = produce_bundle(ledger, agent_id=None)
    ok, msg = verify_bundle(bundle)
    out = Path("adoption")
    out.mkdir(exist_ok=True)
    bundle_path = out / "s1-kanit-bundle.json"
    bundle_path.write_text(bundle_json(bundle), encoding="utf-8")
    results.append(("S1.e  kanıt-bundle üret + pür-sha256 doğrula + yaz",
                    ok, f"{bundle_path} · {msg}"))

    # --- rapor ---
    print("\nPUGIO S1 — F1 dogfood kabul-koşusu")
    print("=" * 64)
    all_ok = True
    for name, ok, note in results:
        all_ok &= ok
        print(f" {'✓' if ok else '✗'} {name}")
        if note:
            print(f"      {note}")
    print("=" * 64)
    print("SONUÇ:", "KABUL — S1 canlı" if all_ok else "RED — senaryo bozuk")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
