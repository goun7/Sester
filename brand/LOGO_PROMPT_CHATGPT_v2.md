# SESTER Logo Atölyesi — ChatGPT Prompt'u (v2, 2026-09-14)

> Kullanım: aşağıdaki **İngilizce prompt'u** olduğu gibi ChatGPT'ye ver
> (görsel-üretimi açık model). Yöntem Tamga-Protocol süreciyle aynıdır:
> **tek seferde 5 farklı konsept, tek sayfada** → kurucu + ajan birlikte
> seçer → seçilen hücre yüksek-çözünürlükte ayrıca üretilir → potrace-ile
> `brand/sester_mark_v2.svg`'e izlenir → favicon-ailesi + og.png/avatar
> `scripts/make_brand_assets.py` ile yeniden türetilir.
>
> Bu prompt, mevcut marka-notundaki sert kuralları (MARKA_NOTU.md §3)
> modele empoze eder: gradient-küre/maskot/ışıksal-parlama YASAK;
> el-kusuru estetiği korunur; 16px'te okunurluk şart.

---

## ChatGPT'ye verilecek prompt (kopyala-yapıştır)

```text
You are designing a logo system for SESTER, a developer-infrastructure product
in the AI-agent payments space. Deliver ONE image containing FIVE distinct
logo concepts, arranged as a labeled concept sheet (grid of 5 cells: top row
3 cells, bottom row 2 cells). This is a selection sheet — variety matters more
than polish of any single option.

BRACKground STORY (for meaning, not for depicting):
SESTER comes from "Sestertius" — the ancient Roman coin that became the empire's
standard unit of trade: "the measure of value everyone accepts." The product is
the metering + policy + verifiable-receipt layer for AI-agent commerce: machine
payments, quotas, hash-chain receipts, fail-closed rules. The mark should feel
like a coin, a seal, or a ledger stamp — an instrument of trusted accounting —
NOT like a generic tech startup logo.

HARD STYLE RULES (violating any of these disqualifies the concept):
- Flat vector style only. No gradients, no 3D, no bevels, no drop shadows,
  no photorealism, no glow, no radial light bursts.
- NO mascot, NO robot face, NO cute character, NO generic "AI orb / neural
  network doodle" clichés.
- Each concept must be essentially MONOCHROME (one ink color on the paper
  background) so it survives single-color printing and tiny favicon sizes.
- Crisp, clean edges suitable for automatic bitmap→vector tracing.
- Must remain legible at 16×16 px (favicon). Test yourself: would the shape
  still read if shrunk to a fingernail?
- Slight hand-drawn irregularity in stroke weight is WELCOME (like an ink
  ledger entry) — do not make it sterile-perfect geometric, but keep edges
  clean enough to trace.

PALETTE (exact hex):
- Ink (primary strokes/fills): #171717
- Paper (background): #F5F0E4
- Antique gold (tiny accent only, optional per concept): #B8860B
Background of every cell must be the paper color. No other colors.

THE FIVE CONCEPT DIRECTIONS (one per cell, labeled A–E in small text under
each cell):
A) SESTER COIN — an ancient Roman coin rendered as a minimal modern mark:
   a circular coin outline with a stylized "S" monogram inside, optionally
   with a tiny rim-dot or short rim-tick detail suggesting minting. The "S"
   may be drawn with subtle chisel-like stroke variation.
B) LEDGER SEAL — a square wax-seal / stamp shape containing an abstract
   "S" or a vertical tally-mark motif; think notary seal meets hash-chain
   block. Corners may be slightly rounded by hand.
C) BALANCE LEDGER — a minimal abstraction of a balance scale where the beam
   forms a subtle "S" curve, or two pans holding a coin; geometric, calm,
   symmetrical-ish but hand-drawn.
D) RECEIPT STRIP — a vertical receipt/ticket with a torn or serrated bottom
   edge, bearing a bold "S" and 2–3 thin horizontal ledger lines suggesting
   entries; the receipt silhouette doubles as a "1" (one middleware).
E) CHAIN-LINK S — a bold letter "S" constructed from 3–4 interlocking chain
   links or square hash-blocks, reading simultaneously as the letter S and
   as a chain (hash-chain receipts). This is the most abstract option.

FOR EACH CELL show the mark twice side by side: (1) the bare mark large,
(2) a small lockup of mark + the wordmark "SESTER" in a letter-spaced serif
(A continental serif like Trajan/Cormorant flavor — not a body-text serif),
all-caps, tracking wide. Wordmark color: ink #171717.

NO mockups, NO business cards, NO app icons in context, NO watermarks,
NO extra text besides cell labels A–E, the wordmark, and (optionally) a
one-word concept name under each label.

Output: one single high-resolution image, 5 cells, clean grid layout,
generous margins.
```

---

## Seçim-kriterleri (kurucu + ajan birlikte puanlar; Tamga-süreciyle aynı)

| # | Kriter | Ağırlık |
|---|---|---|
| 1 | **16px okunurluk** (favicon sadakati) | x3 |
| 2 | Tek-renk hayatta-kalma (gold'suz da çalışır) | x2 |
| 3 | Anlam-yoğunluğu (sikke/mühür/ledger dili — jenerik-tech değil) | x2 |
| 4 | potrace-uyumu (temiz kenar, trace-sonrası sadakat) | x2 |
| 5 | Koyu-zemin uyarlanabilirliği (mürekkep→parşömen çevrimi) | x1 |
| 6 | Wordmark-lockup uyumu (serif + tracking) | x1 |

## Seçim-sonrası entegrasyon (sabit iş-akışı — otomatikleştirilebilir)

1. Seçilen hücre yüksek-çözünürlükte tek-başına yeniden üretilir ("cell B,
   bare mark only, full resolution, same style").
2. Potrace → `brand/sester_mark_v2.svg` (tek-path, `currentColor`, 1:1 sadakat —
   Tamga-standartı: potrace-verified).
3. `scripts/make_brand_assets.py` og/avatar kaynağını v2-marka çevirir →
   `og.png` 1280×640 + `avatar.png` 512×512 + favicon-ailesi
   (16/32/48/64/128/180/512 + .ico).
4. `brand/MARKA_NOTU.md` güncellenir: v2-marka + kullanım-kuralları;
   v1-marka arşive ("kullanılmaz") düşer.
5. Kapı-adımı 4 (marka-varlık PNG'leri) fail-loud selfcheck ile teyit eder.

> Not: mevcut v1-marka (`brand/sester-mark.svg`) halka+S-monogram hattıdır;
> beğenilmemesi üzerine bu v2-atölyesi açıldı. Kablo-alanları ve panel-içi
> gömülü marka (`sester/panel.py MARK_SVG`) seçim-sonrası tek-PR'da
> senkronlanır — görsel-kimlik ile kablo-kimliği ayrı katmanlar kalır.
