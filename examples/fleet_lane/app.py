"""F1 filo-rayı — Sester'in ilk gerçek-kiracısı (dogfood şablonu).

Amaç: gerçek-iç-endpoint'in önüne Sester takmanın en-küçük-örneği.
Demo'yu kopyalamaz: kendi endpoint'ini sarar, filo-politikasıyla çalışır.

Çalıştırma (repo-kökünden):
    export SESTER_FLEET_SECRET="f1-fleet-secret-2026"
    uvicorn examples.fleet_lane.app:app --port 8410

Sonra (aynı klasördeki üretici-istemciyle):
    python examples/fleet_lane/send_paid_request.py --agent f1-n1

Ölçek-notu: süreç-içi tek-Ledger yeterli (SesterMeter'in kendi
kilit-diskiplini yazımları atomik yapar). Çok-süreçli filoda Ledger'ı
Postgres'e taşı (migrate_pg.py hash-korur).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import datetime as _dt

from sester.ledger import Ledger
from sester.middleware import SesterMeter
from sester.policy import DenyAll, Policy, PolicyCorruptError

DB_PATH = Path(
    os.environ.get("SESTER_FLEET_DB", "examples/fleet_lane/fleet.sqlite3"))
POLICY_PATH = Path(
    os.environ.get("SESTER_FLEET_POLICY", "examples/fleet_lane/policy.json"))
SECRET = os.environ.get("SESTER_FLEET_SECRET", "f1-fleet-secret-2026")
PRICE = float(os.environ.get("SESTER_FLEET_PRICE", "0.05"))
DAILY_QUOTA = float(os.environ.get("SESTER_FLEET_DAILY_QUOTA", "10.00"))


# ---- gerçek-iç-endpoint (örnek: F1-telemetri) --------------------------
# Kendi endpoint'ini buraya bağla: bu fonksiyonlar Sester'in ARKASINDA
# çalışır; yalnız geçerli-ödemeyle ulaşılmış olur.

def _json(status: int, payload: dict) -> tuple[int, bytes]:
    return status, json.dumps(payload, ensure_ascii=False).encode()


async def telemetry(scope):
    return _json(200, {
        "car": "f1-63", "lap": 44, "speed_kph": 312.4, "tyre": "C3",
        "note": "gerçek-endpoint'i buraya bağla",
    })


async def history(scope):
    return _json(200, {"laps": 44, "pits": 2, "best": "1:19.873"})


ROUTES = {"/telemetry": telemetry, "/history": history}


async def inner_router(scope, receive, send):
    handler = ROUTES.get(scope.get("path", ""))
    if handler is None:
        status, body = _json(404, {"error": "not_found"})
    else:
        status, body = await handler(scope)
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": body})


# ---- politika-katmanı (demo-deseni: SesterMeter alt-sınıfı) ------------

class _PolicyState:
    """Politika-dosyası her istekte mtime ile izlenir; bozuk/eksik → DenyAll."""

    _mtime: float | None = None
    _policy: Policy | DenyAll | None = None

    @classmethod
    def current(cls) -> Policy | DenyAll:
        try:
            mtime = POLICY_PATH.stat().st_mtime
        except OSError:
            cls._mtime, cls._policy = None, None
            return DenyAll()
        if cls._policy is None or cls._mtime != mtime:
            try:
                cls._policy = Policy.load(POLICY_PATH)
                cls._mtime = mtime
            except PolicyCorruptError:
                cls._policy = None
                return DenyAll()
        return cls._policy


class FleetPolicyMeter(SesterMeter):
    """Ödeme-kapısından ÖNCE politika-kapısı: her karar ledger'a."""

    def __init__(self, *args, now: _dt.datetime | None = None, **kw) -> None:
        # Test-determinizmi: politikanın hour_between penceresi gerçek-zamana
        # bağımlıdır — olmasaydı test takımı iş-saatleri dışında sessizce
        # kırmış olurdu. Sabit bir iş-saatleri anı enjekte edilebilsin.
        super().__init__(*args, **kw)
        self._now = now

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and not any(
            scope.get("path", "").startswith(p) for p in self.exempt_prefixes
        ):
            payment = self._header(scope, "X-Payment")
            if payment and payment.strip().split(" ", 1)[0] == self.VERSION:
                path = scope.get("path", "")
                agent = payment.split(" ", 1)[1].split(":")[0]
                policy = _PolicyState.current()
                d = policy.evaluate(self.price, path, now=self._now)
                if d.verdict != "allow":
                    await self._challenge(send, scope, f"policy_denied:{d.rule_id}")
                    self.ledger.append(
                        "policy_denied", agent, path, 0.0,
                        payload={"rule_id": d.rule_id})
                    return
        return await super().__call__(scope, receive, send)


# ---- Sester-önü --------------------------------------------------------

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
ledger = Ledger(DB_PATH, secret=SECRET)

app = FleetPolicyMeter(
    inner_router,
    ledger,
    price=PRICE,
    daily_quota=DAILY_QUOTA,
    secret=SECRET,
    pay_to="f1:treasury",
)
