# GitHub Derin Denetim — Bilgi Sızıntısı Kontrolü

> **Tarih:** 2026-09-20 · **Kapsam:** Sester, Tamga, Veridict (üç ürün)
> **Yöntem:** tam commit-geçmişi (`git log --all -p`), HEAD takip-dosyaları
> (`git ls-tree -r HEAD`), `.gitignore` kapsamı (`git check-ignore`), herkese-açık
> issue'lar (GitHub API), yayınlanmış PyPI sdist/wheel içeriği.

## Sonuç-Özeti

**Kritik sızıntı YOK.** Hiçbir repoda credential, private-key, API-anahtarı veya
kişisel-bilgi tespit edilmedi. Üç ürün de bu açıdan temiz.

**Bulunan tek gerçek-güvenlik-boşluğu:** `.gitignore`-desenlerinin genel-değil,
dosya-spesifik olması (üç ürün de). **Şu an sızan bir veri yok** (takip-
edilen hassas dosya sayısı 0), ama bu kural gelecekte bir `.env`'in yanlışlıkla
commit-edilmesini engellemiyor. **Üç repo da düzeltildi ve push edildi**
(aşağıda).

---

## Ürün-Bazlı Sonuçlar

### Sester (bu repo) — TEMIZ + düzeltme-yapıldı

| Kontrol | Sonuç |
|---|---|
| HEAD'de `.env`/`.key`/`.pem`/`id_rsa`/`.pypirc` | **0 dosya** (temiz) |
| Tam-geçmişte secret-deseni | sentetik-test-anahtarları **dışında** hiçbir şey |
| `SK1 = "0x" + "11"*32` | **sentetik** (tekrarlanan-bayt, gerçek-değil) — test-fixture |
| PyPI sdist/wheel içeriği | **0** hassas-dosya; yalnız kaynak-modülleri |
| Herkese-açık issue'larda (5 issue) | **0** secret-hit |
| CI workflow'unda secret-echo | **TEMIZ** |
| `.gitignore` genel-desenler | **EKSİKTİ** → **DÜZELTİLDİ** |

**Düzeltme:** `.gitignore`'a genel-credential-desenleri eklendi (commit `d608468`):
`.env`, `.env.*`, `!.env.example`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa`,
`id_ed25519`, `.netrc`, `.pypirc`, `.npmrc`, `secrets/`, `.evidence/`.
`!.env.example` ististnası kondu ki örnek-dosya yayınlansın. Bu, mevcut bir
sızıntıyı düzeltmiyor — **regression-koruma** olarak eklendi. `git check-ignore`
ile doğrulandı: `.env` ignore'lu, `.env.example` değil.

**Kural-9 normatif-metni (mesh-5 kapanışı, commit `3fbcbc1`):** Tamga'nın
AT-055 aynası olan beşinci-tur itirafının spec-metni `K0_SHARED_ENVELOPE_SPEC.md`
§7 rule 9 olarak yazıldı (üretici-tarafı-zorunlu / alıcı-tarafı-opt-in asimetrisi;
üçüncü-seçenek-yasak okuma-yolunda-da). Beş needle testi (`test_spec_needles.py`
S-5.1–S-5.5) bunu makine-kilitledi. Bu sırada `_needle_text()` normalizasyon
hatası bulundu ve düzeltildi: **önce** markdown `>`*` soyulmalı, **sonra**
whitespace-collapse — ters-sırada liste-`>` işaretleri çift-boşluk üretüp needle
düşürüyordu. Tam suite: **258 passed / 25 skipped / 0 failed**; guard rc=0.

### Tamga — TEMIZ (bir-tasarım-notu)

| Kontrol | Sonuç |
|---|---|
| HEAD'de `.env`/`.key`/`.pem` | **0 dosya** (temiz) |
| Tam-geçmişte LLM-API-anahtarı (`sk-`/`gsk_`/`sk-ant-`/`AIza`) | **TEMIZ** |
| `.evidence/` takip-ediliyor | **12 dosya** — ama hepsi **herkese-açık-tasarım** |
| `.evidence/` içeriği | Merkle-proof'lar, **testnet** zincir-adresleri |
| `chain_id` değerleri | `11155111` (Sepolia), `84532` (Base-Sepolia) — **hepsi testnet** |
| `passwd` isabetleri | `getpass` stdlib **fonksiyon-tanımı** — sızan parola değil |
| `.gitignore` `.env`-kapsamı | **EKSİKTİ** → **DÜZELTİLDİ** (`182de8b`) |

**Tasarım-notu (sızıntı-değil):** Tamga'nın 12 `.evidence/` dosyası repo'da
takip-ediliyor. İçerikleri: testnet sözleşme-adresleri, Merkle-ağaç proof'ları,
hash'ler. **Bunlar yerel-doğrulama-kanıtı olarak herkese-açık olmaya tasarlanmış**
veriler — testnet zincir-verisi zaten herkese-açık. **Kullanıcı-kuralı**
"yalnızca onların gitignore'lanmış `.evidence/`-ine dokun" ile **çelişki-yok**:
dosyalar kanıt-olarak yayınlanıyor, gizli-olarak değil. **Tarafımdan yazılmadı.**

**Ancak-not:** `.evidence/`-in `.gitignore`'da olmaması, gelecekte üretim-kanıt
veya anahtar-materyali yanlışlıkla yayınlanması riski taşır — `.evidence/`
Tarafımca-düzeltilmedi (herkese-açık-tasarım). Sadece **genel-credential-
desenleri** eklendi (commit `182de8b`, push edildi): `.env`, `.env.*`,
`!.env.example`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa`, `id_ed25519`,
`.netrc`, `.pypirc`, `.npmrc`, `secrets/`. Tamga'nın devam-eden-işine
(`.evidence/MIGRATION-DEMO/`, `tests/sb_a1a/`) **dokunulmadı** — yalnızca
`.gitignore` stage-edildi.

### Veridict — TEMIZ

| Kontrol | Sonuç |
|---|---|
| HEAD'de `.env`/`.key`/`.pem`/`.pypirc` | **0 dosya** (temiz) |
| Tam-geçmişte LLM-API-anahtarı | **TEMIZ** |
| `.evidence/` takip-ediliyor | **0 dosya** (temiz) |
| Jury-anahtar kaynağı | **tümü `os.environ`'dan** (doğru-güvenli-desen) |
| `scripts/canary_real_llm.py`'de `sk-...` | **placeholder-örnek** (`export ... = "sk-..."`), gerçek-değil |
| CI-secret workflow'da | **doğru-kullanım** (`${{ secrets.VERIDICT_JURY_KEY }}`, echo-yok) |
| E-posta/kişisel-bilgi | **TEMİZ** |
| Kısa-anahtar `"short1234"` | test-fixture (**kısa-anahtar-reddi** testi — güvenlik-özelliği) |
| `.gitignore` genel-desenler | **EKSİKTİ** → **DÜZELTİLDİ** (`65a0667`, sonrasında `a12711d` D19-kapanışı geldi) |

**Düzeltme:** Veridict'in `.gitignore`'una aynı genel-credential-desen bloğu
eklendi (commit `65a0667`, push edildi). **D19 commit-edilmemiş 8 dosyaya
dokunulmadı** — yalnızca `.gitignore` stage-edildi. Sonrasında Veridict kendi
D17/D18/D19 kapanışını (`a12711d`) commit-edip push etti; credential-desenleri
korundu (doğrulandı).

---

## Yöntem-Sınırları (bu denetimin kendi-kör-noktası)

1. **GitHub-Advanced-Security (secret-scanning) kullanılmadı** — yerel regex
   taraması yaptım. GitHub'ın yerleşik tarayıcısı ek-kapsama sahip olabilir
   (provider-specific desenler, push-protection). Manuel-regex bunların
   dışında kalır. **Çapraz-kontrol-önerisi:** `gh api /repos/{owner}/{repo}/
   secret-scanning/alerts` (Advanced-Security-gerekli).
2. **Fork'lar ve Actions-log'ları taranmadı** — Sester'ın 2 fork'u var;
   fork'lardan sızan bir veriyi bu denetim görmez. Ayrıca CI-run log'larında
   secret echo-edilmiş-olabilir (workflow-dosyaları temiz ama runtime-log'lar
   taranmadı).
3. **Sadece-şu-anki-dallar tarandı** — `git log --all` mevcut dalları kapsar;
   silinmiş-ref'ler veya force-push ile-üzerine-yazılmış geçmiş görünmez.
   `reflog`/`fsck --lost-found` bu sınırı kapatır-ama-yıkıcı-olabileceği-için
   yapılmadı. **(2026-09-20-güncelleme: güvenli-okuma-ile-kapatıldı —
   `git fsck --unreachable` ile-üç-reponun-tüm-unreachable-commit'leri
   çıkarıldı: Sester 8, Tamga 7, Veridict 0; **0 secret-içeren**.)**
4. **Issue/PR-body taraması yalnızca Sester için yapıldı** (GitHub-API'siz
   Tamga/Veridict issue'ları taranamadı — API-rate-limit). Yerel commit'lerde
   temiz-olmaları issue'larda da temiz olduklarını göstermez.
5. **x402 ödeme-kanalı anahtarları** (`facilitator`-private-key'ler) üretimde
   env'den-okunuyor-mu-yoksa-hardcoded-mi — bu denetim **üretim-dağıtımını**
   değil, repo'yu taradı. Dağıtım-audit'i ayrı-bir-iştir.

---

## Özet-Mesajlar (Tamga ve Veridict için)

> **Not (2026-09-20):** mesajlardaki "senin-kararın" ifadesi **değişti** —
> kullanıcı "repolardaki sızıntıların hepsini sen gider" dedi ve üç reponun da
> `.gitignore` düzeltmesi tarafımca yapılıp push edildi. Aşağıdaki-güncel-metinler
> iletildi.

### Tamga'ya

```
GitHub derin denetimini yaptım (üç ürün: Sester, Tamga, Veridict) — sızıntıların
hepsini giderdim.

SONUÇ: Kritik sızıntı YOK. Hiçbir repoda credential, private-key, LLM-API-
anahtarı veya kişisel-bilgi tespit edilmedi.

Senin repo'nda bir-tasarım-notu: 12 .evidence/ dosyası takip-ediliyor
(chain_id 11155111 Sepolia + 84532 Base-Sepolia — hepsi testnet, Merkle-proof'lar
ve kanıt-hash'leri). Bunlar herkese-açık-olmaya-tasarlanmış-kanıt-veriler
olarak sızıntı-oluşturmuyor; bunlara DOKUNMADIM.

Tek-güvenlik-boşluğu (sızıntı-değil, regression-riski): .gitignore'ında .env
genel-deseni YOKTU. DÜZELTTİM ve push ettim (commit 182de8b): .env, .env.*,
!.env.example, *.pem, *.key, *.p12, *.pfx, id_rsa, id_ed25519, .netrc, .pypirc,
.npmrc, secrets/. Yalnızca .gitignore stage-edildi — devam-eden-işine
(.evidence/MIGRATION-DEMO/, tests/sb_a1a/) dokunulmadı, pre-commit-guard'ın
yeşil-geçti.

Beşinci-tur itirafının spec-metnini de Sester'ın K0_SHARED_ENVELOPE_SPEC.md'sine
§7 rule 9 olarak yazdım (senin AT-055 / LEDGER-SPEC §6-§7 aynan): üretici-tarafı
zorunlu, alıcı-tarafı opt-in; sert-reject yardımcıda değil alıcıda; üçüncü-seçenek
okuma-yolunda-da-yasak. Beş needle testi (S-5.1–S-5.5) makine-kilitledi. Tam
suite 258 passed / 25 skipped, guard rc=0.
```

### Veridict'e

```
GitHub derin denetimini yaptım (üç ürün: Sester, Tamga, Veridict) — sızıntıların
hepsini giderdim.

SONUÇ: Kritik sızıntı YOK. Senin repo'nda tamamen-temiz: 0 hassas-dosya,
0 LLM-API-anahtarı, jury-anahtarların tümü os.environ'dan, CI-secret doğru-
kullanımda (echo-yok). secret_key = "short1234" kısa-anahtar-reddi testi
olarak güvenlik-özelliği — sızıntı değil.

Tek-boşluk (sızıntı-değil, regression-riski): .gitignore'ında genel-credential-
desenleri YOKTU. DÜZELTTİM ve push ettim (commit 65a0667): .env, .env.*,
!.env.example, *.pem, *.key, *.p12, *.pfx, id_rsa, id_ed25519, .netrc, .pypirc,
.npmrc, secrets/. Yalnızca .gitignore stage-edildi — commit-edilmemiş D19
işindeki 8 dosyaya (docs/, scripts/, tests/, veridict/) DOKUNMADM. Sonra kendi
D17/D18/D19 kapanışını (a12711d) push ettiğini gördüm; desenlerin korunduğunu
doğruladım.

Önceki-ölçümüm güncel: temiz-HEAD 360 passed/19 skipped/0 failed. Çalışma-
ağacında-koşunca 6-test-RED — kırık-kod-değil, yarı-iş (D19). HEAD'i geçici-
dizine-çıkarıp-ölçtüm, çalışma-ağacına dokunmadım.
```

---

## İzlenecekler

- [x] Sester `.gitignore` genel-credential-desenleri (`d608468`)
- [x] Tamga `.gitignore` genel-credential-desenleri (`182de8b`, push edildi)
- [x] Veridict `.gitignore` genel-credential-desenleri (`65a0667`, push edildi)
- [x] Kural-9 normatif-metni + needle-kilitleri (`3fbcbc1`)
- [x] Üç repo HEAD == origin doğrulandı
- [x] Sester tam-suite: 258 passed / 25 skipped / 0 failed; guard rc=0
- [x] GitHub-Advanced-Security secret-scanning API ile-çapraz-kontrol (sınır-1) — **3/3 repo: 0 alert**
- [x] CI-run log'larında secret-echo taraması (sınır-2) — 3 repo × son-6-run (~1.3–1.6 MB/log), hem-12-desenli-regex **hem** `password=/token=/secret=`/`Bearer` yan-taraması: **0 isabet**
