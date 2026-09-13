# SESTER — S5 · Hosted Facilitator Kilometretaşı (tasarım, 2026-09-13)

> Amaç: MONETIZATION lane-1'in (%1 + \$0.005/işlem, ilk 10k işlem bedava)
> MVP'sini, IS_PLANI §7 kabul-disipliniyle (S1–S4 geleneği) kodlamak.
> Hedef-sürüm: **v0.5.0**. Durum: **KODLANDI + KAPİ YEŞİL (2026-09-13, 3. koşum:
> 202+14 / 211+5 PG / S1+S2 KABUL / twine PASSED / canlı T0–T10 21/21 — sıfır RED)**
> — koşu-kanıtı publish-gate'e bağlı (kabuk-aracı kapalı oturumlarda koşulamadı):
> `sester/facilitator_svc/` (service.py + app.py), `tests/test_facilitator_svc.py`
> (test_186–195) ve S6 63-tarafı `tests/test_s6_joint.py` (test_196–201; `/refund`
> uç-kodu dahil — docs/S6_JOINT_ACCEPTANCE.md §2-§3'ün koda-çevrilmiş hâli).
> Kabul-koşusu: tam-suite + aşağıdaki S5.a–S5.e senaryoları (testlere birebir karşılıklı).
> Mevcut temel: `sester/facilitator.py` (istemci: verify/settle + Transport-protokolü
> + fail-closed unknown), `sester/settlement.py` (keccak-batch), `sester/evidence.py`
> (kanıt-zinciri) — S5 bunları **hizmete** çevirir, çekirdeği değiştirmez.

## 0) Konum ve non-custodial sınır

- **Sester facilitator'ı ÜÇÜNCÜ-TARAF doğrulayıcıdır:** satıcı kendi `SesterMeter`'ını
  tutar; facilitator yalnız x402-verify/settle + kanıt-kaydı sunar. Anahtar
  TOPLANMAZ (non-custodial, KARAR_63B §5 tekrar-teyit).
- Doğrulama-kanıtı SESTER kanıt-zincirine (S4 sözleşmesi) yazılır → satıcı
  kanıt-arşivi (lane-2) doğal yükseltme olur; facilitator tek-başına kilit olmaz.
  (Referans: S4'de 81-MERGEN tarafına ingestion-artığı yazılmıştı —
  `TamgaProtocol/tamga_pugio_ingest.py`; 81'in kâğıt-başı
  `04_hukuk_sarti/81-OstrakonSOC`, kod-hattı `06_ozel/MERGEN`.)

## 1) Mimari (yalnız ekleme; çekirdek 0-bağımlılık kalır)

```
sester/
  facilitator_svc/          — yalnız [facilitator] extra'sı (demo'dan AYRI paket-yüzeyi)
    app.py        FastAPI: POST /verify · POST /settle · GET /healthz · GET /panel
    store.py      FacilitatorLedger (Ledger'ı sarmalar: verify/settle olayları;
                  settlement-batch'leri periyodik — settlement.py çıktısı)
    metering.py   facilitator'ın KENDİ faturalaması = SesterMeter dogfood
                  (satıcı-başına işlem-sayacı; ilk 10k bedava; %1 + $0.005)
    auth.py       satıcı-API-anahtarı (HMAC, pugio0-donuk şema) — satıcı→facilitator kanalı
tests/
  test_facilitator_svc.py  — test_186… (aşağıda adım-adım)
scripts/
  s5_facilitator_gate.py   — S5 kabul-senaryosu (S1/S2 geleneği; exit 0/1)
```

- **Taşıma-kuralı korunur:** ağ/timeout → `unknown` → istek RED (fail-closed),
  test-taşıması `FakeTransport`; servis-testi gerçek-HTTP yerine `httpx` + ASGI
  transport (ağ-izolasyonu, CI-uyumlu).
- **Sıfır yeni bağımlılık çekirdeğe:** `facilitator_svc` ayrı extra
  (`facilitator = ["fastapi...", "uvicorn..."]`) — çekirdek 0 kalır.

## 2) API sözleşmesi (x402 v2 uyumlu, bizim kanıt-uzantılarımızla)

| Uç | İstek | Yanıt | Kanıt-olayı |
|---|---|---|---|
| `POST /verify` | x402 payment-zarfı + `resource` | `{"ok":true,"status":"ok"\|"rejected"\|"unknown"}` | `facilitator_verify` (status+reason) |
| `POST /settle` | onaylı zarf | `{"ok":true,"settlement":"0x…"}` | `facilitator_settle` (batch-refsiz mikro) |
| `GET /panel` | — | satıcı-başına sayaç + tahsil-öngörüsü | — |
| `GET /healthz` | — | sürüm + zincir + batch-lag | — |

- **Idempotency:** aynı zarf-nonce'u settle'da bir-kez (ledger `claim_nonce`
  mirası) → tekrar-settle RED.
- **Rate/quota:** satıcı-başına günlük-minor-kota (zaten çekirdekte) — facilitator
  kendi ilacıyla ölçülür (dogfood-satışı: satış-demosu).

## 3) Kabul-senaryosu S5 (IS_PLANI §7 stilinde — kodlanınca doldurulur)

1. **S5.a** satıcı kaydı → API-anahtarı → `/verify` temiz-zarf `ok` + kanıt-olayı.
2. **S5.b** `/settle` idempotent: ikinci aynı-zarf RED; kanıt-zincirde.
3. **S5.c** facilitator-AŞAĞI simülasyonu → istemci `unknown` → satıcı 402
   (fail-closed uçtan-uca; mevcut test-taşıma disipliniyle).
4. **S5.d** metering: 10.001. işlemde kota/fatura-olayı (bedava-band kapanışı);
   %1+$0.005 hesabı ledger'dan kanıtlanabilir.
5. **S5.e** batch: N mikro-settle → `build_settlement_batch` → merkle-root +
   calldata kanıt-olayı; EVM-yayını bilinçli-dışı (non-custodial).

**Test-haritası:** test_186–188 (app/verify/settle), 189 (idempotency),
190 (fail-closed unknown), 191–192 (metering+band), 193 (batch-integrasyon),
194 (auth: bozuk/eksik anahtar → 401; fail-loud).

## 4) Yayın-sırası (v0.5.0)

1. `facilitator_svc` + testler + S5-gate yeşil (tüm-suite ×2, PG dahil).
2. `MONETIZATION.md` lane-1 "MVP kodlandı" satırı + adoption_log.
3. Tek-bölge deploy-rehberi (`docs/FACILITATOR_DEPLOY.md`: uvicorn + PG + PG-backed
   ledger + ters-proxy notu; ölçek-kararı Tek-süreç→çok-satıcı-shard bilinçli-gecikmeli).
4. Fiyat-sayfası zaten MONETIZATION'da; deployment-öncesi hukuk-görüşü NOTU
   (IS_PLANI §11 madde-1 ile aynı ⚖️ tetikleyici).

## 4b) S6-uzantısı (bu kodlamayla geldi; sözleşme docs/S6_JOINT_ACCEPTANCE.md)

- `/refund` uç-kodu + `FacilitatorService.refund` — settle-edilmiş nonce için
  ters-yazım; **nonce-başına toplam-iade ≤ settle** kuralı (kısmi-iade birikimli);
  dispute_ref kanıta düşer; metering-iadesi sayaç-sayısını bozmaz
  (payload.refund_of satırları _tx_count'tan hariçtir).
- Test-haritası uzadı: 186–195 (S5) + 196–201 (S6-63-tarafı) = **test_186–201**.

## 5) Bilinçli-sınırlar (v0.5.0'da YOK)

- On-chain tx-imzası / cüzdan-yönetimi (settlement.py zaten non-custodial çizgide).
- Çok-bölgeli replicasyon; facilitator-federation.
- Satıcı-dashboard'ı (panel + kanıt-bundle yeterli; kurumsal-istek gelirse lane-3).
