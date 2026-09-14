# Kapı-Geçişi Notu — Tenderix'in beklediği koşum (2026-09-13)

> Bu notu Sester oturumunda **tek komutla** koşun; Tenderix'in S6'yı
> bizim kapı-yeşilimize kilitlediği unutulmasın
> (`64-Tenderix/docs/internal/63_SESTER_ALINAN_NOT.md` teyit-satırı).

## Karar-kaydı (2026-09-13, kullanıcı-onaylı — arayüz-decision-aracıyla)

1. **Repo-rename: ŞİMDİ** — `PUSH=1 REPO_RENAME=1 bash scripts/publish_gate.sh`
   onaylandı; komut goun7/sikke → **goun7/sester**'a çevirir + About/topics
   ayarlar (config.yml security-URL küzeltmesi de bu push'la gider).
2. **PyPI lisans-eşiği: A) AÇIK-ÇEKİRDEK (Apache-2.0)** — "para-kazanma-şansını
   en-arttıran" seçim olarak kullanıcı onayladı: benimseme + güven + katkı;
   hasılat hosted-facilitator (lane-1: %1 + $0.005) + destek/entegrasyon.
   **Sonuç-yükümlülüğü:** (a) proje kamusal-yayın-günü `01_unicorn` klasöründen
   taşınabilir (klasör-adı iç-organizasyon ifşa eder) — kullanıcının kendisi
   belirtti; (b) **upload-öncesi kamusal-yüzey taraması ŞART**: docs/'taki
   kardeş-repo referansları (Tenderix/Tamga iç-yolları, AGENT_MESH_PROTOCOLU,
   oturum-kayıtları) kamu-öncesi anonimleştirilecek — md5 eşik: public-tree
   grep iç-organizasyon-adı = sıfır (Tamga'nın 20:27 hijyen-standardı).

## Terminalde (repo-kökünde) koşulacaklar — sırayla:

```bash
cd /home/gokun/projects/01_unicorn/63-Sester

# 1) Yalnız yerel-kapı (test ×2 + PG + S1/S2 + marka-PNG + build + canlı-E2E):
bash scripts/publish_gate.sh

# 2) Yeşilse — private push (aynı komut, PUSH bayrağıyla):
PUSH=1 bash scripts/publish_gate.sh

# 3) İsterseniz — repo-rename + About/topics:
PUSH=1 REPO_RENAME=1 bash scripts/publish_gate.sh

# 4) PyPI-upload-öncesi ŞART — kamusal-yüzey taraması (sdist iç-ad = 0):
SWEEP=1 bash scripts/publish_gate.sh
```

## Kapı-koşumunda ne olacak (adım-adım):

1. `sikke/` tombstone-silme → 2. tam-suite ×2 (SQLite + Postgres, sıfır-skip,
   **216 test-ayak** = 207+9; S6 63-tarafı + payee-küzeltme pinleri dahil) →
3. S1/S2 kabul-kapıları → 4. marka-PNG'leri → 5. build + twine (v0.5.0) →
6. (`SWEEP=1` ise) kamusal-yüzey taraması (sdist iç-ad = 0; PyPI-öncesi şart) →
7. canlı-E2E (rastgele-port, T0–T10) → (bayraklıysa) 8. commit+push →
9. repo-rename + About/topics.

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
- Kalan (kullanıcı-eylemi, kod-dışı): `PUSH=1 REPO_RENAME=1` push (**ONAYLI**,
  yukarıdaki karar-kaydı) · GitHub Social preview + CI billing · PyPI upload
  (karar A: açık — upload-ÖNCESİ kamusal-yüzey taraması yapılacak, checklist §5).
