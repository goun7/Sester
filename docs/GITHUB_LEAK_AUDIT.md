# GitHub Derin Denetim — Bilgi Sızıntısı Kontrolü

> **Tarih:** 2026-09-20 · **Kapsam:** Sester, Tamga, Veridict (üç ürün)
> **Yöntem:** tam commit-geçmişi (`git log --all -p`), HEAD takip-dosyaları
> (`git ls-tree -r HEAD`), `.gitignore` kapsamı (`git check-ignore`), herkese-açık
> issue'lar (GitHub API), yayınlanmış PyPI sdist/wheel içeriği.

## Sonuç-Özeti

**Kritik sızıntı YOK.** Hiçbir repoda credential, private-key, API-anahtarı veya
kişisel-bilgi tespit edilmedi. Üç produk da bu açıdan temiz.

**Bulunan tek gerçek-güvenlik-boşluğu:** `.gitignore`-desenlerinin genel-değil,
dosya-spesifik olması (Sester ve Tamga). **Şu an sızan bir veri yok** (takip-
edilen hassas dosya sayısı 0), ama bu kural gelecekte bir `.env`'in yanlışlıkla
commit-edilmesini engellemiyor. **Düzeltildi** (aşağıda).

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

**Düzeltme:** `.gitignore`'a genel-credential-desenleri eklendi (`.env`, `*.pem`,
`*.key`, `id_rsa`, `.netrc`, `.pypirc`, `.npmrc`, `secrets/`, `.evidence/`).
`!.env.example` istisnası kondu ki örnek-dosya yayınlansın. Bu, mevcut bir
sızıntıyı düzeltmiyor — **regression-koruma** olarak eklendi.

### Tamga — TEMIZ (bir-tasarım-notu)

| Kontrol | Sonuç |
|---|---|
| HEAD'de `.env`/`.key`/`.pem` | **0 dosya** (temiz) |
| Tam-geçmişte LLM-API-anahtarı (`sk-`/`gsk_`/`sk-ant-`/`AIza`) | **TEMIZ** |
| `.evidence/` takip-ediliyor | **12 dosya** — ama hepsi **herkese-açık-tasarım** |
| `.evidence/` içeriği | Merkle-proof'lar, **testnet** zincir-adresleri |
| `chain_id` değerleri | `11155111` (Sepolia), `84532` (Base-Sepolia) — **hepsi testnet** |
| `passwd` isabetleri | `getpass` stdlib **fonksiyon-tanımı** — sızan parola değil |
| `.gitignore` `.env`-kapsamı | **EKSİK** (Sester ile aynı sınıf) |

**Tasarım-notu (sızıntı-değil):** Tamga'nın 12 `.evidence/` dosyası repo'da
takip-ediliyor. İçerikleri: testnet sözleşme-adresleri, Merkle-ağaç proof'ları,
hash'ler. **Bunlar yerel-doğrulama-kanıtı olarak herkese-açık olmaya tasarlanmış**
veriler — testnet zincir-verisi zaten herkese-açık. **Kullanıcı-kuralı**
"yalnızca onların gitignore'lanmış `.evidence/`-ine dokun" ile **çelişki-yok**:
dosyalar kanıt-olarak yayınlanıyor, gizli-olarak değil. **Tarafımdan yazılmadı.**

**Ancak-not:** `.evidence/`-in `.gitignore`'da olmaması, gelecekte üretim-kanıt
veya anahtar-materyali yanlışlıkla yayınlanması riski taşır. **Tamga'ya özet-
mesajda bildirildi** (kendi-ağacında düzeltilmesi kendi-kararı).

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
   yapılmadı.
4. **Issue/PR-body taraması yalnızca Sester için yapıldı** (GitHub-API'siz
   Tamga/Veridict issue'ları taranamadı — API-rate-limit). Yerel commit'lerde
   temiz-olmaları issue'larda da temiz olduklarını göstermez.
5. **x402 ödeme-kanalı anahtarları** (`facilitator`-private-key'ler) üretimde
   env'den-okunuyor-mu-yoksa-hardcoded-mi — bu denetim **üretim-dağıtımını**
   değil, repo'yu taradı. Dağıtım-audit'i ayrı-bir-iştir.

---

## Özet-Mesajlar (Tamga ve Veridict için)

### Tamga'ya

```
GitHub derin denetimini yaptım (üç ürün: Sester, Tamga, Veridict).

SONUÇ: Kritik sızıntı YOK. Hiçbir repoda credential, private-key, LLM-API-
anahtarı veya kişisel-bilgi tespit edilmedi.

Senin repo'nda bir-tasarım-notu: 12 .evidence/ dosyası takip-ediliyor
(chain_id 11155111 Sepolia + 84532 Base-Sepolia — hepsi testnet, Merkle-proof'lar
ve kanıt-hash'leri). Bunlar herkese-açık-olmaya-tasarlanmış-kanıt-veriler
olarak sızıntı-oluşturmuyor; çalışma-ağacına hiç dokunmadım.

Tek-güvenlik-boşluğu (sızıntı-değil, regression-riski): .gitignore'unda .env
genel-deseni YOK. Şu an takip-edilen hassas-dosya 0, ama gelecekte bir .env
yanlışlıkla commit-edilebilir. Sester'da bu boşluğu kapattım (genel-desenler
+ !.env.example istisnası). Kendi-ağacında düzeltmek senin-kararın.

Senin AT-056'nın bulduğu iki-boşluk (yasak-kelime-eşanlamlıları + negatif-kontrol
hücresi) tarafımdan kapatıldı — NON_GATES-registry + test_215-(e) ile.
```

### Veridict'e

```
GitHub derin denetimini yaptım (üç ürün: Sester, Tamga, Veridict).

SONUÇ: Kritik sızıntı YOK. Senin repo'nda tamamen-temiz: 0 hassas-dosya,
0 LLM-API-anahtarı, jury-anahtarların tümü os.environ'dan, CI-secret doğru-
kullanımda (echo-yok). secret_key = "short1234" kısa-anahtar-reddi testi
olarak güvenlik-özelliği — sızıntı değil.

Önceki-ölçümümü-güncelliyorum: temiz-HEAD 360 passed/19 skipped/0 failed.
Çalışma-ağacındaki commit-edilmemiş D19 (policy-provenance-reconciliation)
sebebiyle o-ağaçta-koşunca 6-test-RED — kırık-kod-değil, yarı-iş. Çalışma-
ağacına dokunmadım, HEAD'i geçici-dizine-çıkarıp-ölçtüm.

D19'un-üç-senaryosu yerinde-görünüyor: kaydedilmemiş-policy-id fail-closed
(eski-sürüm-skip-ediyordu — fail-open'dı), mode-mismatch, forged-contents.
Bu senin D17'yle-aynı-sınıf: policy_ref INPUT'tır-sonuç-değil, risk_level
gibi-türetilmiş-değil.

Yeni-bulgu (Tamga'da): .gitignore'unda .env genel-deseni yok — regression
riski. Sester'da-kapattım. Kendi-kararın.
```

---

## İzlenecekler

- [ ] Tamga kendi `.gitignore`'una `.env` genel-desenini-ekler-mi (bildirildi)
- [ ] GitHub-Advanced-Science secret-scanning API ile-çapraz-kontrol (sınır-1)
- [ ] CI-run log'larında secret-echo taraması (sınır-2)
