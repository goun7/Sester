# SESTER — PRD v1.1

> Durum: **B-KATI PROTOTİP ONAYLANDI** (2026-09-20, kullanıcı-kararı) · Tarih: 2026-09-11 · **v1.1 veri-tazeleme: 2026-09-12**
> **Onay-kanıtı (2026-09-20):** 258 passed/25 skipped/0 failed · guard rc=0 · üç-repo HEAD==origin · cross-repo CI-job'ı-ilk-kez-etkin (run `35527689113`) · GitHub derin-sızıntı-denetimi temiz (4/5 yöntem-sınırı-kapalı). **Açık-takip:** üretim-dağıtımı-yok (Docker demo-etiketli); facilitator-varsayılan-secret fail-closed-yapılacak (bkz. `docs/GITHUB_LEAK_AUDIT.md` x402-bölümü).
> Üst belgeler: ``docs/adr/0002`` · `the research memo (2026-09-12)` (tüm sayıların kanıt-tabanı) · `../../Yeni Fikirler/HAVUZ_DEGERLENDIRMESI_2026-09-11.md`
> **Dönüşüm cümlesi:** "Ajan/API satan geliştiricilerin, kullanım başına ücreti
> (x402) tek middleware ile kesip, ajanlara harcama limitli cüzdan ve olay
> kaydı vermesini sağlarım."

## 1) Problem

x402 rayı canlı: **205M+ işlem / ~$53M kümülatif (Ağu 2026)**; Linux Foundation
çatısında (Nis/Tem 2026) Stripe/Cloudflare/AWS/Adyen/AmEx destekli. Ama dürüst
küre: gerçek hacim ~**$28K/gün** (Mar 2026) ve işlemlerin ~%50'si
oyunlaştırılmış — yani **işlem-sayısı patlamış, ticari-hacim bebek**.
İki kutuplu gerçek, tezi keskinleştirir: gösteriş-hacmi politikasız ajanı
iflas ettirir; **satıcı altyapısı** (sayaç, kota, ajan-farklılaştırmalı fiyat,
cüzdan, izin, olay kaydı) hâlâ herkes için ayrı inşaa. Bizim katman bunu üç
modülde verir: A (cüzdan+kural), B (sayaç+fatura), C (guvence proxy — 81 ile
ortak çekirdek). Makro rüzgâr: Gartner'a göre 2026 sonunda kurumsal-uygulamaların
%40'ı görev-özel ajan gömülü (2025: <%5).

> 📊 **Veri-disiplini:** tüm pazar-sayıları `the research memo (2026-09-12)` §1'e
> kaynaklıdır; işlem-sayısı değil gerçek-hacim + aktif-demo kararı belirler
> (kill/pivot tetikleri `docs/adr/0001` §2'de).

## 2) Sürüm tablosu (inşa sırası B→A→C)

| Hafta | Çıktı | Kabul ölçütü |
|---|---|---|
| 1 | **B:** FastAPI middleware — x402 el sıkışması + usage ledger (SQLite) | Demo API'ye bir ajan ücretli istek attı; kayıt oluştu |
| 2 | **B:** kota + iade + panel (basit HTML tablo) | Kota aşımı 402 döndürür; iade kaydı düzgün |
| 3 | **A:** non-custodial alt-anahtar üretimi + kural DSL v0 (limit/beyaz liste/saat) | Kural ihlali engellenen istek + ledger olayı |
| 4 | **C v0:** tool-call imzalama → tamga hash-chain'e olay | MERGEN tool çağrısı imzalı olarak zincire düşer |

## 3) Kod-öncesi talep testi

- Vitrin hedefi doğrulama: 2-3 OSS projesine "kendi API'ne x402 tak" teklifi
  (dogfood istekli). + 5 ajan-geliştiricisi DM'i (Discord/X üzerinden).
- Huni: 5 vitrin kurulumu → ≥2 aktif demo → GitHub yıldız sinyali (G1 benzeri).
- Not: gelir testi değil **benimseme testi** — G puanı düşük olduğu için
  burada ölçülen şey vitrin itibarıdır.

## 4) Mimari özet

- Protokol adaptör katmanı: **x402 ↔ AP2 ↔ ACP** fark tablosu (protocol survey_TABLOSU
  v2) — üçüncü oyuncu ACP (Stripe+OpenAI, Instant Checkout Şub 2026) adaptör
  tezini güçlendirdi; birincil ray x402, yetki-katmanı AP2, ACP izlemede.
- Yönetişim-girdi: x402 → Linux Foundation; AP2 → FIDO Alliance (Nis 2026) —
  spec-takip kanalları güncellendi (ARASTIRMA §2).
- Referans-implementasyon notu: Stripe x402'i PaymentIntents/fiat-settlement
  olarak sarmalıyor (⚠️ teyit-edilecek) — B-katmanı entegrasyon-örneği.
- Ledger: tamga hash-chain; cüzdan **non-custodial** (anahtar kullanıcıda).
- Tek-dosya CLI (pkgforge kültürü) + kütüphane dağıtımı (PyPI).

## 5) 💰 Vergi kanalı (hook)

OSS sponsorluk → **20/B**; Pro lisans (yurt dışı) → **MoR+89/13**; ajan-mikro-ödeme
kripto tahsilatı → §4 prosedürü (lisanslı borsa çevrimi + şerhli fatura).
Detay: `../../Yeni Fikirler/VERGI_KANAL_CERCEVESI.md`.

## 6) Riskler

| Risk | Önlem |
|---|---|
| Ray kayması (x402/AP2 evrimi) | Adaptör katmanı; tek galibiyet senaryosuna bağlanma |
| Custody/regülasyon ⚖️ | Non-custodial zorunlu mimari kural; kullanıcıdan parayı asla tutmama |
| Vitrin ilgisizliği | MERGEN/tamga/Veridict ekosisteminde iç-talep zaten var (dogfood) |
| Gösteriş-hacim yanılsaması | gerçek-hacim takibi + `docs/adr/0001` §2 hacim-tetikleyicisi (ARASTIRMA §1) |
| Protokol-sayısı artışı (ACP) | `ProtocolAdapter` arayüzü + protocol survey v2 üçlü-tablo |
