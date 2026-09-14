#!/usr/bin/env python3
"""SESTER marka-varlık-üreticisi v2 — Chain-S markası (aday-E, 2026-09-14).

Tek-kaynak: brand/sester-mark-v2.svg (potrace, tek-path, IoU 0.9924).
Bu script aynı SVG'yi rsvg-convert ile rasterize eder ve OG/avatar/favicon
ailesini üretir — fail-loud: rsvg-convert/Pillow/font yoksa RED, sessiz
fallback YOK.

Çıktılar (.github/assets/):
    og.png                 1280×640  GitHub sosyal-önizleme
    avatar.png             512×512   org avatar
    favicon-{16,32,48,64,128,180,512}.png + favicon.ico
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:  # fail-loud
    sys.exit(f"RED: Pillow gerekli — `pip install pillow` ({e})")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".github" / "assets"
MARK_SVG = ROOT / "brand" / "sester-mark-v2.svg"

PARCHMENT = (245, 240, 228)   # #F5F0E4
INK = (23, 23, 23)            # #171717
OLD_GOLD = (184, 134, 11)     # #B8860B

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


def render_mark(height: int) -> Image.Image:
    """sester-mark-v2.svg'yi parşömen-zeminde rasterize et (fail-loud)."""
    if not MARK_SVG.is_file():
        sys.exit(f"RED: tek-kaynak marka yok: {MARK_SVG}")
    rsvg = shutil.which("rsvg-convert")
    if not rsvg:
        sys.exit("RED: rsvg-convert yok (librsvg) — sessiz-fallback YOK; "
                 "`apt install librsvg2-bin` ile kurun")
    tmp = OUT / "_mark_tmp.png"
    r = subprocess.run([rsvg, "-b", "#F5F0E4", "-h", str(height),
                        "-o", str(tmp), str(MARK_SVG)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"RED: marka-rasterizasyonu başarısız: {r.stderr}")
    img = Image.open(tmp).convert("RGB")
    tmp.unlink()
    return img


def spaced_text(d: ImageDraw.ImageDraw, xy, text, font, fill, tracking: int):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + tracking
    return x


def _spaced_width(text, font, tracking: int) -> float:
    return sum(font.getlength(c) + tracking for c in text) - tracking


def _fit_font(text, tracking: int, max_w: float, start: int):
    """Metin max_w'ye sığana kadar punto düşür (taşma-yok sözleşmesi)."""
    size = start
    while size > 12:
        f = _font(size)
        if _spaced_width(text, f, tracking) <= max_w:
            return f
        size -= 1
    return _font(12)


def make_og() -> None:
    img = Image.new("RGB", (1280, 640), PARCHMENT)
    d = ImageDraw.Draw(img)
    # el-ledger çerçevesi (2px sürüklenme bilinçli: ikinci çerçeve ofsetli)
    d.rectangle([34, 30, 34 + 1213, 30 + 581], outline=INK, width=3)
    d.rectangle([40, 36, 40 + 1213, 36 + 581], outline=OLD_GOLD, width=1)
    # Chain-S markası: yükseklik 400 (oran 668:1056 → genişlik ~253)
    mark = render_mark(400)
    img.paste(mark, (150, 120))
    # sağ kolon: wordmark + alt-başlık + mikro-özellikler
    f_title = _font(104)
    f_foot = _font(17)
    spaced_text(d, (490, 210), "SESTER", f_title, INK, 14)
    # alt-başlık: çerçeveye otomatik-sığdırma (taşma-yok)
    sub = "metering · policy · evidence — fail-closed by default"
    f_sub = _fit_font(sub, 2, 1230 - 494, 28)
    spaced_text(d, (494, 344), sub, f_sub, OLD_GOLD, 2)
    # mikro-özellikler: elmas-bülten çizilir (font-glif riski yok), metin girintili
    f_feat = _fit_font("AP2 mandates · ACP checkout · UCP monetization", 1, 1230 - 522, 22)
    feats = [
        "x402-style 402→payment→receipt handshake",
        "AP2 mandates · ACP checkout · UCP monetization",
        "hash-chain receipts + Merkle evidence bundles",
    ]
    y = 424
    for line in feats:
        # 7px yarıçaplı elmas (brand-altın sabit; glif-yerine çizim)
        cx, cy = 502, y + int(f_feat.size * 0.62)
        d.polygon([(cx, cy - 7), (cx + 7, cy), (cx, cy + 7), (cx - 7, cy)], fill=OLD_GOLD)
        spaced_text(d, (522, y), line, f_feat, INK, 1)
        y += 44
    tail = "v0.5.0 · APACHE-2.0"
    w = sum(f_foot.getlength(c) + 4 for c in tail) - 4
    spaced_text(d, (1240 - w, 588), tail, f_foot, OLD_GOLD, 4)
    img.save(OUT / "og.png")
    print(f"OK: {OUT / 'og.png'} (1280×640)")


def make_avatar() -> None:
    """512 avatar: Chain-S parşömen üzerinde, %10 pad."""
    img = Image.new("RGB", (512, 512), PARCHMENT)
    mark = render_mark(410)
    img.paste(mark, ((512 - mark.width) // 2, (512 - 410) // 2))
    img.save(OUT / "avatar.png")
    print(f"OK: {OUT / 'avatar.png'} (512×512)")


def make_favicons() -> None:
    """Favicon-ailesi: aynı avatardan LANCZOS inişi + çok-boyutlu .ico."""
    av = Image.open(OUT / "avatar.png").convert("RGB")
    sizes = [16, 32, 48, 64, 128, 180, 512]
    for s in sizes:
        av.resize((s, s), Image.LANCZOS).save(OUT / f"favicon-{s}.png")
    av.save(OUT / "favicon.ico", sizes=[(s, s) for s in (16, 32, 48, 64)])
    print(f"OK: favicon-ailesi ({', '.join(map(str, sizes))} + .ico)")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    make_og()
    make_avatar()
    make_favicons()
    for name, wh in (("og.png", (1280, 640)), ("avatar.png", (512, 512))):
        p = OUT / name
        if not p.exists() or Image.open(p).size != wh:  # fail-loud selfcheck
            sys.exit(f"RED: {p} beklenen {wh} boyutunda değil")
    for s in (16, 32, 48, 64, 128, 180, 512):
        p = OUT / f"favicon-{s}.png"
        if not p.exists() or Image.open(p).size != (s, s):
            sys.exit(f"RED: {p} beklenen {(s, s)} boyutunda değil")
    print("SESTER marka-varlıkları tamam (v2 Chain-S; fail-loud selfcheck geçti).")
