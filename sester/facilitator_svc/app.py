"""FastAPI yüzeyi — S5 (yalnız `[facilitator]` extra'sı; çekirdek 0-bağımlılık).

Uçlar (docs/S5_FACILITATOR_MILESTONE.md §2):
  POST /verify   {payment, resource}                → status/reason
  POST /settle   {payment, resource, amount_minor}  → status/receipt/metering
  GET  /panel    satıcı-faturaları (dogfood-görünürlüğü)
  GET  /healthz  sürüm + zincir-durumu (fail-closed sinyali)

Kimlik-doğrulama: `X-Facilitator-Key` — sabit-zaman karşılaştırma; bozuk/eksik
→ 401 (fail-loud; test_194).
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
from typing import Any

from .. import __version__ as pkg_version
from ..ledger import Ledger
from .service import FacilitatorService

try:
    from fastapi import FastAPI, Header, HTTPException
    from pydantic import BaseModel
except ImportError as e:  # pragma: no cover - fail-loud
    raise ImportError(
        "facilitator_svc için fastapi gerekir: pip install 'sester[facilitator]'"
    ) from e


class VerifyReq(BaseModel):
    payment: str
    resource: str


class SettleReq(BaseModel):
    payment: str
    resource: str
    amount_minor: int


class RefundReq(BaseModel):
    payment: str
    resource: str
    amount_minor: int
    reason: str = ""
    dispute_ref: str = ""


def create_app(ledger: Ledger, *, secret: str = "facilitator-secret",
               auth_key: str | None = None) -> FastAPI:
    """Servis + HTTP yüzeyi. auth_key verilmezse secret'tan türetilir."""
    svc = FacilitatorService(ledger, secret=secret)
    key = (auth_key or hashlib.sha256(
        f"facilitator-key:{secret}".encode()).hexdigest())

    app = FastAPI(title="SESTER Facilitator", version=pkg_version)

    def _guard(x_key: str | None) -> None:
        if not x_key or not hmac_mod.compare_digest(x_key, key):
            raise HTTPException(status_code=401, detail="auth-key geçersiz")

    @app.post("/verify")
    def verify(req: VerifyReq,
               x_facilitator_key: str | None = Header(default=None)) -> dict:
        _guard(x_facilitator_key)
        d = svc.verify(req.payment, req.resource)
        return {"status": d.status, "reason": d.reason}

    @app.post("/settle")
    def settle(req: SettleReq,
               x_facilitator_key: str | None = Header(default=None)) -> dict:
        _guard(x_facilitator_key)
        if req.amount_minor < 0:
            raise HTTPException(status_code=422, detail="amount_minor negatif")
        d = svc.settle(req.payment, req.resource, req.amount_minor)
        return {"status": d.status, "reason": d.reason, **(d.receipt or {})}

    @app.post("/refund")
    def refund(req: RefundReq,
               x_facilitator_key: str | None = Header(default=None)) -> dict:
        """S6 §2: settle-edilmiş nonce için ters-yazım (dispute-kanıtlı)."""
        _guard(x_facilitator_key)
        if req.amount_minor < 0:
            raise HTTPException(status_code=422, detail="amount_minor negatif")
        d = svc.refund(req.payment, req.resource, req.amount_minor,
                       reason=req.reason, dispute_ref=req.dispute_ref)
        return {"status": d.status, "reason": d.reason, **(d.receipt or {})}

    @app.get("/panel")
    def panel(x_facilitator_key: str | None = Header(default=None)) -> dict:
        _guard(x_facilitator_key)
        sellers: dict[str, dict[str, Any]] = {}
        for r in ledger.export_events():
            if r["event_type"] == "facilitator_metering":
                sellers[r["agent_id"]] = svc.seller_invoice(r["agent_id"])
        return {"sellers": sellers}

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "version": pkg_version,
                "chain_valid": ledger.verify_chain()}

    app.state.service = svc
    return app
