#!/usr/bin/env python3
"""SESTER FastAPI entegrasyon örneği — müşteri tarafı.

Issue #4: bir agent'ın SESTER ödeme kapısını (x402 simülasyonu) FastAPI
üzerinden nasıl kullandığını uçtan uca gösterir. Bu dosya bir **demo
istemcisidir**: SESTER'in kendi demo API'sini çağırır, ödeme başlığını
gönderir ve reddedildiğinde geri çekilir.

Çalıştırma (demo API önceden ayağa kalkmış olmalı):

    pip install "sester[demo]" fastapi uvicorn httpx
    uvicorn sester.demo_api:app --port 8402   # ayrı terminalde
    python examples/fastapi_client_demo.py

Akış:
    1. agent ücretli `/weather` endpoint'ine X-Payment başlığı ile istek atar;
    2. middleware (SesterPolicyMeter) başlığı doğrular, ücreti cüzdanından
       düşer ve policy'ye (examples/f1_policy.json) sorar;
    3. *allow* → veri gelir; *deny* → 402 döner, istek hiç işlenmez;
       *escalate* → insan onay kuyruğuna düşer (demo'da önceden onaylanmış
       olabilir).

Üretimde bu örneği kullanma: demo-secret ve demo-kotası değerlendirme
içindir. Gerçek bir entegrasyon kendi cüzdan anahtarınızı ve
`SESTER_DEMO_SECRET`'ınızı kullanır.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Örnek repo kökünden import için (pip install -e . yapmadan çalışır).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx

# Demo API varsayılanları (docker compose up / uvicorn sester.demo_api:app)
GATEWAY = os.environ.get("SESTER_EXAMPLE_GATEWAY", "http://127.0.0.1:8402")
AGENT = os.environ.get("SESTER_EXAMPLE_AGENT", "demo-agent")
SECRET = os.environ.get("SESTER_DEMO_SECRET", "sester-demo-secret-v0")
PRICE = 0.05  # demo fiyatı — gateway'in PRICE'ı ile aynı tutulur


def _payment_header(resource: str) -> str:
    """Demo X-Payment başlığı: EIP-191 imzalı `Sester-EVM` jetonu.

    Bu, gateway'in duyurduğu `exact-sester` şemasının istemci tarafıdır:
    ajan, kaynak+nonce+tutar mesajını özel anahtarıyla imzalar. Demo anahtar
    (`0xd3..`) demo API'si ile aynı SADDE-demo-anahtardır; üretimde kendi
    cüzdan anahtarınızı kullanırsınız.
    """
    from eth_account import Account
    from sester.schemes import sign_exact_sester

    # Demo secret key — demo_api --evm ile aynı SADDE-demo-anahtarı.
    sk = "0x" + "d3" * 32
    agent = Account.from_key(sk).address
    # Nonce her istekte benzersiz olmalı: gateway replay koruması tutar
    # (aynı nonce ile ikinci ödeme reddedilir). Üretimde bunu bir monoton
    # sayaç veya UUID ile üretin.
    nonce = f"example-{os.getpid()}-{int(time.time() * 1000)}"
    return sign_exact_sester(sk, agent, nonce, f"{PRICE:.6f}", resource)


def paid_get(client: httpx.Client, path: str) -> dict | None:
    """Bir ücretli istek yap; reddedilirse temiz şekilde çık.

    Gateway'e X-Payment başlığını gönderir. Yanıt ya veriyi taşır ya da
    402 Payment Required ile gelir (fail-closed: kapı reddettiyse veri yok).
    """
    r = client.get(
        f"{GATEWAY}{path}",
        headers={"X-Payment": _payment_header(path.split("?")[0])},
        timeout=10,
    )

    if r.status_code == 200:
        return r.json()
    if r.status_code == 402:
        # Fail-closed: ödenmeyen/geri çevrilen istek veri döndürmez.
        try:
            body = r.json()
        except json.JSONDecodeError:
            body = {"raw": r.text[:120]}
        print(f"  ✗ reddedildi (402): {body.get('error', body)}")
        return None

    raise RuntimeError(f"gateway hatası {r.status_code}: {r.text[:120]}")


def main() -> int:
    print(f"SESTER FastAPI örnek istemci — gateway {GATEWAY}, agent {AGENT}")

    with httpx.Client() as client:
        try:
            data = paid_get(client, "/weather?sehir=istanbul")
        except RuntimeError as exc:
            print(f"  istek başarısız: {exc}", file=sys.stderr)
            return 1

        if data:
            print(f"  ✓ ödeme onaylandı: {data}")
        else:
            print("  ✓ kapı reddetti (kota dolu olabilir) — istek yapılmadı")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
