# SESTER Vitrin Rehberi — kendi API'ne sayaç+politika tak (15 dakika)

> Hedef kitle: API'sini ajanlara satmak isteyen geliştirici. Çıktı: her istekte
> 402-el sıkışması + imzalı kanıt + günlük kota + fail-closed politika + panel.

## 1) Kurulum

```bash
pip install sester[demo]        # çekirdek + demo sunucusu
# EVM-imza doğrulaması için: pip install sester[evm]
```

## 2) 5 satırda bağla

```python
from fastapi import FastAPI
from sester.ledger import Ledger
from sester.middleware import SesterMeter

app = FastAPI()
ledger = Ledger("benim-api.sqlite3", secret="ortam-değişkeninden-al")

app.add_middleware(SesterMeter, ledger=ledger, price=0.02,
                   daily_quota=10.0, secret="ortam-değişkeninden-al",
                   pay_to="0xCüzdanAdresin")

@app.get("/veri")
def veri(): return {"deger": 42}
```

Not: `add_middleware` ASGI-katmanında sarar; `/panel`, `/healthz`, `/agents.json`
varsayılan muaf. Korunan endpoint'ler: ödemesiz → **402 + X-Payment-Required**.

## 3) Ajan-tarafı imza (EVM, önerilen)

```python
from sester.schemes import sign_exact_sester
from eth_account import Account

sk = "0x..."                                   # ajan-cüzdanı (non-custodial: sende)
addr = Account.from_key(sk).address.lower()
header = sign_exact_sester(sk, addr, "nonce-1", "0.02", "/veri")
# → curl -H "X-Payment: <header>" http://localhost:8000/veri
# ← 200 + X-Sester-Receipt (hash-chain kanıtı)
```

HMAC geri-uyumu (`pugio0` şeması — DONUK kablo-alanı, ESKI_KIMLIK.md) test/iç-
dogfood için durur; canlıda EVM (`exact-sester`).

## 4) Politika (KURAL_DSL v0)

`examples/f1_policy.json` kopyala → host-listeni/kurallarını yaz → `policy_guard`
örneğini `sester/demo_api.py`'den al. Fail-closed sözü: dosya bozulursa **hiçbir
harcama geçmez** (DenyAll) — panelde zincir-rozeti kırmızıya döner.

## 5) Vitrin-checklist (PRD §3 benimseme-testi)

- [ ] Demo API'sine kendi ajanın ücretli istek attı, receipt düştü
- [ ] Kota aşımı 402 döndürdü
- [ ] Panelde ajan-satırı + SAĞLAM rozeti
- [ ] (Vitrin-kaydı) `docs/adoption_log.md`'e tarih + repo + demo-linki

## Sınırlar (v0.1 — KARAR_63B §4)

Gerçek zincir-settle yok (facilitator hattı v0.2); nonce kalıcı-tabloda;
HMAC şeması yalnız geri-uyum. Parayı asla tutmayız — non-custodial.
