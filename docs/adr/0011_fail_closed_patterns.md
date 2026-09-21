# SESTER — Fail-closed desenleri: secret-yokluğu vs varsayılan-secret-yok

> Durum: **KABUL EDİLDİ** · Tarih: 2026-09-20 · Üst: `0007` (PRD), `docs/GITHUB_LEAK_AUDIT.md` (x402-bölümü)

## Bağlam

8-saatlik-otonom-turda üç-ürün karşılıklı denetiminde iki benzer-ama-**farklı** fail-closed deseni ortaya çıktı. Yüzeysel olarak ikisi de "zayıf-secret" gibi görünür — ama düzeltilecek yer sadece biri.

1. **Sester facilitator** (`sester/facilitator_svc/`): `create_app(ledger, secret="facilitator-secret")` hardcoded varsayılan-secret taşıyordu. `uvicorn --factory` argümansız çağrıldığında auth-key tahmin-edilebilir oluyor (refund-dahil uzaktan-yönetim-yüzeyi).

2. **Veridict** (`veridict/jury.py`): `os.environ["VERIDICT_JURY_KEY"]` KeyError ile **zorunlu** — ama opsiyonel API-key `VERIDICT_JURY_KEY` boş-defaultlu (`""`).

## Karar

**Sadece (1) düzeltildi.** (2) bilinçli-olarak-dokunulmadı (Veridict-ajan'ın doğrulamasıyla).

### Neden farklılar

| | Sester facilitator | Veridict jury-key |
|---|---|---|
| Sorun | **Varsayılan-secret var** — saldırgan-değer-biliyor | **Secret yok** — kimse-bilmiyor |
| Sömürü | Default-secret ile anonim-auth | Ücretli-gateway'de-anonymous-erişim |
| Doğal-davranış | Gateway secret'i-**kabul-eder** → GREEN-geçiş | Gateway secret'in-yokluğunu-**reddeder** → fail-closed |
| Kırılacak-akış | — (yeni-env-her-zemand-çalışır) | Local-Ollama-0.32.5 canary'leri (API-anahtarı-YOK) |

İkincisi "secret-sızıntısı" değil: sızan bir değer yok, **değerin yokluğu** var. Reddeeden taraf dış-gateway olduğu için sistem kendiliğinden fail-closed'dur. Zorunlu-hale-getirmek yerel-canary akışını kırardı — gerçek-LLM-receipt'leri (`docs/notes/real-llm-canary-*.json`) Ollama üzerinden koşuyor.

## Uygulanan-düzeltmeler (Sester-tarafı)

- `SESTER_FACILITATOR_SECRET` env'i-zorunlu; yoksa `RuntimeError` (fail-closed, **varsayılan-değer-yok**) — `test_193b` üç-yolu-kilitler
- `SESTER_DEMO_SECRET` env-override + sabit-secret-kullanımında-açılış-uyarısı (demo-ışığı-tutmak-için fail-değil)
- README env-tablosu: değişken-başına-fail-modu-belgeli (bkz. "Environment variables" bölümü)

## İzlenim

"Secret-yokluğu-güvenli-değil" yanlış-genelleme-yapar: **değer-dağıtılmış-olmadıkça** yokluğu-bir-korumadır. Denetimde bu-ayrımı-tutmak-gerçek-düzeltmeyi-yanlış-düzeltmekten-kurtarır. Aynar-derst: her-boş-default'u-düzeltme-olarak-görme.

## Kanıt

- `sester/facilitator_svc/service.py` + `app.py` (fail-closed-secret)
- `tests/test_facilitator_svc.py::test_193b` (üç-yol)
- `sester/demo_api.py` (uyarı-modu), `README.md` env-tablosu
- Veridict-tarafı-kanıtı: `docs/notes/real-llm-canary-2026-09-19/20.json` (Ollama-0.32.5)
