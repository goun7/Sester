# İS PLANI — 63 · SESTER (AjanTicaretYigini) (2026-09-11, kimlik-göçü 2026-09-13: ESKI_KIMLIK.md)

> Mükemmelliyet V2 katmanı. V1: `KAGIT.md` + `PRD.md` + `SPEC_FARK_TABLOSU.md`
> (x402↔AP2 adaptör-kararları) + `KURAL_DSL_V0.md` (fail-closed cüzdan-politikası)
> + Hat/IP + operasyon. Bu dosya stratejik katmanı doldurur.
> **v2.1 veri-tazeleme (2026-09-12):** rakip-tablosu, birim-ekonomi benchmark'ı,
> tehdit-modeli ve pitch-verileri `ARASTIRMA_2026-09-12.md` ile tarihli
> kaynaklandı; SPEC_FARK v2 üçlü-tabloya (x402↔AP2↔ACP) büyüdü.
> Üst: `CIFT_HAT_PLANI.md` (🦄 · unicorn-hat ticaret-rayı), VERGI (₿-tahsilat §4).

## 1) Rekabet-stratejisi

**Kategori:** ajan-ticaret rayı: cüzdan + sayaç + güvence (x402/AP2/ACP üstü adaptör-katman).

| Rakip-tipi | Örnekler | Ne yapar | Bizim açığımız |
|---|---|---|---|
| Protokol-düzey oyuncular | x402-uygulayıcıları, AP2-ekosistem | protokol-kütüphanesi | **protokol-tarafsız adaptör**: hangisi kazanırsa kazansın ray aynı |
| Ajan-ödeme-startup'ları | Skyfire (KYA-platform, günc. 8 Eyl 2026), Payman (Visa-yatırımlı), Nekuda (AmEx-seedli) | kimlik (KYA) + yetki + ödeyici tek-platforma yakınsıyor | non-custodial + protokol-tarafsız politika-katmanı (KURAL_DSL) + kanıt-zinciri — yakınsama bizim ekseni doğrular |
| Kart-şebekeleri | Visa Intelligent Commerce (Skyfire/Nekuda/PayOS/Ramp, Ara 2025), Mastercard Agent Pay for Machines (Haz 2026) | ödeyici-sonu + şebeke-standardı | satıcı-sırasında politika+metering+kanıt yok — segmente teğet geçiyorlar |
| Hyperscaler-bundle | Cloudflare Agents SDK x402 desteği (Eyl 2025), Stripe x402-sarmalayıcı (⚠️ teyit-edilecek) | dağıtım + ödeme-primitifleri | bundle satıcı-politikası vermez; katmanımız üstünde çalışır — rakip değil, kanal adayı |
| Klasik-fintech köprüleri | Stripe-agent-odaları | kredi-kartı-hattı | stablecoin-doğal + ajan-mikro-ödeme (x402-402-akışı) |
| Kendi-kur | firma-içi ajan-ödemesi | dağınık | standart + 81-güvence + tamga-kanıt tek-boru |

**Konumlanma:** "Protokol-savaşı sürerken, kazananın-altındaki rayı kuran taraf
biz oluruz — cüzdan+sayaç+kanıt tek boru."
**Hendek:** (a) SPEC_FARK adaptör-decisyonları (ChargeIntent/ChargeReceipt soyutlama),
(b) KURAL_DSL fail-closed politika (kurumsal-satışta şart), (c) 81-güvence ile
aynı kanıt-zinciri. **Ne yapmayız:** custodial-cüzdan (63 tezine ters), kendi-token
(yok), protokol-fork (adaptör kalır).

## 2) Birim ekonomisi

| Kalem | Değer | Not |
|---|---|---|
| Sürüm-1 (63-B AgentMeter) | 4 B-blok hafta | PRD |
| Altyapı | ~$30/ay | node-RPC + imza-servisi |
| Onboarding | 3 saat | politika-yazımı + cüzdan-bağlama |
| Fiyat (63-B giriş) | %0,5 + $99/ay | işlem-üstü + sabit |
| Marj | >%85 | SaaS + RPC-değişken maliyet |
| Benchmark | Coinbase facilitator ~$999/ay @1M settlement ⚠️; ACP ~%4 ⚠️ | dürüst kıyas: $999 düz-ücret yüksek-sepetli hacimde daha ucuz ama **yalnız ray** — politika+metering+kanıt dahil değil; 63'ün %0,5'i katman-değerini fiyatlar. ACP %4 = üst-bound referansı |
| Başabaş | ~2 müşteri | unicorn-hat: ilk-yıl gelir-baskısı yok |
| Hacim-taban-tetikleyici | gerçek-hacim ~$28K/gün (Mar 2026), ~%50 oyunlaştırılmış | pilot zamanına kadar gerçek-hacim QoQ büyümezse → "politika-katmanı-her-ray" pivotu (x402-tek-ray bağımlılığı düşer) |

## 3) Fiyat paketleri

| Paket | Kapsam | Fiyat |
|---|---|---|
| Open-source | adaptör-kütüphanesi + DSL-yorumlayıcı | $0 (Apache-2.0) |
| Meter | sayaç + rapor + politika-UI | $99/ay + %0,5 işlem |
| Ray | çok-ajan + politika-orkestrasyonu + 81-kanıt | $499/ay + %0,3 |
| Kurumsal | kendi-altyapı + SLA + 73-sertifika | yıllık $24K+ |

## 4) Müşteri yolculuğu

OSS-kütüphane-çekimi → GitHub-yıldız/issue → dogfood-vaka (F1-botlarına-limit)
→ ilk-kurumsal-pilot ("ajan-filom x402'ye çıkacak, politika-gerekiyor") → Ray-paketi.
**Ölçüm:** OSS→pilot dönüşümü, politika-yazım-süresi, işlem-ortalaması, kanıt-okuma-oranı.
**Kayıp-anı:** DSL-öğrenme-yükü → hazır-şablon kütüphanesi (kısa-politika-bankası).

## 5) Tehdit modeli

| Tehdit | Vektör | Önlem |
|---|---|---|
| Anahtar-tehlikeye | ajan-cüzdan-key sızması | non-custodial + fail-closed + 24s gevşetme-gecikmesi (KURAL_DSL_V0) |
| Protokol-kayması | x402/AP2/ACP-üç-taraflı değişim | adaptör-soyutlama + SPEC_FARK v2-takip (çeyrekte: LF + FIDO + ACP-repo kanalları) |
| İşlem-kanıt-red | müşteri-işlemi-inkârı | tamga-zincir + 81-imzalı-kanıt-bundle |
| Sayaç-hilesi | ajan-sayacı-ayarlama | sayaç-imza + sunucu-tarafı-doğrulama |
| Regülasyon | stablecoin-ödeme mevzuatı | ⚖️ vergi-çerçevesi §kripto + hukukçu-görüşü (kurumsal-öncesi) |
| OSS-tehdit | kütüphane-sahte-PR | imzalı-commit + RFC-akışı |
| ACP-kapanıklığı | checkout-akışının platform-içi yetkisi | satıcı-sırası metering+kanıt odaklı kalır; perakende-pivotu izlemede (SPEC_FARK v2 §3) |
| Gösteriş-hacim yanılsaması | ~%50 oyunlaştırılmış işlem-metriği karar-vericiyi yanıltır | karar-metriği = gerçek-hacim + aktif-demo (ARASTIRMA §1) |
| Foundation-standartlaşma gecikmesi | LF x402 / FIDO AP2 süreç-yavaşlığı | adaptör çekirdeği stable-spec üstünde; yeni sürümler adaptör-altında izole |

## 6) Veri modeli

`wallet_policy` (KURAL_DSL-yaml) · `charge_intent` (ChargeIntent) ·
`charge_receipt` (ChargeReceipt) · `meter_reading` (sayaç, imzalı) ·
`evidence_ref` (81-bundle-hash) — kanıt-yazma: tamga-zincir (68 KIMLIK_SEMASI ile
hizalı kimlik-sahası). 68-kimlik şeması 63'ün cüzdan-kimliğini taşır (aynı 🦄-hat
içi kontrat).

## 7) Kabul senaryoları

1. **S1:** F1-botlarından birine politika: günlük-$50-cap + saat-aralığı → fail-closed canlı.
   ✅ **2026-09-12 KABUL:** `scripts/s1_dogfood.py` — 5×$9.99 → 200; 6. → 402
   quota; 23:30 → 402 saat-dışı; bilinmeyen-host → 402; kanıt-bundle SAĞLAM
   (`adoption/s1-kanit-bundle.json`, deterministik saat-enjeksiyonuyla tekrar-runnable).
2. **S2:** aynı işlem x402-ve-AP2-simülatörden geçirilir → aynı ChargeReceipt.
   ✅ **2026-09-12 KABUL:** `scripts/s2_protocol_parity.py` + test_107 —
   pugio0 + AP2-mandate + ACP-session üç yolu, tek mantıksal işlem: üçü 200,
   ChargeReceipt çekirdeği (agent, host, amount) birebir aynı; ortak-cüzdan
   tek-kota (0.15 = 3×0.05); zincir SAĞLAM. (K4 adaptörlerinin canlı-kanıtı.)
3. **S3:** politika-gevşetme talebi → 24s-gecikme + imzalı-onay akışı çalışır.
   ✅ **2026-09-12 KABUL:** `sester/policy_signed.py` + test_118–128 — JWS-mühürlü
   politika-zarfları (HS256/ES256); sıkılaştırma anında geçer, gevşetme
   `signed_at + 86400` vadesi dolmadan uygulanmaz (deterministik saat ile tam
   gecikme-senaryosu test_123); bekleyen gevşetme kararlara sızmaz (test_124);
   bozuk/imza-dışı zarf son-iyi-durumu korur (test_125).
4. **S4:** 81-kanıt-bundle harici-doğrulanır (63↔81 kontratı canlı).
   ✅ **2026-09-12 ilk-adım:** `sester/evidence.py` + `scripts/dogrula.py` —
   alıcı kütüphanesiz pür-sha256 doğrular; inkâr-saldırısı proof-uyuşmazlığıyla
   yakalanır (test_48–54). 81-MERGEN tarafının aynı şemayı okuması kalan adım.
   ✅ **2026-09-12 K1/Tamga-ucu:** çıpa-alıcı Tamga repo'sunda canlı (test_74–76).
   ✅ **2026-09-13 kardeşsiz-kanıt:** gömülü ayna-alıcılar (`bridge_receivers/`,
   pür-stdlib, kopya-hazır) + test_bridges_mirror — donuk zarf-sözleşmesi
   kardeş-repo makinede olmasa da her koşumda regresyona-sabit (test_186-öncesi seri).
   ✅ **2026-09-12 KAPANDI:** 81-tarafı yerel-okuyucu — Tamga repo'sunda
   `tamga_pugio_ingest.py`: K0 bundle'ını pür-stdlib doğrular + deterministik
   doğrulama-makbuzu üretir   (test_136–140: temiz→SAĞLAM+makbuz, kazınmış→RED
   makbuz-üretimsiz, başlık-yalanı→RED). 63↔81 kontratı iki-ucundan canlı.
5. **S5 (tanım 2026-09-13; kodlandı aynı gün):** Hosted-facilitator MVP
   (MONETIZATION lane-1) — verify/settle/refund-servisi + satıcı-metering'i
   (dogfood) + settlement-batch entegrasyonu; tasarım+test-haritası:
   `docs/S5_FACILITATOR_MILESTONE.md`, ortak-sözleşme: `docs/S6_JOINT_ACCEPTANCE.md`
   (64-Tenderix ile; 63-tarafı test_186–201 kodlu). Durum: **kodlandı —
   koşu-kanıtı publish-gate'e bağlı**.

## 8) Çeyreklik haritası

- **1.ay (81-sonrası):** OSS-adaptör v0.1 + F1-dogfood + politika-şablon-bankası.
- **2.ay:** 81-entegrasyon + ilk-kurumsal-pilot-görüşmesi (🦄-hat satış-deneği).
- **3.ay:** Meter-paketi + SPEC_FARK v3 (çeyreklik-protokol-takibi: LF x402
  sürüm-notları + FIDO AP2 mandate-evrimi + ACP webhook-şemaları — ARASTIRMA
  çeyreklik taramasıyla senkron).

## 9) Pitch paketi

**Dönüşüm:** "Ajanınız ödeyecekse, kuralları siz koyarsınız — protokol-ne-olursa-
olsun, cüzdan+sayaç+kanıt tek rayda." **Marka:** SESTER · Sester-sikkesi
(coin + S-monogram; mürekkep+eski-altın) — palet ve kullanım `brand/MARKA_NOTU.md`.
Demo-script: (1) politika-yazımı (3-dakika), (2) x402-canlı-ücret-akışı,
(3) 81-kanıt-bundle-doğrulama. One-pager: dönüşüm + non-custodial-tez + DSL-örnek +
fiyat + protokol-tarafsızlığı. **Tarihli-kanıt satırları:** kurumsal-uygulamaların
%40'ının 2026 sonunda görev-ajanı gömülü olması (Gartner-derleme, Tem 2026) ve
üretim-deploy'ların ~%73'ünde prompt-injection görülmesi (2025 anketi, ⚠️
tek-kaynak) → politika-katmanı güven-hikâyesinin kanıtı (KURAL_DSL §5).

## 10) Ekip/otonomi tetikleyicileri

- OSS-yıldız ≥ 500 → devrel-içerik ekip-işi.
- İlk kurumsal-pilot → 🦄-kuruluş-tetikleyicisi (CIFT_HAT §tetikleyici #2).
- x402/AP2-galip-belirsizliği çeyrekte → SPEC_FARK v2 + adaptör-haritası-güncelleme.

## 11) Açık sorular

1. ⚖️ **Öncelik yükseltildi (2026-09-12):** Stablecoin-ödeme-aracılığı
   mevzuat-görüşü (kurumsal-pilot öncesi). 2021 TCMB kripto-ödeme yasağı
   yürürlükte — görüş "ödeme-aracılığı" tanımını netleştirecek (ARASTIRMA §7).
2. OSS-lisans kararı: Apache-2.0 vs AGPL (çift-lisans-stratejisi ile).
3. 68-kimlik-şeması ile cüzdan-kimlik-contract'ının dondurulması (63↔68 ortak-karar).

> Not (2026-09-12): "28 Ağustos 2026 ödeme-yasağı" çıkışı **yanlış-etiket** —
> SPK 52/1589 yatırım-fonu-rehberi değişikliği; ödeme-yasağı hâlâ 2021 TCMB
> düzenlemesi (ARASTIRMA §7). Kanal-kararı dedikoduya değil, hukuk-görüşüne bağlanır.

---
*V2 kapanış: 2026-09-11 · v2.1 veri-tazeleme: 2026-09-12. Bağımlılık: 81-MERGEN-dogfood (kanıt-zinciri S1).*
