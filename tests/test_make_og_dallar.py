"""make_brand_assets.make_og dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Dış çağrı YOK: tmp_path cikti + sentetik font.
"""
import sys

import pytest

import scripts.make_brand_assets as mba


@pytest.fixture
def outdir(tmp_path, monkeypatch):
    target = tmp_path / "og"
    target.mkdir()
    monkeypatch.setattr(mba, "OUT", target)
    return target


# -- temel ---------------------------------------------------------------------------------

def test_make_og_returns_none(outdir):
    assert mba.make_og() is None


def test_make_og_no_exception(outdir):
    mba.make_og()


def test_output_png_created(outdir):
    mba.make_og()
    files = list(outdir.glob("*.png"))
    assert len(files) >= 1


def test_output_named_og(outdir):
    mba.make_og()
    files = [f.name for f in outdir.glob("*.png")]
    assert any("og" in n.lower() for n in files)


# -- yardimcilar ---------------------------------------------------------------------------------

def test_font_returns_object(outdir):
    f = mba._font(40)
    assert f is not None


def test_fit_font_returns_object(outdir):
    f = mba._fit_font("test metni", 400, 40, 30)
    assert f is not None


def test_fit_font_shrinks_for_long(outdir):
    """Uzun metin -> daha kucuk font."""
    big = mba._fit_font("cok uzun bir test metni", 100, 60, 50)
    small = mba._fit_font("kisa", 1000, 60, 50)
    assert big.size <= small.size


def test_render_mark_returns_image(outdir):
    img = mba.render_mark(200)
    assert img is not None


def test_render_mark_height(outdir):
    img = mba.render_mark(120)
    assert img.height == 120


# -- cikti formati ---------------------------------------------------------------------------------

def test_og_image_width(outdir):
    mba.make_og()
    from PIL import Image
    files = list(outdir.glob("*og*.png"))
    if not files:
        files = list(outdir.glob("*.png"))
    with Image.open(files[0]) as im:
        assert im.width > 0


def test_og_image_rgb(outdir):
    mba.make_og()
    from PIL import Image
    files = list(outdir.glob("*.png"))
    with Image.open(files[0]) as im:
        assert im.mode in ("RGB", "RGBA")


# -- tekrar ---------------------------------------------------------------------------------

def test_repeatable(outdir):
    mba.make_og()
    first = [f.stat().st_size for f in sorted(outdir.glob("*.png"))]
    mba.make_og()
    second = [f.stat().st_size for f in sorted(outdir.glob("*.png"))]
    assert len(first) == len(second)


def test_multiple_runs_no_crash(outdir):
    for _ in range(3):
        mba.make_og()
    assert len(list(outdir.glob("*.png"))) >= 1
