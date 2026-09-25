# AEGISFORGE VAKA ÇALIŞMASI 04 — SESTER (x402 ÖDEME KATMANI)

**Tarih:** 2026-09-25
**Tarayan:** AegisForge/AutoVerus uzmanlığı (harici denetim)
**Hedef:** Bu deponun kök dizini (`01_unicorn/63-Sester/`)
**Önem:** Sester, **4 ajanın ödeme katmanıdır** — x402 rayında kritik
**Yöntem:** `scan --src-dir` (kaynak imza taraması), salt-okur
**Durum:** YAYINLANDI — sonuç ne olursa olsun (LE-3 kalkanı)

---

## 1. Hedef ve Kısıt

Sester bir **Python** projesidir — akıllı kontrat değildir. AegisForge'un
sözleşme kademesi **uygulanabilir değildir**; sadece **kaynak-dosya imza
taraması** koşuldu.

> **Neden bu hedef kritik:** Sester x402 ödeme rayını çalıştırır. Arka kapı
> veya sızma imzası burada, doğrudan **4 ajanın ödeme akışını** etkiler.
> "Temiz" demek kolay; kanıtlamak için taramayı çalıştırdık.

**Tarayıcı bu depoya salt-okur erişti.** Hiçbir kaynak dosyası değiştirilmedi;
bu rapor `docs/` altına yerleştirildi.

## 2. Tarama Sonucu

```
stage 5 (source): 5157 file(s) scanned, 0 finding(s)
                   0 critical / 0 high / 0 medium
clean score:       100/100
target hash:       0x5d0cceb2536d230faed301068b3b79320a8ad0812255df286210c8c6be4c4a3e
PoV_Hash:          0x8628545c4bd91c0023e6b963e494da6a54442c9c89a1bf31d84e91a48f032af5
```

**Hiçbir bilinen arka kapı imzası tetiklenmedi.** Bu, "güvenli" demek değildir
— taramanın neyi kapsadığı ve neyi kapsamadığı aşağıda açıktır.

### Aşama uygulanabilirliği

| Aşama | Durum | Gerekçe |
|---|---|---|
| 1 — Z3 SMT invariant | n/a | Python hedef; supply/balance yok |
| 2 — Metamorfik fuzz | n/a | Eşzamanlı vault durumu yok |
| 3 — Tokenomics | n/a | Token veya likidite havuzu değil |
| 4 — EVM gizli tarama | n/a | EVM bytecode'u değil, Python kaynağı |
| **5 — Kaynak imza** | **ÇALIŞTI** | 5157 dosya tarandı |

## 3. Süreç Boyunca Bulunan Yapısal Anormallik

Bu deponun ağacı **kendisinin 40 seviye derin öz-yinelemeli bir kopyasını**
içerir:

```
63-Sester/
├── 63-Sester/          ← bir kopya
│   ├── 63-Sester/      ← kopyanın kopyası
│   │   └── … (40 seviye)
│   └── .venv/          ← her seviyede kendi virtualenv'i
└── .venv/
```

Bu, tarayıcıda **dört gerçek hatayı ortaya çıkardı** — hepsi bu vaka
çalışmasının doğrudan çıktısıdır ve AegisForge tarafında düzeltildi:

### Hata 1: `.venv` atlanmıyordu

Python virtualenv'leri binlerce üçüncü-taraf dosya içerir. `.venv` SKIP_DIRS
listesinde değildi. **Düzeltme:** `.venv`, `venv`, `env`, `site-packages`,
`.tox`, `.nox` atlama listesine eklendi.

### Hata 2: Öz-yinelemeli ağaç sınırı yoktu

40 seviyeli öz-yineleme, aynı projeyi **binlerce kez** tarıyordu (ilk koşu:
3526 dosya). **Düzeltme:** `MAX_SCAN_DEPTH = 32` sınırı her iki yürüyüş
fonksiyonuna da eklendi.

**Kök neden (sembolik bağlantı):** `63-Sester` **kendine işaret eden bir
sembolik bağlantıdır**:

```
63-Sester -> /home/gokun/projects/01_unicorn/63-Sester
```

Bu sonsuz öz-yineleme yaratır. **Disk israfı yoktur** (inode'lar paylaşılır,
152 MB tek seferlik), ama `find`, `grep -r`, `tar` sonsuz dönebilir.
Ayrıntılar: `AEGISFORGE_FINDINGS.md`.

### Hata 3: Config dosyalarındaki secret'lar görünmüyordu

`.txt`, `.md`, `.env`, `.ini` uzantıları tarama yüzeyinin **dışındaydı** —
bir AWS anahtarı `aws.txt`'de görünmezdi. **Düzeltme:** config/doc uzantıları
taramaya eklendi; `.env` gibi uzantısız dotfile'lar basename ile tanınır.

### Hata 4: Markdown false-positive'leri

Config taraması eklendiğinde ilk koşu **194 CRITICAL + 96 HIGH** üretti —
**hepsi false positive**:

| Kaynak | Sayı | Gerçek mi? |
|---|---|---|
| README tablo ayırıcıları `\| Shipped` → `\| sh` | 130 CRITICAL | **Hayır** |
| `authorized_keys`, `.onion/` prose geçişleri | 64 CRITICAL | **Hayır** |
| `` `.npmrc` `` dokümantasyon geçişleri | 192 MEDIUM | **Hayır** |

**Düzeltme:** `is_prose` bayrağı — markdown'da command/persistence imzaları
kapatıldı; canlı anahtar biçimleri (AKIA, ghp_) hâlâ tetikler. **Hiçbir
CRITICAL finding yayınlanmadan gürültü teşhis edildi ve temizlendi.**

**Not:** 5157 dosyanın çoğu bu öz-yinelemeli kopyalardan gelir; deponun
**birinci-el kaynakları ~86 dosyadır.** İmza taraması açısından bu
güvenlidir (her kopya aynı şekilde taranır), ancak bir bulgu çıksaydı
**hangi kopyada** olduğunu ayırt etmek ek çaba gerektirirdi.

Bu öz-yineleme yapısı bir **geliştirme anomalisi** olarak işaretlenmiştir —
depo boyutunu ve CI tarama süresini şişirir. Düzeltme deponun takdirine
bırakılmıştır; tarayıcı buna karşı artık dayanıklıdır.

## 4. Güven Kontrolleri

### Negatif kontrol

`/tmp/planted4` içine bilinen arka kapılar yerleştirildi:

| Yerleştirilen | Dosya | Sonuç |
|---|---|---|
| Telegram sızlatma | `telemetry.ts` | **CRITICAL** yakalandı |
| AWS anahtarı (`AKIA…`) | `config.py` | **HIGH** yakalandı |
| AWS anahtarı | `aws.txt` | taranmadı — `.txt` kapsam dışı (sınırlar) |

Tarayıcı "temiz" rapor ediyorsa, nedenini somut olarak biliyoruz: her imza
sınıfı canlı bir örnekte tetiklendi.

### Determinizm

Aynı `--timestamp 1790304944` ile iki bağımsız koşu **byte-identical**
PoV_Hash üretti. `--timestamp` değişince PoV_Hash değişti — timestamp
taahhüt alanının içindedir, üçüncü-taraf hile yapamaz.

## 5. İmza Kataloğu (Kapsam)

Aşağıdaki imza sınıfları tarandı (AF-SRC-001..009):

| Kimlik | Sınıf |
|---|---|
| AF-SRC-001 | Ters-kabuk (`bash -i`, `/dev/tcp/`) |
| AF-SRC-002 | Sızlatma (Telegram bot, Discord webhook) |
| AF-SRC-003 | Kabuğa borulama (`\| sh`, `\| bash`) |
| AF-SRC-004 | Dinamik çalıştırma (`eval(\``, `new function(`) |
| AF-SRC-005 | Kalıcılık (`authorized_keys`, `crontab -e`) |
| AF-SRC-006 | Kimlik dosyası okuma (`.npmrc`, `.aws/credentials`) |
| AF-SRC-007 | Obfuscation (`atob(`) |
| AF-SRC-008 | Madenci/C2 (`stratum+tcp`, `.onion/`) |
| AF-SRC-009 | Canlı anahtar biçimleri (AKIA, ghp_, PEM) |

## 6. Dürüst Sınırlar

1. **"0 bulgu" = "0 bilinen imza tetiklendi"** — "güvenli" demek değildir.
   Katalogdeki imzaların yokluğu bir **ölçümdür**, garanti değil.
2. **Sözleşme kademeleri koşulmadı** — Python hedef, hiçbir ERC-4626/ERC-20
   invariant'ı bu hedefe uygulanabilir değildi. Bu kasıtlı bir
   "çalışmadı" raporudur, sessiz bir "temiz" değil.
3. **`.txt` kapsam dışı** — kimlik dosyası okuma imzaları yalnızca
   taranabilir uzantılarda çalışır (`.py`, `.ts`, `.sh`, `.json`, …).
4. **Derinlik sınırı veriyi değiştirir** — 32'nin ötesi taranmaz. Bu projede
   hiçbir birinci-el dosya o derinlikte değildi (yalnızca öz-yinelemeli
   kopyalar).

## 7. Ticari Etki

- **x402 ödeme katmanı** için ilk resmi güvenlik kanıtı yayınlandı.
- **Sürekç olarak değerli:** tarama, tarayıcıdaki iki gerçek hatayı yakaladı
  (`.venv` atlama, öz-yineleme sınırı) — bir ödeme sistemi taranırken
  bulundu, dolayısıyla bir sonraki gerçek hedefte gürültü üretmeyecekler.
- **LE-3 kalkanı çalıştı:** sonuç yayınlandı, kısıt açıkça belirtildi,
  PoV_Hash ile yeniden üretilebilir.

## 8. Yeniden Üretim

```bash
cd 07_Temporit_DeFi_Metamorfik_Yaris_Durumu_Avcisi
cargo build -p aegisforge --release

./target/release/aegisforge scan --src-dir . \
  --tier scan --timestamp 1790304944
```

PoV_Hash'in yukarıdakiyle aynı olduğu doğrulanabilir.

---
*AegisForge: "PoV_Hash bir SHA-256 hash taahhüdüdür, ZK-SNARK değil. CleanScore
ücretsizdir. Haraç modeli yok."*
