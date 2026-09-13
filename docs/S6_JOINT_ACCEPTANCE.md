# S6 · Ortak Kabul-Sözleşmesi — Tenderix (authorize/capture/refund) ↔ Sester (verify/settle)

> Taraflar: **63-Sester** (metering/policy/evidence/facilitator, v0.4.0 — S5
> facilitator_svc kodlandı) · **64-Tenderix** (ticaret/escrow, CSVO imzalı).
> Amaç: 64'ün ödeme-yasam-döngüsü ile 63'ün facilitator sözleşmesini TEK
> kanıt-defteri üstünde buluşturan ortak kabul-senaryosu. Durum: **TASARIM —
> iki tarafın testleri buna göre yazılacak; 63 tarafı kapı-yeşili sonrası
> koşmaya hazır.** Bağlam: `docs/S5_FACILITATOR_MILESTONE.md`,
> `64-Tenderix/docs/internal/63_SESTER_ALINAN_NOT.md`.

## 1) Sorumluluk-bölüşümü (tek-ledger, çift-kanıt)

| Ödeme-anı | 64-Tenderix (ticaret) | 63-Sester (kanıt) | Ortak ledger olayı |
|---|---|---|---|
| Teklif-kabulu | CSVO imzalanır (`settlement_rail: sester_x402`) | — | `csvo_accepted` (64) |
| **authorize** | escrow-açılışı (non-custodial hold) | `POST /verify` — zarf + tutar doğrulaması | `facilitator_verify` (63) |
| **capture** | teslim-kanıtıyla escrow-kapanışı | `POST /settle` — nonce-bağı kesinleştirme + metering | `facilitator_settle` (63) |
| **refund** | inkâr-kararı (dispute) | `POST /refund` — settle-edilen nonce'a ters-yazım | `facilitator_refund` (63) |
| Denetim | dispute_resolver karar-kanıtı | evidence-bundle + batch | K0 bundle (her iki taraf okur) |

**Kural:** 64 escrow'yu TUTAR (non-custodial havuz), 63 parayı hiç tutmaz —
63 yalnız doğrular + kanıtlar + sayar. Para-hareketi tek yerde: 64.

## 2) S6 API-uzantısı (63 tarafı; S5 üstüne tek uç)

```
POST /refund   {payment, resource, amount_minor, reason, dispute_ref}
```

- Yalnız **settle-edilmiş** `(seller, nonce)` çifti için: ledger'da o nonce'a
  ait `facilitator_settle` olayı yoksa → `rejected: refund_without_settlement`.
- Zarftaki nonce **ikinci kez tüketilemez** (settle zaten claim'ledi) — refund
  nonce-bağı KIRMAZ; `facilitator_refund` olayı `dispute_ref`'i taşır.
- Tutar: `amount_minor ≤ settle-edilen` tutar; aşarsa `rejected: refund_exceeds`.
- Metering: ücret-iadesi `facilitator_metering` negatif-düzeltme olayıyla
  (auditable; sayaç-toplamı doğrulanabilir kalır).

## 3) Kabul-senaryoları (iki tarafın test-numaralarıyla)

| # | Senaryo | 63-test | 64-test |
|---|---|---|---|
| S6.a | CSVO kabul → authorize: 64 escrow açar, 63 `/verify` ok | test_196 | (64 numaralandırır) |
| S6.b | capture: 64 teslim-kanıtıyla kapanır, 63 `/settle` ok + tek-nonce | test_197 | " |
| S6.c | replay-capture: aynı zarf ikinci capture → 63 `replay_detected`, 64 escrow zaten kapalı | test_198 | " |
| S6.d | refund: inkâr → 64 dispute açar, 63 `/refund` ters-yazım + metering-iade | test_199 | " |
| S6.e | refund-sınırları: settle'siz refund RED; tutar-aşımı RED; bozuk dispute_ref RED | test_200 | " |
| S6.f | uçtan-uca kanıt: oturum-sonu tek K0 bundle — 64'ün CSVO olayları + 63'ün facilitator olayları aynı zincirde; harici-doğrulama (`scripts/dogrula.py`) SAĞLAM | test_201 | " |

**Kabul-beyanı:** altı senaryo iki tarafta da yeşil + tek bundle'da iki imza
(64: CSVO Ed25519, 63: hash-chain) → S6 KAPANDI beyanı IS_PLANI §7'ye düşer.

## 4) Ray-adı geçişiyle bağ (tek-commit paketi)

- 64'ün `pugio_*` → `sester_*` geçişi **bridge_version=2** ile bu turda
  yürürlüğe girer; S6 senaryoları yalnız `sester_x402` ray-adıyla yazılır
  (eski-ad testi ayrıca tutulur).
- `dispute_resolver` varsayılanı aynı pakette `81-OstrakonSOC`'a taşınır.

## 5) Açık maddeler (durum güncel — 2026-09-13, üçüncü tur)

1. Facilitator `/refund` uç-kodu — **KODLANDI** (`sester/facilitator_svc`:
   service + app; kümülatif-iade ≤ settle kuralı dahil) + **test_196–201**
   yazıldı; koşum-kanıtı 63 kapı-yeşilinde (publish-gate).
2. Karşı-taraf-olayı alan-uzlaşması — **KAPANDI**: 64-tarafı haritası
   (`64-Tenderix/docs/internal/S6_ORTAK_KABUL_TENDERIX.md`) gerçek
   kaynak-koddan alan-adlarıyla donduruldu — birleştirme-anahtarı `nonce`,
   64 alanları `offer_id` / `auth_ref` / `escrow_state` / `dispute_ref`
   (= 64 delil-defteri `entry_hash`'i), yazar-işareti `counterparty:
   "tenderix"`. Not: 64'ün şemasında anahtar `offer_id`'dir; bu belgenin
   ilk-taslğındaki `csvo_id` adı düşürüldü.
3. Ortak-deploy + ortak koşum: 64 v1.3.0 ray-geçişini yaptı (bridge_version=2
   teyitli); tetik = 63 kapı-yeşili → S6.a–S6.f pilot-koşumu (tek-bölge VM,
   ayrı süreçler).
