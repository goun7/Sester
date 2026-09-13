# 63 — AjanTicaretYigini · Araştırma Dosyası 2026-09-12 (Mükemmelliyet E0)

> Amaç: kâğıt-bağındaki (KAGIT/PRD/SPEC_FARK/KURAL_DSL/IS_PLANI) tüm pazar,
> yönetişim, rakip, güvenlik ve mevzuat iddialarının **tarihli + kaynaklı +
> güven-dereceli** kanıt-tabanı. Kural: tek-kaynak (⚠️) veriler SDK/kod kararı
> öncesi ikinci kaynakla teyit edilir — kâğıdın kendi "satır-satır teyit"
> disipliniyle (SPEC_FARK_TABLOSU §4) hizalı.
> Tarama tarihi: **2026-09-12** (web). Önceki veri-tarihi: 2026-04/05 (PRD v1).

## 0) Güven-dereceleri

- **A** = birincil/resmî kaynak (protokol-blog, şebeke basın-bülteni, kurum sitesi)
- **B** = saygın ikincil (Chainalysis, CoinDesk, PRNewswire, hukuk-bülteni)
- **C** = tek-kaynak / analiz-blogu → teyit-şartı işaretli ⚠️

## 1) x402 — kullanım gerçekleri (dürüst küre)

| Veri | Kaynak, tarih | Güven |
|---|---|---|
| 205M+ işlem / ~$53M kümülatif hacim | cryptorank/feed, 27 Ağu 2026 | C ⚠️ tek-kaynak |
| 100M+ kümülatif işlem (Q1 2026 sonu itibarıyla) | Chainalysis, 3 Haz 2026 | B |
| Gerçek hacim ~$28K/gün; çoğu test/"gamed" işlem | CoinDesk, 11 Mar 2026 | B |
| İşlemlerin ~%50'si oyunlaştırılmış (167M settled itibarıyla) | Presenc tracker, 15 May 2026 | C ⚠️ |
| Facilitator kümülatif hacim $26.19M ATI (eski veri-noktası, eğri-için) | sektörel-analiz, 9 Ara 2025 | C |
| Coinbase facilitator ücreti: free-tier sonrası ~$999/ay @1M aylık settlement | Wavect karşılaştırma, 2 Eyl 2026 | C ⚠️ |

**Yorum (PRD §1 + IS_PLANI §2 girdisi):** işlem-sayısı patladı ama dolar-hacmi
bebek; sentetik-işlem oranı yüksek. Bu, "satıcı-altyapısı yok" tezini
güçlendirir (gösteriş-hacmi politikasız ajanı iflas ettirir) ama gelir-tahmini
gerçek-hacim taşıyıcısı üzerine kurulmalı. Karar-metrikleri işlem-sayısı değil:
**gerçek-hacim + aktif-demo** (kill/pivot tetikleri IS_PLANI §2).

## 2) Yönetişim kaymaları (adaptör-priority etkisi)

| Olay | Kaynak, tarih | Güven | 63'e etkisi |
|---|---|---|---|
| x402 → Linux Foundation "x402 Foundation" (duyuru) | LF + CoinDesk, 2 Nis 2026 | A | spec-takip LF repo'ya taşındı |
| x402 Foundation operasyonel lansman | PRNewswire, 14 Tem 2026 | A | çeyreklik sürüm-takibi (IS_PLANI §8) |
| Yönetim: Cloudflare + Stripe; kurucu: Adyen, AWS, AmEx vb. | LF/CoinDesk, 2 Nis 2026 | A | "tek-galip" senaryosu zayıfladı → adaptör-tezi güçlendi |
| AP2 → FIDO Alliance bağışı | Google blog, 28 Nis 2026 | A | mandate-spec takibi FIDO kanalına taşındı |
| Cloudflare: Agents SDK + MCP sunucularına x402 desteği | Cloudflare blog, 23 Eyl 2025 | A | B-katmanı için dağıtım-kanalı adayı |
| Stripe x402'i PaymentIntents + fiat-settlement olarak sarıyor | Wavect, 2 Eyl 2026 | C ⚠️ | B-katmanı entegrasyon-örneği + konum-teyidi |

## 3) Üçüncü protokol: ACP (SPEC_FARK v2'nin yeni bölümü)

| Olay | Kaynak, tarih | Güven |
|---|---|---|
| Stripe+OpenAI "Agentic Commerce Protocol" açık-standart duyurusu + Instant Checkout (ABD) | OpenAI + Stripe newsroom, 29 Eyl 2025 | A |
| Instant Checkout GA 16 Şub 2026; ~%4 işlem-ücreti | sektör-rehberi, 17 Şub 2026 | C ⚠️ ücret tek-kaynak |
| OpenAI strateji-pivotu: perakende-uygulamaları merkeze | DigitalCommerce360, 6 Mar 2026 | B |

**Etki:** 63'ün "protokol-tarafsız adaptör" tezi üçüncü oyuncuyla *güçlenir*;
`ChargeIntent` soyutlamasına "checkout-session" tipi eklenir (SPEC_FARK v2 §3).
ACP API-metering-odaklı olmadığından 63-B birincil rayı x402 kalır.

## 4) Kart-şebekeleri ve rakip hareketleri

| Olay | Kaynak, tarih | Güven |
|---|---|---|
| Visa Intelligent Commerce; ortaklar Skyfire, Nekuda, PayOS, Ramp | Visa basın-bülteni, 18 Ara 2025 | A |
| Mastercard "Agent Pay for Machines" — yüksek-frekans/düşük-değer makine-ödemesi | Mastercard basın-bülteni, 10 Haz 2026 | A |
| Skyfire: KYA ("Know Your Agent") kimlik+ödeme-yetki platformu | skyfire.xyz blog (günc. 8 Eyl 2026) | A |
| Visa → Payman yatırımı; AmEx → Nekuda seed-turu | sektör-derlemesi, ~Ağu 2026 | C ⚠️ |

**Yakınsama tezi (IS_PLANI §1 girdisi):** kimlik (KYA) + yetki (politika) + ödeme
üçlüsü tüm oyuncularda tek-platforma yakınsıyor — ama **hiçbiri protokol-tarafsız,
non-custodial, kanıt-zincirli satıcı-katmanı** olarak konumlanmıyor. Açık hâlâ var.

## 5) Güvenlik literatürü (KURAL_DSL §5 girdisi)

| Bulgu | Kaynak, tarih | Güven |
|---|---|---|
| Prompt-injection üretim-deploy'larının ~%73'ünde görüldü (2025 anketi); kötücül örneklerde %32 artış | zylos araştırma-dosyası, 16 May 2026 | C ⚠️ anket tek-kaynak |
| "Lethal trifecta": özel-veri + dışı-erişim + kontrolsüz-içerik üçlemesi | airia rehberi, 6 Oca 2026 | C |
| AgentSecBench: tool-use bütünlüğü/privacy değerlendirme çerçevesi | AI Security Research derlemesi, May 2026 | C |
| 5 kurgu-belge ile RAG-manipülasyonu ~%90 | getmaxim derlemesi, 2 Haz 2026 | C ⚠️ |

**Yorum:** fail-closed politika-DSL artık "tasarım-zevki" değil
literatür-destekli blast-radius kontrolü — satış-anlatısına resmen girer.

## 6) Makro talep

| Veri | Kaynak, tarih | Güven |
|---|---|---|
| Gartner: 2026 sonunda kurumsal-uygulamaların %40'ı görev-özel ajan gömülü (2025: <%5) | Gartner ikincil-derleme, 2 Tem 2026 | B |

## 7) TR mevzuat — yanlış-etiket koruması

| Konu | Durum, tarih | Kaynak | Güven |
|---|---|---|---|
| Kripto ile mal/hizmet ödemesi | **Yasak — 2021 TCMB düzenlemesi, hâlâ yürürlükte** | TCMB 2021 + hukuk-bültenleri | A |
| KVSP çerçevesi | 7518 (Tem 2024) + SPK tebliğleri (2025): platform-lisansı + denetim | SPK / hukuk-bültenleri | A |
| ⚠️ "28.08.2026 ödeme-yasağı" iddiası | **YANLIŞ-ETİKET:** SPK 52/1589 (28 Ağu 2026) = yatırım-fonu-rehberi değişikliği (i-SPK 128.31 ilke kararı); ödeme-yasağı DEĞİL | SPK mevzuat + sektör-haberi 29 Ağu 2026 | A |

**Kural:** hukuk-görüşü (IS_PLANI §11, açık-soru 1 — önceliği yükseltildi)
2021-yasağındaki "ödeme-aracılığı" tanımını doğrulayacak; kâğıt 2021-yasağını
referans alır, dedikodu-kararı yapılmaz.

## 8) Protokol-savaş skor tablosu (2026-09-12)

| Ölçüt | x402 | AP2 | ACP |
|---|---|---|---|
| Yönetişim | Linux Foundation (Nis/Tem 2026) | FIDO Alliance (Nis 2026) | Stripe+OpenAI ikilisi (açık spec) |
| Momentum | 205M işlem ⚠️ ~%50 oyunlaştırılmış | mandate-pilot aşaması | Instant Checkout canlı (ABD perakende) |
| 63-B ray-uyumu | **yüksek** (istek-başı 402-metering doğal) | orta (mandate-yetki katmanı) | düşük-orta (checkout-oturumu, perakende-odaklı) |
| Ücret-kıyas | facilitator ~$999/ay @1M ⚠️ | n/a (protokol) | ~%4 ⚠️ tek-kaynak |
| TR-mevzuat uyumu | stablecoin=ödeme-aracı sorusu hukuk-görüşüne bağlı | kart/banka → uyumlu | kart/banka → uyumlu |
| **63 kararı** | **birincil adaptör** | **ikincil (yetki-katmanı)** | **izleme + checkout-session tipi** |

## 9) Doğrulama-günlüğü (SPEC_FARK §4 ile senkron)

| Madde | Durum | Tarih |
|---|---|---|
| x402 yönetişim-teyidi (LF: duyuru + operasyonel) | ✅ | 2026-09-12 |
| AP2 yönetişim-teyidi (FIDO bağışı) | ✅ | 2026-09-12 |
| ACP standart + durum + ücret (⚠️ ücret) | ✅ | 2026-09-12 |
| Kart-şebekeleri + rakip hareketleri | ✅ | 2026-09-12 |
| Güvenlik-literatürü taraması | ✅ | 2026-09-12 |
| TR-mevzuat ayrıştırması (52/1589 yanlış-etiket) | ✅ | 2026-09-12 |
| x402 resmî spec satır-satır (header şemaları + zincir listesi, LF repo) | ☐ SDK-öncesi | — |
| AP2 spec satır-satır (mandate türleri + receipt formatı, FIDO) | ☐ SDK-öncesi | — |
| İki sağlayıcının örnek akışlarının uçtan-uca elle koşusu | ☐ B-prototip kabulü | — |

## 10) Kaynak-listesi (tarihli)

1. Chainalysis — "Inside x402: 100M Agentic Payments on Base" · 3 Haz 2026
2. CoinDesk — "Coinbase-backed AI payments protocol… demand not there yet" · 11 Mar 2026
3. cryptorank/feed — 205M işlem / $53M kümülatif · 27 Ağu 2026 ⚠️
4. Presenc — "x402 Protocol Adoption Tracker 2026" · 15 May 2026 ⚠️
5. Wavect — "x402 Payments 2026: Coinbase, Stripe & Alternatives" · 2 Eyl 2026 ⚠️
6. Linux Foundation press + CoinDesk — x402 Foundation duyurusu · 2 Nis 2026
7. PRNewswire — LF x402 operasyonel lansman · 14 Tem 2026
8. Google blog — "AP2 → FIDO Alliance" · 28 Nis 2026
9. Cloudflare blog — "Launching the x402 Foundation" (Agents SDK/MCP) · 23 Eyl 2025
10. OpenAI "Buy it in ChatGPT" + Stripe newsroom — ACP · 29 Eyl 2025
11. Sektör-rehberi — Instant Checkout GA + ~%4 ücret · 17 Şub 2026 ⚠️
12. DigitalCommerce360 — OpenAI checkout-pivotu · 6 Mar 2026
13. Visa basın — "Visa and Partners Complete Secure AI Transactions" · 18 Ara 2025
14. Mastercard basın — "Agent Pay for Machines" · 10 Haz 2026
15. skyfire.xyz/blog — KYA platform-durumu · güncelleme 8 Eyl 2026
16. zylos.ai research — injection istatistikleri · 16 May 2026 ⚠️
17. airia.com — lethal-trifecta rehberi · 6 Oca 2026
18. getmaxim — RAG-manipülasyon derlemesi · 2 Haz 2026 ⚠️
19. Gartner-ikincil-derleme — %40 kurumsal-ajan istatistiği · 2 Tem 2026
20. SPK mevzuat + sektör-haberi — 52/1589 fon-rehberi · 28/29 Ağu 2026
21. TCMB 2021 ödeme-yasağı + hukuk-bültenleri (moral.av.tr, Lexology) · 2021

---
*E0 kapanış: 2026-09-12. Sonraki tarama: çeyreklik (IS_PLANI §8 3.ay ile senkron).*
