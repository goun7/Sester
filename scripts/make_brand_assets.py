#!/usr/bin/env python3
"""SESTER marka-varlık-üreticisi — SVG kaynaklarının PNG raster-ikizleri.

Standart-bağımlılık: Pillow. Kullanım:
    .venv/bin/python scripts/make_brand_assets.py

Çıktılar:
    .github/assets/og.png      1280×640  (GitHub sosyal-önizleme)
    .github/assets/avatar.png  512×512   (org avatar / favicon kaynağı)

İlke: brand/sester-mark.svg + .github/assets/*.svg el-çizimi kaynaktır; bu
script aynı kompozisyonu vektör-matematiğiyle (küp-bezier örneklemesi +
Pillow çizimi) yeniden üretir — fail-loud: Pillow/font yoksa RED, sessiz
fallback YOK. El-kusuru (2px sürüklenme) bezier-kontrol-noktalarında korunur.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:  # fail-loud
    sys.exit(f"RED: Pillow gerekli — `pip install pillow` ({e})")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".github" / "assets"

PARCHMENT = (245, 240, 228)   # #F5F0E4
INK = (23, 23, 23)            # #171717
OLD_GOLD = (184, 134, 11)     # #B8860B
BRIGHT_GOLD = (201, 162, 39)  # #C9A227

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSerif-Bold.ttf",
    "/Library/Fonts/Georgia Bold.ttf",
    "C:/Windows/Fonts/georgiab.ttf",
]


def _font(size: int):
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    sys.exit("RED: serif font bulunamadı — DejaVu/Liberation/Georgia gerekli")


def _bez(p0, p1, p2, p3, t):
    """Küp-bezier noktası."""
    mt = 1 - t
    x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
    y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
    return (x, y)


# brand/sester-mark.svg'deki S-monogramı: 3 küp-segment, 200-viewBox koordinatı
S_SEGMENTS = [
    ((129, 73), (119, 61), (81, 61), (77, 82)),
    ((77, 82), (73, 101), (127, 99), (123, 118)),
    ((123, 118), (119, 139), (81, 139), (70, 126)),
]


def draw_coin(d: ImageDraw.ImageDraw, ox: float, oy: float, s: float, width_scale: float = 1.0):
    """Sester-sikkesi: dış halka + iç halka + S-monogramı + parlak-altın nokta."""
    def P(x, y):
        return (ox + x * s, oy + y * s)

    # dış halka (cx=101, cy=99, r=80, w=14)
    d.ellipse([P(101 - 80, 99 - 80), P(101 + 80, 99 + 80)],
              outline=INK, width=round(14 * s * width_scale))
    # iç halka (cx=100, cy=100, r=58, w=7)
    d.ellipse([P(100 - 58, 100 - 58), P(100 + 58, 100 + 58)],
              outline=OLD_GOLD, width=round(7 * s * width_scale))
    # S-monogramı — bezier'i yoğun örnekleyip kalın-yuvarlak çizgi olarak bas
    pts: list[tuple[float, float]] = []
    for seg in S_SEGMENTS:
        for i in range(41):
            pts.append(P(*_bez(*seg, i / 40)))
    d.line(pts, fill=INK, width=round(15 * s * width_scale), joint="curve")
    # uçlar: yuvarlak kapak
    r = 15 * s * width_scale / 2
    for tip in (pts[0], pts[-1]):
        d.ellipse([tip[0] - r, tip[1] - r, tip[0] + r, tip[1] + r], fill=INK)
    # parlak-altın mühür-noktası (cx=100, cy=100, r=6)
    d.ellipse([P(100 - 6, 100 - 6), P(100 + 6, 100 + 6)], fill=BRIGHT_GOLD)


def spaced_text(d: ImageDraw.ImageDraw, xy, text, font, fill, tracking: int):
    """Harf-aralıklı (tracking) metin — Pillow'un letter-spacing desteği yok."""
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + tracking
    return x


def make_og() -> None:
    img = Image.new("RGB", (1280, 640), PARCHMENT)
    d = ImageDraw.Draw(img)
    # el-ledger çerçevesi (2px sürüklenme bilinçli: ikinci çerçeve 6px ofsetli)
    d.rectangle([34, 30, 34 + 1213, 30 + 581], outline=INK, width=3)
    d.rectangle([40, 36, 40 + 1213, 36 + 581], outline=OLD_GOLD, width=1)
    # mark: SVG'de translate(150,130) scale(1.9)
    draw_coin(d, 150, 130, 1.9)
    # wordmark + alt-başlık
    f_title = _font(96)
    f_sub = _font(28)
    f_feat = _font(22)
    f_foot = _font(17)
    spaced_text(d, (566, 228), "SESTER", f_title, INK, 14)
    spaced_text(d, (566, 342), "metering · policy · evidence — fail-closed by default",
                f_sub, OLD_GOLD, 2)
    feats = [
        "✦ x402-style 402→payment→receipt handshake",
        "✦ AP2 mandates · ACP checkout · UCP monetization",
        "✦ hash-chain receipts + Merkle evidence bundles",
    ]
    y = 428
    for line in feats:
        spaced_text(d, (566, y), line, f_feat, INK, 1)
        y += 44
    tail = "v0.5.0 · APACHE-2.0"
    w = sum(f_foot.getlength(c) + 4 for c in tail) - 4
    spaced_text(d, (1240 - w, 588), tail, f_foot, OLD_GOLD, 4)
    img.save(OUT / "og.png")
    print(f"OK: {OUT / 'og.png'} (1280×640)")


def make_avatar() -> None:
    img = Image.new("RGB", (512, 512), PARCHMENT)
    d = ImageDraw.Draw(img)
    # SVG: 200-viewBox'un 2.56 ölçeği; avatar-okunurluğu için kalınlıklar arttı
    draw_coin(d, 0, 0, 2.56, width_scale=1.0)
    img.save(OUT / "avatar.png")
    print(f"OK: {OUT / 'avatar.png'} (512×512)")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    make_og()
    make_avatar()
    for name, wh in (("og.png", (1280, 640)), ("avatar.png", (512, 512))):
        p = OUT / name
        if not p.exists() or Image.open(p).size != wh:  # fail-loud selfcheck
            sys.exit(f"RED: {p} beklenen {wh} boyutunda değil")
    print("SESTER marka-varlıkları tamam (fail-loud selfcheck geçti).")
