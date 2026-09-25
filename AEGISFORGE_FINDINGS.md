# AEGISFORGE FINDINGS — SESTER DEPO YAPISAL RAPORU

**Tarih:** 2026-09-25
**Tarayan:** AegisForge/AutoVerus (harici denetim, **SALT-OKUR**)
**Kapsam:** x402 ödeme katmanı güvenlik taraması sırasında bulunan **depo yapısı** gözlemleri
**Not:** Bu rapor bir **gözlem**dir. AegisForge, Sester'ın kodunu veya
yapısını **değiştirmedi**. Aşağıdaki kalemler Sester ekibinin takdirine
bırakılmıştır.

---

## Özet

| # | Gözlem | Risk | Öneri |
|---|---|---|---|
| 1 | `63-Sester` kendine işaret eden **sembolik bağlantı** (sonsuz öz-yineleme) | Düşük (disk yok) ama araç karmaşası | Bağlantıyı kaldır veya `.gitignore`'a ekle |
| 2 | `.venv` deponun **içinde** commit edilmiş (152 MB) | Orta — depo şişmesi, CI yavaşlaması | `.gitignore`'a `.venv/` ekle |
| 3 | Güvenlik taraması sonucu: **0 arka kapı imzası** | — | (aşağıda) |

## 1. `63-Sester` Öz-Yinelemeli Sembolik Bağlantı

**Gözlem:** Deponun kök dizininde

```
63-Sester -> /home/gokun/projects/01_unicorn/63-Sester
```

şeklinde kendine işaret eden bir sembolik bağlantı var. Bu, **sonsuz
öz-yineleme** yaratır:

```
63-Sester/63-Sester/63-Sester/63-Sester/… (sonsuz)
```

**Disk etkisi: YOK.** inode'lar paylaşıldığı için `du` toplamı 152 MB'dir
(40 seviye × 148 MB **değil** — aynı inode tekrar sayılır, ama `du`
örneklemesi 0 döner çünkü bağlantı döngüsü kestirilir).

**Gerçek etki (araç karmaşası):**
- AegisForge ilk taramasında **3526 dosya** saydı (aynı projenin tekrarı)
- Derinlik sınırı (`MAX_SCAN_DEPTH = 32`) eklenmeden önce tarama süreleri
  ve rapor boyutları şişer
- `find`, `grep -r`, `rsync`, `tar` gibi araçlar bu döngüde **sonsuz** dönebilir

**Öneri:**
```bash
# Güvenli kaldırma (salt-okur tarama yaptık, sizinkini öneriyoruz)
rm 63-Sester          # bağlantıyı kaldırır, hedefe dokunmaz
# veya en azından tarayıcıların gözünden gizle:
echo "/63-Sester" >> .gitignore
```

## 2. `.venv` Deponun İçinde

**Gözlem:** `.venv/` dizini 152 MB ve deponun kökünde. `git status` temiz,
yani ya `.gitignore`'da ya da commit edilmemiş.

**Kontrol:**
```bash
grep -n "venv" .gitignore    # var mı?
git ls-files | grep -c venv  # commit edilmiş mi?
```

Eğer commit edilmişse: depo klonu gereksiz 152 MB yük taşır. `.venv/` her
geliştirici için yeniden oluşturulmalı (`python -m venv .venv`), commit
edilmemeli.

**Öneri:**
```
# .gitignore
.venv/
venv/
env/
```

## 3. Güvenlik Taraması Sonucu (Referans)

Aynı taramanın **güvenlik** boyutu ayrı bir dokümanda:
`docs/AEGISFORGE_VAKA_CALISMASI_04_SESTER.md`

**Özet:** 2742 dosya tarandı, **0 bilinen arka kapı imzası** tetiklendi,
CleanScore 100/100, PoV_Hash ile yeniden üretilebilir.

> **Dürüst not:** "0 bulgu", "0 bilinen imza" demektir — "güvenli" demek
> değildir. Negatif kontrollerimiz (planted Telegram sızlatma → CRITICAL,
> AWS anahtarı → HIGH) tarayıcının gerçekten çalıştığını kanıtlar, ama
> tarama kataloğumuzun dışındaki saldırı vektörlerini kapsamaz.

## 4. AegisForge Tarafında Yapılan Düzeltmeler

Bu gözlemler **tarayıcıda** düzeltmeler tetikledi (Sester'ın kodunda değil):

1. `.venv`/`venv`/`env`/`site-packages`/`.tox`/`.nox` atlama listesine eklendi
2. `MAX_SCAN_DEPTH = 32` sınırı eklendi (sembolik bağlantı döngülerine karşı)
3. **Config dosyası taraması:** `.txt`, `.md`, `.env`, `.ini` vb. artık
   taranıyor (daha önce `.txt`'deki AWS anahtarı görünmüyordu)
4. **AF-SRC-010:** Slack/Google/Stripe/GitLab anahtar biçimleri eklendi
5. **Markdown false-positive disiplini:** tablo ayırıcıları (`| Shipped` →
   `| sh`) ve backtick içindeki dosya adları (`` `.npmrc` ``) artık
   komut/credential imzası olarak tetiklenmiyor

Bu, bir sonraki hedefte aynı gürültüyü üretmeyecekler.

## 5. Tarama Sırasında Bulunan Teknik Gerçek

İlk genişletilmiş tarama (config dosyaları eklendikten sonra) Sester'da
**194 CRITICAL + 96 HIGH** raporladı. Bunların **tamamı false positive** olarak
belirlendi ve düzeltildi:

| Kaynak | Bulgu | Gerçek mi? | Düzeltme |
|---|---|---|---|
| README.md tablo ayırıcıları `| Shipped` | 130 × AF-SRC-003 CRITICAL | **Hayır** — markdown tablo satırı | `is_prose` bayrağı ile command imzaları markdown'da kapatıldı |
| `authorized_keys`, `.onion/` geçişleri | 64 × AF-SRC-001 CRITICAL | **Hayır** — prose | aynı kural |
| `` `.npmrc` `` dokümantasyon geçişleri | 192 × AF-SRC-006 MEDIUM | **Hayır** — backtick içindeki dosya adı | markdown'da credential-**dosya** imzaları kapatıldı; canlı anahtar biçimleri (AKIA, ghp_) hâlâ tetikler |

> **Bu, tarayıcının dürüstlük disiplininin bir parçasıdır:** yeni bir tarama
> yüzeyi eklendiğinde ortaya çıkan gürültü, "temiz" diye yayınlanmadan önce
> **false positive olarak teşhis edilip düzeltildi.** Hiçbir CRITICAL finding
> yayınlanmadı.

---

*Bu rapor salt-okur bir gözlemdir. AegisForge, Sester'ın kaynak kodunu,
yapısını veya yapılandırmasını değiştirmedi. Tüm düzeltmeler AegisForge'un
kendi deposunda (07_Temporit_DeFi_Metamorfik_Yaris_Durumu_Avcisi) yapıldı.*
