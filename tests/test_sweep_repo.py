"""public_surface_sweep.sweep_repo marka-yüzey tarama testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Dış çağrı YOK: geçici sahte-repo + monkeypatch ROOT.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")

import public_surface_sweep as pss  # noqa: E402


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """Sahte repo kökü + birkaç dosya."""
    monkeypatch.setattr(pss, "ROOT", tmp_path)
    return tmp_path


def _pats(*pats):
    return [re.compile(p) for p in pats]


# -- temiz repo ---------------------------------------------------------------------------

def test_clean_repo_returns_zero(fake_repo, capsys):
    (fake_repo / "clean.py").write_text("print('hello')\n", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"yasaklı"), []) == 0


def test_ok_message_printed(fake_repo, capsys):
    (fake_repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    pss.sweep_repo(_pats(r"yasaklı"), [])
    assert "OK" in capsys.readouterr().out


def test_scanned_count_printed(fake_repo, capsys):
    for i in range(3):
        (fake_repo / f"f{i}.py").write_text("x\n", encoding="utf-8")
    pss.sweep_repo(_pats(r"yasaklı"), [])
    assert "3 dosya" in capsys.readouterr().out


# -- dosya-adı eşleşmesi ---------------------------------------------------------------------------

def test_filename_hit_returns_one(fake_repo):
    (fake_repo / "iç-ad-dosya.py").write_text("x\n", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"iç-ad"), []) == 1


def test_filename_hit_reported(fake_repo, capsys):
    (fake_repo / "iç-ad-dosya.py").write_text("x\n", encoding="utf-8")
    pss.sweep_repo(_pats(r"iç-ad"), [])
    assert "filename-hit" in capsys.readouterr().out


def test_filename_hit_stops_content_scan(fake_repo, capsys):
    """Dosya-adı eşleşince içerik taranmaz (tek hit)."""
    p = fake_repo / "iç-ad.py"
    p.write_text("yasaklı1\nyasaklı2\nyasaklı3\n", encoding="utf-8")
    pss.sweep_repo(_pats(r"iç-ad", r"yasaklı"), [])
    out = capsys.readouterr().out
    # sadece 1 hit (filename) — 3 satırlık içerik taranmadı
    assert out.count("yasaklı") == 0


# -- içerik eşleşmesi ---------------------------------------------------------------------------

def test_content_hit_returns_one(fake_repo):
    (fake_repo / "a.py").write_text("bu bir yasaklı kelimedir\n", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"yasaklı"), []) == 1


def test_content_hit_has_line_number(fake_repo, capsys):
    p = fake_repo / "a.py"
    p.write_text("satır1\nsatır2\nyasaklı kelime\nsatır4\n", encoding="utf-8")
    pss.sweep_repo(_pats(r"yasaklı"), [])
    assert "a.py:3" in capsys.readouterr().out


def test_content_hit_truncated_to_120(fake_repo, capsys):
    p = fake_repo / "a.py"
    p.write_text("yasaklı " + "x" * 200 + "\n", encoding="utf-8")
    pss.sweep_repo(_pats(r"yasaklı"), [])
    lines = [l for l in capsys.readouterr().out.splitlines() if "yasaklı" in l]
    assert len(lines[0]) <= 200  # hit satırı kırpılmış


def test_multiple_content_hits(fake_repo):
    p = fake_repo / "a.py"
    p.write_text("yasaklı1\nyasaklı2\nyasaklı3\n", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"yasaklı"), []) == 1  # 3 hit → rc=1


def test_hit_count_in_message(fake_repo, capsys):
    p = fake_repo / "a.py"
    p.write_text("yasaklı1\nyasaklı2\n", encoding="utf-8")
    pss.sweep_repo(_pats(r"yasaklı"), [])
    assert "2 iç-ad-hit" in capsys.readouterr().out


# -- çoklu örüntü ---------------------------------------------------------------------------

def test_multiple_patterns(fake_repo):
    (fake_repo / "a.py").write_text("gizli1\n", encoding="utf-8")
    (fake_repo / "b.py").write_text("özel2\n", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"gizli1", r"özel2"), []) == 1


def test_pattern_in_hit_message(fake_repo, capsys):
    (fake_repo / "a.py").write_text("gizli kelime\n", encoding="utf-8")
    pss.sweep_repo(_pats(r"gizli"), [])
    assert "/gizli/" in capsys.readouterr().out


def test_no_pattern_match_returns_zero(fake_repo):
    (fake_repo / "a.py").write_text("normal kod\n", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"yasaklı"), []) == 0


def test_empty_patterns_returns_zero(fake_repo):
    (fake_repo / "a.py").write_text("herhangi\n", encoding="utf-8")
    assert pss.sweep_repo([], []) == 0


# -- istisnalar ---------------------------------------------------------------------------

def test_default_excludes_skipped(fake_repo, capsys):
    for d in (".git", ".venv", "dist", "__pycache__", ".pytest_cache"):
        (fake_repo / d).mkdir()
        (fake_repo / d / "yasaklı.py").write_text("x\n", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"yasaklı"), []) == 0
    assert "0 dosya" in capsys.readouterr().out


def test_brand_marka_excluded(fake_repo):
    (fake_repo / "brand").mkdir()
    (fake_repo / "brand" / "SESTER_marka.md").write_text("yasaklı yasaklı\n", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"yasaklı"), []) == 0


def test_extra_excludes_added(fake_repo):
    (fake_repo / "secret").mkdir()
    (fake_repo / "secret" / "a.py").write_text("yasaklı\n", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"yasaklı"), ["secret/"]) == 0


def test_extra_exclude_count_in_message(fake_repo, capsys):
    (fake_repo / "a.py").write_text("x\n", encoding="utf-8")
    pss.sweep_repo(_pats(r"yasaklı"), ["extra1/", "extra2/"], )
    assert "istisnalar: 8" in capsys.readouterr().out  # 6 varsayılan + 2


def test_excludes_are_substring_match(fake_repo):
    """exclude alt-dizi eşleşmesi — yolun herhangi bir yerinde geçer."""
    (fake_repo / "a").mkdir()
    (fake_repo / "a" / "yerel_ozel").mkdir()
    (fake_repo / "a" / "yerel_ozel" / "x.py").write_text("yasaklı\n", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"yasaklı"), ["yerel_ozel"]) == 0


# -- dosya türleri ---------------------------------------------------------------------------

def test_binary_file_skipped(fake_repo):
    p = fake_repo / "a.bin"
    p.write_bytes(b"\xff\xfe\x00\x00\x80\x00")
    # UnicodeDecodeError → atla, crash yok
    assert pss.sweep_repo(_pats(r"yasaklı"), []) == 0


def test_empty_file_ok(fake_repo):
    (fake_repo / "empty.py").write_text("", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"yasaklı"), []) == 0


def test_nested_directories_scanned(fake_repo):
    (fake_repo / "a" / "b" / "c").mkdir(parents=True)
    (fake_repo / "a" / "b" / "c" / "deep.py").write_text("yasaklı\n", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"yasaklı"), []) == 1


def test_unicode_content_ok(fake_repo):
    (fake_repo / "u.py").write_text("# Türkçe açıklama: yasaklı\n", encoding="utf-8")
    assert pss.sweep_repo(_pats(r"yasaklı"), []) == 1


# -- hit sınırı ---------------------------------------------------------------------------

def test_hits_truncated_at_40(fake_repo, capsys):
    p = fake_repo / "a.py"
    p.write_text("".join(f"yasaklı{i}\n" for i in range(50)), encoding="utf-8")
    pss.sweep_repo(_pats(r"yasaklı"), [])
    out = capsys.readouterr().out
    assert "+10 satır" in out


def test_fewer_than_40_no_truncation(fake_repo, capsys):
    p = fake_repo / "a.py"
    p.write_text("".join(f"yasaklı{i}\n" for i in range(10)), encoding="utf-8")
    pss.sweep_repo(_pats(r"yasaklı"), [])
    assert "+0 satır" not in capsys.readouterr().out


# -- çoklu dosya ---------------------------------------------------------------------------

def test_multiple_files_multiple_hits(fake_repo, capsys):
    for i in range(3):
        (fake_repo / f"f{i}.py").write_text("yasaklı\n", encoding="utf-8")
    pss.sweep_repo(_pats(r"yasaklı"), [])
    out = capsys.readouterr().out
    assert out.count("f0.py") + out.count("f1.py") + out.count("f2.py") == 3


def test_empty_repo_returns_zero(fake_repo, capsys):
    assert pss.sweep_repo(_pats(r"yasaklı"), []) == 0
    assert "0 dosya" in capsys.readouterr().out


def test_only_directories_skipped(fake_repo):
    (fake_repo / "emptydir").mkdir()
    assert pss.sweep_repo(_pats(r"yasaklı"), []) == 0
