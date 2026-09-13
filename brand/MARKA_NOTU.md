# PUGIO — Marka Notu (2026-09-12, kimlik onaylı)

> 63 · AjanTicaretYigini'nin ürün-adı **PUGIO** olarak onaylandı; ana marka
> **Pugio-Tally** (konsept A). Atölye: `../pugio-logo-atolyesi.html` · Ana SVG:
> `pugio-mark.svg` (saydam zemin).

## 1) İsim-gerekçe

- **Pugio** = Roma lejyonerinin yedek pikası: birincil silah (gladius) çöktüğünde
  dahi görevi tamamlayan ikincil. 63'ün teziyle birebir: protokol çökerse bile
  **fail-closed politika + kanıt-zinciri görevi tamamlar**.
- Kısa (5 harf), Latin kökenli, teknoloji-sesi; "kural/sayaç/kanıt" üçlüsüne
  hikâye katıyor.

## 2) Niş-taraması (2026-09-12, web — ARASTIRMA disipliniyle)

| Bulgusu | Durum |
|---|---|
| Ajan-ödeme/AI/dev-tools alanında "Pugio" ürünü | **Yok — niş boş** |
| ASUS ROG Pugio (gaming fare hattı) | Var — SEO kirliliği (ilk-sayfa baskısı orta); sınıf-9 marka kesişimi |
| crates.io "Pugio" (Rust yardımcı-araç, küçük) | Var — düşük risk, farklı ekosistem |
| "Pugra"/"Tomar" adayları | Boştu; Pugio hikâye-gücüyle seçildi |

⚖️ **Açık kalem (kurumsallaşma-öncesi şart):** marka-review — ASUS sınıf-9
tescilli hattıyla çakışma analizi + TR/AB tescil-ihtimali. İlk kurumsal-pilot
görüşmesinden önce tamamlanır (IS_PLANI §11'e bağlı).

## 3) Palet

| Rol | Hex |
|---|---|
| Mürekkep (birincil) | `#171717` |
| Eski Altın (vurgu) | `#B8860B` |
| Parşömen (zemin) | `#F5F0E4` |
| Parlak Altın (alternatif vurgu, koyu zemin) | `#C9A227` |

## 4) Kullanım kuralları

- **Min. boyut:** 16px — tally deseni okunur (favicon-testi geçildi).
- **Clearspace:** her yönde bir tally-genişliği (≈ çizgi-kalınlığı × 3).
- **Koyu zemin:** Mühür varyantı (konsept C) — altın halka + parşömen tally.
- **Wordmark:** "PUGIO" harf-aralıklı (tracking 2px) + Monogram P· ortağı (konsept F).
- **El-kusuru ilkesi:** çizgilerdeki 2–4px sürüklenme bilinçlidir — düzeltilmez;
  marka "el-yazısı ledger kaydı" estetiğini taşır. Yeniden çizimde kusur korunur.
- **AI-jenerik yasağı:** gradient-küre, maskot, yarıçapsal parlama kullanılmaz.

## 5) Varlık-listesi

| Dosya | İçerik |
|---|---|
| `pugio-mark.svg` | Ana marka — Pugio-Tally, saydam zemin |
| `../pugio-logo-atolyesi.html` | 6 konsept atölyesi (A onaylı; B–F yedek/varyant havuzu) |

Panel/ürün içi kullanım: `pugio/panel.py` gömülü SVG olarak aynı markayı kullanır.
