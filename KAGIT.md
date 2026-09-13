# 63 — SESTER (AjanTicaretYigini · Agent Commerce Stack)

> Aile: `algoat` (F1 disiplini + platform hattı) · Durum: **KÂĞIT → B-PROTOTİP** · Açılış: 2026-09-11 · **Kimlik: SESTER kesin (2026-09-13; dizisi Pugio → Sikke → Sester — ESKI_KIMLIK.md)**
> Kaynak: `Fikirler.md` §1.1 (AgentMeter) + §2.4 (AgentWallets) + §4.2 (AgentDefense) — **üç fikir tek yığında birleşti**
> Kural: Bu klasör yalnız fikir/PRD geliştirme başlığıdır; kod kararı ayrı verilir.

## Neden birleştirildi (ayrı 3 proje olamaz)

Üç fikir aynı müşteriye (ajan kullanan/yazan geliştirici) aynı mimari yüzeyden
(tool-call ve HTTP-ödeme akışına) dokunuyor:

1. **AgentWallets (72→A)**: ajan cüzdanı, ebeveyn-çocuk anahtar hiyerarşisi, kural
   motoru (limit, beyaz liste, saat aralığı), non-custodial.
2. **AgentMeter (1.1→B)**: x402 uyumlu sayaç + faturalama: per-request fiyat, kota,
   iade, ajan/insan diferansiyel fiyatlaması.
3. **AgentDefense (4.2→C)**: tool-call guvence hattı: izin anomalisi, injection
   skoru, imzalı olay kaydı.

Ayrı yazılsaydı üçü aynı ledger'ı, aynı kimlik modelini, aynı konfigürasyon
katmanını üç kez inşa edecekti. Tek yığında: **cüzdan → sayaç → guvence** aynı
boru hattının üç aşaması.

## Yığın mimarisi (kağıt)

```
[ Ajan ] → [ C Kattı: Tool-call proxy / SDK ] → [ B Kattı: Metering middleware ] → [ Hedef API ]
                 │ imzalı olay kaydı                  │ usage kaydı
                 ▼                                     ▼
            [ tamga hash-chain ledger ] ← ortak kimlik ← [ A Kattı: Ajan Cüzdanı + kural motoru ]
```

- **Boru sırası (inşa):** B → A → C. B en bağımsız ve vitrin değeri en yüksek;
  C, Veridict standardıyla en çok entegre olan katman, en sona.
- **Protokol nötrlüğü:** x402 + AP2 adaptör katmanı; galip protokol değişirse
  sadece adaptör değişir.
- **Ledger:** tamga-protocol hash-chain (01-KokProtocol) olay/imza katmanı olarak
  kullanılır — yeniden icat edilmez.

## Gelir modeli (tek yığın)

- OSS çekirdek (Apache-2.0): SDK + middleware + CLI.
- Pro: self-hosted panel (cüzdan kural motoru UI + metering rapor + olay inceleme).
- Veridict hattıyla uyum: guvence sertifikası ileride "watcher" ekosistemine bağlanabilir.

## Sinerjiler

- **tamga-protocol**: olay ledger'ı → vitrin kredisi iki yöne akar.
- **MERGEN**: proxy'nin ilk barındırıcısı (dogfood).
- **F1 botları**: kendi ajanlarına limit/sayaç takmak = ilk gerçek kullanım.
- **74-LocalMesh** (b2b): bu yığının ödeme katmanını kullanacak ilk müşteri adayı.

## İlk sürüm (hafta sonu ölçeği) — B Kattı

FastAPI middleware → x402 el sıkışması → SQLite usage ledger → basit panel
(kim, kaç çağrı, ne kadar). Başarı ölçütü: kendi bir ajanını ücretli endpoint'e
bağlayıp ilk mikro-ödemeyi kesmek.

## Riskler

- x402/AP2 standart kayması → adaptör katmanı zorunlu mimari kural.
- Custody/kvkk: cüzdan katmanı **non-custodial** tasarlanmak zorunda (⚖️).
- Büyük bulut benzer özellik gömerse → self-host + protokol nötrlüğü + OSS itibarı ile ayakta kal.

## 💰 Vergi kanalı (hook)

OSS çekirdek sponsorluğu → **GVK Mük. 20/B** (%15 banka stopajı, deftersiz) ·
Pro lisans (yurt dışı) → **Şahıs + GVK 89/13** (%0, MoR e-fatura KDV %0) ·
ajan/kripto mikro-ödeme tahsilatı → **Kripto tahsilat prosedürü §4** (lisanslı
borsa çevrimi + şerhli fatura + banka transferi).
Kanonik çerçeve: `../../Yeni Fikirler/VERGI_KANAL_CERCEVESI.md`.

## 🏆 Mükemmelliyet kapanışı (100/100) — 2026-09-11

**Hat/IP (E3):** 🦄 unicorn hattı — çekirdek (metering+cüzdan motoru) şirket IP'si;
OSS vitrin katmanı (SDK örneği + x402 middleware tek-dosya sürümü) Apache-2.0
kalır (vitrin itibarı şahside, ticari derinlik şirkette — katman ayrımı
kuruluşta yazılı hale gelir). Şahıs dönemi kodu: bireysel telif → katkı-tablosu
ile şirkete devir (CIFT_HAT_PLANI §4). ⚖️ Non-custodial mimari ZORUNLU kural:
parayı asla tutmayız; custody lisans alanı dışındayız.

**Operasyon sözleşmesi (E4):** demo koşuları + sayaç L3 (otomatik); müşteri
onboarding + vitrin lansmanı insan (L0/L1). Escalation: adaptör şema-teyit
başarısızlığı (SPEC_FARK_TABLOSU §4 maddeleri) → SDK uygulaması durur.
Kill kriteri: 2-3 vitrin kurulumundan ≥2 aktif demo çıkmazsa → B-katı dondur,
sadece spec/sinıf kütüphanesi olarak devam.

**Ölçüm/kanıt planı:** vitrin benimseme (kurulum→aktif-demo sayıları) haftalık
→ `docs/adoption_log.md`; protokol-teyit arşivi → SPEC_FARK_TABLOSU §4
(tarihli); kural-DSL test vektörleri → KURAL_DSL_V0.md §4. Sonuç: **10/10
unsur dolu → başlama izni: 81 sonrası B-blok sırası.**

## Sonraki adımlar

1. ~~Bu dosyayı PRD'ye büyüt: katman A kural motoru şeması (DSL taslağı).~~ ✅ PRD v1.1 + KURAL_DSL_V0
2. ~~x402 + AP2 spec fark tablosu çıkar~~ ✅ SPEC_FARK_TABLOSU v2 (ACP dahil üçlü)
3. ~~B Kattı prototipi için ayrı karar kaydı aç.~~ → **SESTER-B v0 kodlandı** (`KARAR_63B.md`, `sester/`)

## İSİM: SESTER (2026-09-13; dizisi Pugio → Sikke → Sester)

Ürün-adı **SESTER** (Sestertius'tan): Antik Roma'nın ilk standart ticaret sikkesi —
"herkesin kabul ettiği değer-ölçüsü" = ajan-ticaretinde herkesin kabul ettiği
metering+kanit katmanı. Sikke adı İngilizce fonetik riski ("sick") nedeniyle elendi;
Pugio ekosistem-kalabalığı nedeniyle elenmişti. Tarama: PyPI/Crates/NPM/.ai/.io
**%100 temiz**. Kablo-alanları donduruldu (`pugio_bundle_version`, `pugio0`,
`pugio_evidence_bundle`, `source:sikke` — ESKI_KIMLIK.md). Logo: `brand/sester-mark.svg`
+ `brand/sester_primary_logo.jpg`.


## 🎯 TUR-2 PRENSİP (2026-09-11, video-taraması)

- **P5 model-kişilik:** 63-A kural-DSL fail-closed semantiği zaten "emir-görevli" disiplininde; ajan-motoru seçiminde model-kişilik tablosu (VIDEO_ANALIZI_TUR2 §3) TADAD-önerilerine eklendi.
- **P6 fork-test:** 63-B vitrininin x402-adaptör testleri anvil-fork ile koşulur (88-Ustafirin'in katmanı ortak).
- **P8 1-yaz-10-test:** kural-DSL'e her kural için test-vektör şartı — imzasız kural canlıya çıkmaz (KURAL_DSL_V0 test maddeleriyle hizalı).
- **V4-uYARI:** Clanker-tipi kontratların admin-mint/burn "güven-ince-dokunuşu" çıkarması 63-B vitrininin konum-cümlesini güçlendirdi: "custodial yok + kod-ne-kadar-az" anlatısı.

## 🌐 TUR-3 (2026-09-12, web-taraması — kanıt: ARASTIRMA_2026-09-12.md)

- **Yönetişim-kaymaları:** x402 Linux Foundation'a geçti (Nis/Tem 2026;
  Cloudflare+Stripe yönetim, Adyen/AWS/AmEx kurucu); AP2 FIDO Alliance'a
  bağışlandı (Google, Nis 2026). "Tek-galip protokol" senaryosu zayıfladı →
  **protokol-tarafsız adaptör tezi üçüncü kez doğrulandı**.
- **Üçüncü oyuncu ACP:** Stripe+OpenAI Agentic Commerce Protocol (Eyl 2025) —
  Instant Checkout canlı (Şub 2026). SPEC_FARK_TABLOSU v2 üçlü-tabloya büyüdü;
  `ChargeIntent` tip-çekirdeği `checkout_session` ile genişledi.
- **Dürüst-küre kuralı:** x402 205M+ işlem ama gerçek-hacim ~$28K/gün,
  ~%50 oyunlaştırılmış (Mar/May 2026) → karar-metriği işlem-sayısı değil
  **gerçek-hacim + aktif-demo**; IS_PLANI §2'ye hacim-taban pivot-tetikleyicisi
  eklendi.
- **Rakip-yakınsama:** Skyfire-KYA + Visa/Payman + AmEx/Nekuda — kimlik+yetki+
  ödeme tek-platforma yakınsıyor ama protokol-tarafsız satıcı-politika-katmanı
  hâlâ boş; kart-şebekeleri (Visa Intelligent Commerce, Mastercard Agent Pay
  for Machines) segmente teğet.
- **Mevzuat-nerdi notu:** "28.08.2026 ödeme-yasağı" çıkışı yanlış-etiket
  (SPK 52/1589 = fon-rehberi); kripto-ödeme yasağı hâlâ 2021 TCMB düzenlemesi —
  hukuk-görüşü önceliği yükseltildi (IS_PLANI §11).