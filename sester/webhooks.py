"""SESTER webhooks — v0.6.0 adım-3: kanıt-olaylarının imzalı dışa-akışı.

Üretici:
    payload = {"event_id", "type", "agent", "resource", "amount", "seq", "hash", "ts"}
    başlıklar:
      X-Sester-Signature: t=<unix>, v1=<hex-hmac-sha256(secret, f"{t}.{body}")>
Alıcı (spec-only doğrulama; sıfır-import — K0 §7 disiplini):
    verify_webhook(secret, body, x_sester_signature, *, tolerance=300)
      → (ok: bool, reason: str)
    · timestamp-penceresi (varsayılan ±300 sn) → replay penceresi kapanır
    · constant-time imza-karşılaştırma
    · imza-satırı bozuksa RED (fail-loud, sessiz-geçiş yok)

Gönderici:
    deliver_webhook(url, secret, event, *, post=None, retries=3, backoff=1.0)
    · post enjekte-edilebilir (varsayılan urllib.request); test-fake ile
      uçtan-uca koşulur
    · retry 3× (1s/2s/4s backoff); tüm-denenler-başarısız → ledger'a
      `webhook_delivery` failure-olayı (denetim-izi; sessiz-düşüş yok)
    · secret boşsa RED (imzasız gönderim yok — üretim-disiplini)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable

__all__ = ["build_webhook_payload", "sign_webhook", "verify_webhook",
           "deliver_webhook"]

_SIGNATURE_PREFIX = "t="
_VERSION_TAG = "v1="


def build_webhook_payload(rec: dict[str, Any]) -> dict[str, Any]:
    """Ledger-satırını webhook-yüküne çevir (yalnız kamusal-alanlar).

    Hem tam-satırı (`export_events` sözlüğü) hem `append` dönüşünü
    ({seq, ts, hash, prev_hash}) kabul eder — eksik-alan nötr-default.
    """
    return {
        # AT-184-BULGU-1: stabil-DEDUP-anahtarı — alıcı-çift-teslimi-ayırt-edip
        # reddedebilir ( retry-ack-kaybı/partition-ardışı-yeniden-gönderim).
        # seq+kaynak+hash'ten-türetilir ( aynı-event → aynı-id; deterministic).
        "event_id": f"{rec.get('seq', 0)}:{rec.get('agent_id', '')}:"
                    f"{rec.get('hash', '')[:16]}",
        "type": rec.get("event_type", ""),
        "agent": rec.get("agent_id", ""),
        "resource": rec.get("host", ""),
        "amount": rec.get("amount", 0.0),
        "seq": rec.get("seq", 0),
        "hash": rec.get("hash", ""),
        "ts": rec.get("ts", time.time()),
    }


def sign_webhook(secret: str, body: bytes, *, ts: float | None = None) -> str:
    """`t=<unix>, v1=<hmac>` başlık-değeri (Stripe-sözdizisi-tarzı, kendi-şeması)."""
    if not secret:
        raise ValueError("webhook secret boş — imzasız gönderim yok (fail-closed)")
    t = int(time.time() if ts is None else ts)
    mac = hmac.new(secret.encode(), f"{t}.".encode() + body,
                   hashlib.sha256).hexdigest()
    return f"{_SIGNATURE_PREFIX}{t}, {_VERSION_TAG}{mac}"


def verify_webhook(secret: str, body: bytes, x_sester_signature: str, *,
                   tolerance: float = 300.0, now: float | None = None) -> tuple[bool, str]:
    """Alıcı-tarafı doğrulama — spec-only, sıfır-import (karşı-taraf kopyalayabilir)."""
    if not secret or not x_sester_signature:
        return False, "imza-başlığı/secret eksik"
    try:
        parts = dict(
            piece.strip().split("=", 1)
            for piece in x_sester_signature.split(",")
        )
        t = int(parts["t"])
        v1 = parts["v1"].strip().lower()
    except (ValueError, KeyError):
        return False, "imza-satırı bozuk (beklenen: t=<unix>, v1=<hex>)"
    current = time.time() if now is None else now
    if abs(current - t) > tolerance:
        return False, "timestamp pencere-dışı (replay koruması)"
    expected = hmac.new(secret.encode(), f"{t}.".encode() + body,
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, v1):
        return False, "imza uyuşmuyor"
    return True, "ok"


def deliver_webhook(
    url: str,
    secret: str,
    event: dict[str, Any],
    *,
    post: Callable[[str, bytes, dict[str, str]], int] | None = None,
    retries: int = 3,
    backoff: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Olayı imzalı POST-la; retry+backoff; sonunda da başarısızsa RED-dön.

    post(url, body, headers) → HTTP-status (>=200 <300 başarılı sayılır).
    Dönüş: {"ok": bool, "attempts": n, "status": son-status, "error": ...}
    (ledger-yazısı çağıranın işi — bu modül sıfır-import kalır.)
    """
    body = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = sign_webhook(secret, body)
    headers = {"Content-Type": "application/json",
               "X-Sester-Signature": sig}
    poster = post or _default_post
    last_status, last_error = 0, ""
    for attempt in range(1, retries + 1):
        try:
            status = poster(url, body, headers)
            if 200 <= status < 300:
                return {"ok": True, "attempts": attempt, "status": status}
            last_status, last_error = status, "http-error"
        except Exception as e:  # ağ-hatası: retry (fail-loud sonunda)
            last_status, last_error = 0, f"{type(e).__name__}: {e}"
        if attempt < retries:
            sleep(backoff * (2 ** (attempt - 1)))
    return {"ok": False, "attempts": retries,
            "status": last_status, "error": last_error}


def _default_post(url: str, body: bytes, headers: dict[str, str]) -> int:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (URL sahibinin)
        return resp.status
