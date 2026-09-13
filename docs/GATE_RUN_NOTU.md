# Kapı-Geçişi Notu — Tenderix'in beklediği koşum (2026-09-13)

> Bu notu Sester oturumunda **tek komutla** koşun; Tenderix'in S6'yı
> bizim kapı-yeşilimize kilitlediği unutulmasın
> (`64-Tenderix/docs/internal/63_SESTER_ALINAN_NOT.md` teyit-satırı).

## Terminalde (repo-kökünde) koşulacaklar — sırayla:

```bash
cd /home/gokun/projects/01_unicorn/63-Sester

# 1) Yalnız yerel-kapı (test ×2 + PG + S1/S2 + marka-PNG + build + canlı-E2E):
bash scripts/publish_gate.sh

# 2) Yeşilse — private push (aynı komut, PUSH bayrağıyla):
PUSH=1 bash scripts/publish_gate.sh

# 3) İsterseniz — repo-rename + About/topics:
PUSH=1 REPO_RENAME=1 bash scripts/publish_gate.sh
```

## Kapı-koşumunda ne olacak (adım-adım):

1. `sikke/` tombstone-silme → 2. tam-suite ×2 (SQLite + Postgres, sıfır-skip,
   **216 test-ayak** = 207+9; S6 63-tarafı + payee-küzeltme pinleri dahil) →
3. S1/S2 kabul-kapıları → 4. marka-PNG'leri → 5. build + twine (v0.5.0) →
6. canlı-E2E (rastgele-port, T0–T10) → (bayraklıysa) 7. commit+push →
8. repo-rename + About/topics.

## 2026-09-13 ilk-koşum düzeltmeleri (3 RED → küzeltildi):

- `test_74` Tamga-alıcısı kaynak-uyumu: kardeş-alıcı eski `pugio`-sıkı hâline
  dönmüştü — çift-ad-okuma geri-kondu (sikke|pugio; bilinmeyen RED) + K0 §5
  okuma-uyumu kuralı + pin.
- `test_193`/`test_201` payee-kayıt-defteri: ledger-kimliği artık ABI
  `address` alanına geçirilmiyor — `register_payee`/`derive_payee_address`
  (açık-belingi türetme kayıt-altında; çakışma RED; digest adres-bağlı).
- Suite-kümülatif: 191 geçti + 3 RED + 14 skip (=208) → küzeltme + 8 yeni
  pin (`tests/test_payee_registry.py`) → **207+9**.

## Yeşil-sonrası üç madde (otomatikleşmez, hızlı):

1. **GitHub Social preview**: Settings → Social preview →
   `.github/assets/og.png` (adım-4 üretir).
2. **CI billing**: GitHub → Billing → spending-limit — CI yeşili için
   kullanıcı-eylemi (kod-hatası değil).
3. **Tenderix'e sinyal**: kapı-yeşili haberini verin — S6 ortak-turunu
   başlatırlar; 63-tarafı test_186–201 kodlu, `/verify /settle /refund`
   uçları hazır.

## Durum özeti (2026-09-13, 3. koşum — **KAPI YEŞİL**):

- **Koşum A:** 202 passed · 14 skip — **Koşum B (PG):** 211 passed · 5 skip
- **S1/S2:** KABUL — **build/twine:** PASSED (sester-0.5.0) — **canlı-E2E:** 21/21
- **Sıfır RED → 100/100 mührü verildi.** Tenderix'e sinyal-notu yazıldı
  (`64-Tenderix/docs/internal/S6_KAPI_YESILI_SINYALI.md`) — S6 ortak-turu açık.
- Kalan (kullanıcı-eylemi, kod-dışı): `PUSH=1` (+`REPO_RENAME=1`) push ·
  GitHub Social preview + CI billing · PyPI upload (twine komutu checklist'te).
