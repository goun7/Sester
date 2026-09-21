# SESTER — x402 ↔ AP2 ↔ ACP ↔ UCP Spec Fark Tablosu v3.1 (Mükemmelliyet E1)

> Amaç: adaptör katmanının tasarım girdisi — **dört** oyuncunun farklarının tam
> haritası. v1 (2026-09-11) iki-oyuncuydu; v2 (2026-09-12) ACP'yi ve
> yönetişim-kaymalarını ekledi; v3 (2026-09-12, TUR-2) **UCP'yi (dördüncü oyuncu)**
> ve katman-modeli teyidini ekler. Kanıt-tabanı: `the research memo (2026-09-12)` §2–§3
> + v3-tazelemesi (aşağıda tarihli); SDK uygulama öncesi resmî spec'lerle
> satır-satır teyit şartı sürer (§4 doğrulama-günlüğü).

## 0) Yönetişim-kaymaları (v2→v3)

- **x402 → Linux Foundation** (duyuru 2 Nis 2026; operasyonel 14 Tem 2026):
  yönetim Cloudflare+Stripe; kurucu Adyen/AWS/AmEx — "tek-galip" senaryosu
  zayıfladı, **adaptör-tezi güçlendi**. v3-notu: Cloudflare Agents SDK + MCP
  sunucularına x402-desteği → 63-B için doğal benimseme-kanalı (MCP paid-tools).
- **AP2 → FIDO Alliance** (Google, 28 Nis 2026): mandate-spec takibi FIDO
  kanalına taşındı.
- **ACP** (Stripe+OpenAI, 29 Eyl 2025): Instant Checkout canlı (GA 16 Şub 2026,
  ABD perakende; ~%4 ücret ⚠️ tek-kaynak) — API-metering-odaklı değil,
  perakende-checkout-odaklı.
- **UCP (YENİ · v3):** Google+Shopify'ın Universal Commerce Protocol'ü (açık
  standart, 11 Oca 2026; keşif `/.well-known/ucp`); 24 Nis 2026'da **Stripe,
  Amazon, Meta, Microsoft, Salesforce** Tech-Council'e katıldı —
  perakende-checkout'ta konsolidasyon (ACP'nin yetki-council'i gibi ama daha geniş).
- **Katman-modeli teyidi (Google Cloud blog, 10 Haz 2026):** "ACP ve AP2 rakip
  değil — ACP checkout'u, AP2 ödeme-rızasını (mandate) taşır." → sektör kendi
  katmanlaşmasını kabul ediyor: x402 (ödeme-rayı) + AP2 (yetki/kanıt) +
  ACP/UCP (perakende-checkout). **63-B'nin metering+politika konumu bu dördünün
  de altında — tez dördüncü kez doğrulandı.**

## 1) Konumsal fark (protokolün cevapladığı soru)

| | **x402** | **AP2** | **ACP** | **UCP** |
|---|---|---|---|---|
| Soru | "HTTP isteğinin karşılığını anında nasıl öderim?" | "Ajanın insan adına satın alma yetkisi nasıl yetkilendirilir ve kanıtlanır?" | "Chat-oturumunda perakende satın alma nasıl checkout'a çevrilir?" | "Ajan, perakende platformuyla nasıl keşif→sepet→checkout akışı yürütür?" |
| Katman | Ödeme rayı (request-bağımlı mikro-ödeme) | Yetki+kanıt katmanı (mandate/receipt) | Perakende-checkout katmanı (OpenAI/Stripe hattı) | Perakende-checkout katmanı (platform-tarafsız council) |
| Aktörler | İstemci (ajan) ↔ kaynak sunucu | Kullanıcı ↔ satıcı-ajan ↔ ödemesi-ajan ↔ ödeyici | Kullanıcı (ChatGPT) ↔ OpenAI ↔ satıcı ↔ Stripe | Ajan ↔ satıcı-platformu (Google/Shopify + council) |
| Varsayılan para | Stablecoin (USDC; zincir-agnostik) | Kart/banka/stablecoin — ödeyici nötr | Kart (OpenAI/Stripe hattı) | Satıcı-bağımlı (kart/ödeme-ajanı) |
| Yönetişim | Linux Foundation (2026) | FIDO Alliance (2026) | Stripe+OpenAI ikilisi (açık spec) | Google+Shopify + Tech-Council (Stripe/Amazon/Meta/MSFT/Salesforce, Nis 2026) |

## 2) Alan-bazlı fark tablosu (adaptörün uyarlayacağı yerler)

| Alan | x402 | AP2 | ACP | UCP | Adaptör kararı |
|---|---|---|---|---|---|
| **Tetik** | HTTP 402 + `payment-required` header/challenge | Mandate imzası (intent/cart mandate) | Checkout-session oluşturma (chat-içi) | Platform-checkout (well-known keşif → cart → checkout) | Tetikleyici soyutlaması: `PaymentTrigger` |
| **Yetki modeli** | İstek başı ödeme (ajan cüzdanı doğrudan) | İnsan-çift-imzalı mandate'ler (kanıt zinciri) | OpenAI/Stripe platform-akışı (satıcı tarafında) | Platform-hesap bağlama + checkout-akışı | Yetki modülü AP2'de, yoksa "istek-başı" fallback |
| **Kimlik** | Cüzdan adresi imzası | Mandate imzalayan varlıklar (kullanıcı/satıcı/ödeme) | Satıcı-merchant + OpenAI-oturum kimliği | Platform-kimliği (identity-linking yeteneği) | 68-RobotProof kimlik şemasına köprü |
| **Kanıt** | Zincir işlemi + sunucu onayı | Signed receipt'ler (işlem sonrası kanıt) | Order/receipt webhook kaydı | Order-management kayıtları | Kanıt normalizasyonu → tamga ledger |
| **İade/dava** | Protokol-dışı (uygulama işi) | Mandate şartlarına bağlı süreç | Platform iade/refund akışı | Order-management iade-akışı | İade modülü B-katmanında ortak |
| **Fiyatlama** | Sunucu belirler (header'da quote) | Satıcı-ajan kataloğu/teklif | Satıcı-katalog (merchant feed) | Catalog Search/Lookup yeteneği | Tek fiyat kataloğu, dört formata render |
| **Kimin parası** | Ajanın cüzdanı (kullanıcı önceden yükledi) | Kullanıcının ödeyicisi (kart vb.) | Kullanıcının kartı (OpenAI/Stripe hattı) | Kullanıcının satıcı-hesabı | 63-A cüzdan kural motoru AP2'de "istek-başı limit"e dönüşür |
| **Keşif** | Endpoint başına 402 challenge | Satıcı manifest/ajan keşif akışı | Satıcı manifest/checkout-session | `/.well-known/ucp` (standart-keşif) | 64 `agents.txt` + well-known-alışkanlığına bağlanır |
| **Kapanış-olayı** | Sunucu onayı + zincir-işlemi | Payment receipt | Order/receipt webhook (OpenAI/Stripe) | Order-management durum-güncellemesi | Webhook → ChargeReceipt normalizasyonu |

## 2b) Kart-şebeke katmanı (tek-satır harita)

| Şebeke | Girişim | Tarih | 63 ilişkisi |
|---|---|---|---|
| Visa | Intelligent Commerce — Skyfire/Nekuda/PayOS/Ramp ortakları | 18 Ara 2025 | partner-startup'lar yetki+ödeyici-odaklı; protokol-tarafsız politika-katmanı yok |
| Mastercard | Agent Pay for Machines (yüksek-frekans/düşük-değer makine-ödemesi) | 10 Haz 2026 | mikro-ödeme segmenti — 63-B'nin segmentine teğet geçer |

## 3) Adaptör mimarisi çıkarımları (63 için net kararlar)

1. **Soyutlama çekirdeği:** `ChargeIntent` (fiyat+kimlik+kanıt-istemi) ve
   `ChargeReceipt` (ödeme kanıtı) — her protokol bunlara çevrilir/çevrilir.
   v2: `ChargeIntent` tip-çekirdeği genişler — `per_request` (x402),
   `mandate` (AP2), `checkout_session` (ACP) — üç oyuncu tek soyutlamaya iner.
2. **Yetki katmanı opsiyonel:** x402-only müşteride AP2 mandate yok → cüzdan
   kural motoru (63-A) devrede; AP2 müşteride mandate birincil, cüzdan ikincil;
   ACP'de yetki OpenAI/Stripe tarafında → 63 satıcı-sırasında sayaç+kanıt verir.
3. **Kanıt birleşik:** her üç yolun kanıtı tamga hash-chain'e aynı olay şemasıyla
   yazılır → 81 ve 69 aynı dili okur.
4. **Galip-protokol riski kontrolü:** sadece `ProtocolAdapter` arayüzü şart —
   çekirdek (metering/cüzdan) protokolden bağımsız. v2: üçüncü oyuncu + LF/FIDO
   yönetişim-kaymaları bu tezi üçüncü kez doğruladı (skor-tablosu: ARASTIRMA §8).

## 4) Doğrulama-günlüğü (SDK uygulaması öncesi — ARASTIRMA §9 ile senkron)

| Madde | Durum | Tarih |
|---|---|---|
| x402 yönetişim-teyidi (Linux Foundation: duyuru + operasyonel lansman) | ✅ | 2026-09-12 |
| AP2 yönetişim-teyidi (Google → FIDO Alliance bağışı) | ✅ | 2026-09-12 |
| ACP standart-durumu + Instant Checkout + ücret (⚠️ %4 tek-kaynak) | ✅ | 2026-09-12 |
| Kart-şebekeleri (Visa/Mastercard) + rakip hareketleri | ✅ | 2026-09-12 |
| **v3:** UCP keşif + Tech-Council üyeliği (Stripe/Amazon/Meta/MSFT/Salesforce, 24 Nis 2026) | ✅ | 2026-09-12 (TUR-2) |
| **v3:** Katman-modeli teyidi — "ACP checkout, AP2 consent" (Google Cloud blog, 10 Haz 2026) | ✅ | 2026-09-12 (TUR-2) |
| **v3:** x402 Cloudflare Agents SDK + MCP entegrasyonu — 63-B benimseme-kanalı | ✅ | 2026-09-12 (TUR-2) |
| **v3.1 (2026-09-20): x402 V2 resmî-yayın (24 Haz 2026)** — CAIP-identifiers, dynamic `payTo` routing, multi-facilitator, Extensions, wallet-based-sessions; **header-değişiklikleri: deprecate-X-\* → `PAYMENT-REQUIRED`/`PAYMENT-SIGNATURE`/`SIGN-IN-WITH-X`**; SDK geri-uyumlu-V1 | ✅ araştırma-yapıldı | 2026-09-20 (genişletme-turu) |
| **v3.1 uyumluluk-notu:** Sester-middleware hâlâ `X-Payment`/`X-Payment-Required` (V1) kullanıyor — V2-header'a-geçiş **açık-takip** (break-değil: SDK geri-uyumlu-V1; V2-öneri IETF-hizalı-adlar, zorunlu-sunset-tarihi-yok) | ☐ açık-takip | 2026-09-20 |
| İki sağlayıcının örnek akışlarının uçtan uca elle koşusu (demo API) | ✅ **B-prototip kabulü** — S2 parite (pugio0+AP2+ACP) | 2026-09-12 |
| x402 resmî spec satır-satır: header şemaları + zincir destek listesi (LF repo, tarihli arşiv) | ☐ SDK-öncesi | — |
| AP2 spec satır-satır: mandate türleri + receipt formatı (FIDO kanalı, tarihli arşiv) | ☐ SDK-öncesi | — |
| ACP spec satır-satır: checkout-session + webhook şemaları (açık repo) | ☐ SDK-öncesi | — |
| UCP spec satır-satır: yetenek-şemaları + checkout-akışı (ucp.dev) | ☐ SDK-öncesi | — |
| Bu tablonun satır-satır teyidi ve güncellemesi | ☐ SDK-öncesi | — |

## 5) v3 adaptör-öncelik yeniden-değerlendirmesi (TUR-2)

Kod-gerçekleri (v0.4.0): `register_scheme` Registry'sinde 7+ şema canlı
(`pugio0` [DONUK], `Sester-EVM` [eski adı Sikke-EVM], `exact`, `x402`,
`AP2-Mandate`, `ACP-Session`, `UCP-Checkout`);
AP2 JWS (HS256/ES256) + ACP satıcı-imzası + gövde-bağı testlerle kilitli.

| Protokol | Öncelik | Gerekçe (v3-verisiyle) |
|---|---|---|
| x402 `exact` | **1** (değişmez) | LF yönetişim + Cloudflare Agents SDK/MCP dağıtım-kanalı → vitrin-müşterisi burada |
| AP2 mandate | **2** (yükselmedi, derinleşti) | FIDO standardizasyonu + "consent-katmanı" konumu → mandate-JWS 63'ün politika-motoruyla birebir örtüşür |
| ACP | **3** (satıcı-ucu tamam) | Google teyidi: checkout-katmanı — 63 satıcı-sırasında sayaç+kanıt; buyer-tarafı oturum-üretimi artık `issue_acp_session` |
| UCP | **4 — kodlandı (v0.4)** | Tech-Council geniş ama spec 63'ün request-metering segmentine değil perakende-akışına oturur; **v0.4.0'da adaptör kodlandı**: `UCP-Checkout <b64>` zarfı — satıcı-mühürlü (JWS) + merchant-bağı + `require_ucp_signature` üretim-bayrağı (test_159–166); canlı-trafik hizası ucp.dev SDK'sıyla izlenmeye devam eder |

**Sonuç:** dördüncü oyuncu adaptör-tezini dördüncü kez doğruladı; öncelik-sırası
değişmedi, UCP izleme-listesine girdi (K4-gibi karar-kaydı v0.4'te).
