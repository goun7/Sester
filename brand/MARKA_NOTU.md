# SESTER — Marka Notu (v2 revizyonu, 2026-09-14; kimlik-dizisi Pugio → Sikke → Sester)

> 63 · Agent Commerce Stack'in ürün-adı **SESTER** (kesin, 2026-09-13).
> Kimlik-tarihi ve donuk-alan kararları: `../ESKI_KIMLIK.md`.
> **v2-marka (2026-09-14): "Chain-S" (aday-E) kurucu + ajan ortak-seçimi ile
> kabul edildi** — v1 halka-sikke markası (`sester-mark.svg`) arşive düştü.

## 1) İsim-gerekçe

- **Sester** (Sestertius'tan): Antik Roma'nın ilk standart ticaret sikkesi —
  imparatorluğun "herkesin kabul ettiği değer-ölçüsü". SESTER'nun teziyle birebir:
  ajan-ticaretinde herkesin kabul ettiği **metering + kanıt** katmanı.
- Kısa (6 harf), Latin-alfabeli global-okunuş temiz; fintech/protokol tonu.
- **Tarama (2026-09-13):** PyPI, Crates, NPM, .ai, .io tescillerinde **%100 temiz**.
- Önceki ad Sikke, İngilizce fonetiğinde "sick" çağrışımı nedeniyle elendi;
  Pugio bilinen ekosistem-kalabalığı (pugio.js, ASUS ROG Pugio) nedeniyle elenmişti.

## 2) v2-marka: Chain-S (aday-E)

**Anlam:** S harfi ile hash-chain bağının çift-okuması — ürünün çekirdek tezi
(hash-chain kanıt-defteri) şeklin içinde. Sikke/mühür dili taşımaz; jenerik-tech
görsel-dili (gradient-küre, maskot, ışıksal-parlama) taşımaz.

**Seçim-kanıtı (ağırlıklı-kriter tablosu, 11 puan-tartısı):**

| Aday | 16px | Mono | Anlam | potrace | Koyu-zemin | Toplam |
|---|---|---|---|---|---|---|
| A — Coin | 2 | 5 | 4 | 3 | 4 | 38 |
| B — Ledger Seal | 4 | 5 | 3 | 4 | 5 | 44 |
| C — Balance | 1 | 4 | 3 | 2 | 3 | 27 |
| D — Receipt | 3 | 5 | 4 | 3 | 4 | 41 |
| **E — Chain-S** | **5** | **5** | **5** | **5** | **5** | **54** |

**Üretim-hattı (1:1 sadakat kanıtlı):** ChatGPT 5-aday sayfası (`logo.png`) →
E-hücresi bağlı-bileşen izolasyonu (etiket/küçük-lockup hariç) → ×4 LANCZOS
upscale → eşik-bitmapi → `potrace` (tek-path, flat) → `brand/sester-mark-v2.svg`
→ **trace-round-trip IoU 0.9924** (Tamga-standardı ≥0.99; vektör girdi-bitmapiyle
1:1). Kaynak-sayfa yumuşaklığı nedeniyle sayfa-üzeri IoU 0.97/16px 0.96 —
potrace-disiplini için ölçüm round-trip'tir.

## 3) Palet

| Rol | Hex |
|---|---|
| Mürekkep (birincil) | `#171717` |
| Eski Altın (vurgu) | `#B8860B` |
| Parşömen (zemin) | `#F5F0E4` |
| Parlak Altın (alternatif vurgu, koyu zemin) | `#C9A227` |

## 4) Kullanım kuralları

- **Tek-kaynak:** `brand/sester-mark-v2.svg` (tek-path, `fill`-tabanlı,
  `currentColor`-çevrilebilir). Tüm raster ikizler bu dosyadan üretilir
  (`scripts/make_brand_assets.py`, fail-loud).
- **Koyu zemin:** `fill="#171717"` → `#F5F0E4` (mürekkep↔parşömen çevrimi).
- **Min. boyut:** 16px (favicon) — Chain-S tek-blok silüeti bu boyutta okunur
  (aday-taramasındaki en-yüksek 16px-puanı).
- **Wordmark:** "SESTER" harf-aralıklı serif (tracking) + mark-partner.
- **AI-jenerik yasağı:** gradient-küre, maskot, yarıçapsal parlama kullanılmaz.

## 5) Varlık-listesi

| Dosya | İçerik |
|---|---|
| `sester-mark-v2.svg` | **Ana marka (v2 Chain-S)** — potrace tek-path, 1:1 |
| `../.github/assets/og.png` | Sosyal-önizleme 1280×640 (v2-marka ile üretildi) |
| `../.github/assets/avatar.png` | Org-avatar 512×512 |
| `../.github/assets/favicon-{16..512}.png` + `.ico` | Favicon-ailesi (tek-kaynaktan) |
| `../sester/panel.py MARK_SVG` | Panel/ürün içi gömülü kopya (v2 ile senkron) |
| `sester-mark.svg` | **Arşiv** — v1 halka-sikke markası (kullanılmaz) |
| `LOGO_PROMPT_CHATGPT_v2.md` | Atölye-prompt'u + seçim-kriterleri + seçim-tablosu (süreç-kanıtı; kaynak-sayfa `logo.png` seçim-sonrası arşivden çıkarıldı — sdist-bloat/public-temizliği) |
| Arşiv | `pugio-mark.svg`, `pugio-avatar.png`, `sester_*_1789296*.jpg` — kullanılmaz |

## 6) Donuk-alan notu

Marka-yenilemesi kablo-şemasını DEĞİŞTİRMEZ: `pugio0` şeması, `pugio_bundle_version`,
`pugio_evidence_bundle`, `source: sikke` alıcı-uyumu için v2'ye kadar korunur
(`ESKI_KIMLIK.md`). Kanıt-dosyaları eski markayla imzalanmış görünse de doğrulaması
geçerli kalır — görsel-kimlik ile kablo-kimliği ayrı katmanlardır.
