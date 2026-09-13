"""PUGIO facilitator — x402 v2 verify/settle istemcisi (v0.2).

x402 'authorization' akışı (docs.x402.org/schemes/exact, teyit 2026-09-12):
  verify  — ödeme-zarfı doğrulanır (zincir-hareket ETMEDEN, handler'dan önce)
  settle  — handler başarılıysa zincir-hareketi kesinleşir (sonradan)

Taşıma-katmanı enjektabl: gerçek HTTP istemcisi + testler için sahte taşıma.
Mimari kural: facilitator ERİŞİLEMEZSE ödeme "unknown" kabul edilir ve istek
RETREDİLİR (fail-closed) — asla açık-kapı bırakılmaz (KARAR_63B §5).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


class FacilitatorError(Exception):
    """Ağ/protokol hatası — arayan taraf fail-closed reddine çevirir."""


@dataclass(frozen=True)
class FacilitatorResult:
    ok: bool
    status: str                 # "ok" | "rejected" | "unknown"
    reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class Transport(Protocol):
    def post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class UrllibTransport:
    """Gerçek HTTP taşıması (stdlib; ek bağımlılık yok)."""

    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout

    def post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            raise FacilitatorError(f"facilitator erişilemedi: {e}") from e


class FakeTransport:
    """Test taşıması: scripted sonuçlar. pending list settle-açısını simüle eder."""

    def __init__(self, verify_results: list[dict[str, Any]] | None = None,
                 settle_fail_first: int = 0) -> None:
        self.verify_results = list(verify_results or [])
        self.settle_fail_first = settle_fail_first
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((url, payload))
        if url.endswith("/verify"):
            r = self.verify_results.pop(0) if self.verify_results else {"ok": True}
        else:  # settle
            if self.settle_fail_first > 0:
                self.settle_fail_first -= 1
                r = {"ok": False, "error": "transient_settle"}
            else:
                r = {"ok": True, "settlement": "0x" + "be" * 32}
        if not r.get("ok"):
            return {"ok": False, "error": r.get("error", "rejected"),
                    "status": r.get("status", "rejected")}
        return r


class Facilitator:
    """x402 v2 uçları. base_url örn. https://x402.org/facilitator."""

    def __init__(self, base_url: str, transport: Transport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.transport = transport or UrllibTransport()

    def verify(self, envelope: dict[str, Any]) -> FacilitatorResult:
        try:
            raw = self.transport.post_json(f"{self.base_url}/verify", envelope)
        except FacilitatorError as e:
            return FacilitatorResult(False, "unknown", str(e))
        if raw.get("ok"):
            return FacilitatorResult(True, "ok", raw=raw)
        return FacilitatorResult(False, "rejected",
                                 str(raw.get("error", "rejected")), raw)

    def settle(self, envelope: dict[str, Any]) -> FacilitatorResult:
        try:
            raw = self.transport.post_json(f"{self.base_url}/settle", envelope)
        except FacilitatorError as e:
            return FacilitatorResult(False, "unknown", str(e))
        if raw.get("ok"):
            return FacilitatorResult(True, "ok", raw=raw)
        return FacilitatorResult(False, "rejected",
                                 str(raw.get("error", "rejected")), raw)
