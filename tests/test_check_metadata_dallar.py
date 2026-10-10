"""63-Sester preupload_check.check_metadata dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: tmp wheel zip (gercek dist YOK).
"""
import io
import sys
import zipfile

import pytest

sys.path.insert(0, "scripts")

from preupload_check import check_metadata  # noqa: E402


class _Spy:
    oks = []
    reds = []


@pytest.fixture
def fake(monkeypatch):
    _Spy.oks = []
    _Spy.reds = []
    import preupload_check as P
    monkeypatch.setattr(P, "_version", "1.2.3", raising=False)
    monkeypatch.setattr(P, "ok", lambda m: _Spy.oks.append(m))
    monkeypatch.setattr(P, "red", lambda m: _Spy.reds.append(m))
    return P


def _wheel(tmp_path, meta_text, name="sester-1.2.3-py3-none-any.whl"):
    p = tmp_path / name
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("sester-1.2.3.dist-info/METADATA", meta_text)
    return p


_META_OK = """Name: sester
Version: 1.2.3
Summary: Sester protocol
License-Expression: Apache-2.0
Requires-Python: >=3.11
License-File: LICENSE
"""


def _run(fake, tmp_path, meta=_META_OK):
    check_metadata(_wheel(tmp_path, meta))
    return _Spy.oks, _Spy.reds


# -- tumu-yerinde ---------------------------------------------------------------------------------

def test_no_red_when_complete(fake, tmp_path):
    _, reds = _run(fake, tmp_path)
    assert reds == []


def test_six_ok_messages(fake, tmp_path):
    oks, _ = _run(fake, tmp_path)
    assert len(oks) == 6


def test_ok_has_metadata_prefix(fake, tmp_path):
    oks, _ = _run(fake, tmp_path)
    assert all("METADATA" in o for o in oks)


def test_name_ok(fake, tmp_path):
    oks, _ = _run(fake, tmp_path)
    assert any("Name:" in o for o in oks)


def test_version_ok(fake, tmp_path):
    oks, _ = _run(fake, tmp_path)
    assert any("Version:" in o for o in oks)


def test_license_expression_ok(fake, tmp_path):
    oks, _ = _run(fake, tmp_path)
    assert any("License-Expression:" in o for o in oks)


def test_requires_python_ok(fake, tmp_path):
    oks, _ = _run(fake, tmp_path)
    assert any("Requires-Python:" in o for o in oks)


def test_summary_ok(fake, tmp_path):
    oks, _ = _run(fake, tmp_path)
    assert any("Summary:" in o for o in oks)


def test_license_file_ok(fake, tmp_path):
    oks, _ = _run(fake, tmp_path)
    assert any("lisans-dosyası" in o for o in oks)


# -- eksik ---------------------------------------------------------------------------------

def test_missing_name_red(fake, tmp_path):
    meta = _META_OK.replace("Name: sester\n", "")
    _, reds = _run(fake, tmp_path, meta)
    assert any("Name:" in r for r in reds)


def test_missing_version_red(fake, tmp_path):
    meta = _META_OK.replace("Version: 1.2.3\n", "")
    _, reds = _run(fake, tmp_path, meta)
    assert any("Version:" in r for r in reds)


def test_wrong_version_red(fake, tmp_path):
    meta = _META_OK.replace("Version: 1.2.3\n", "Version: 0.1.0\n")
    _, reds = _run(fake, tmp_path, meta)
    assert any("Version:" in r for r in reds)


def test_version_regex_anchored(fake, tmp_path):
    """^Version: 1.2.3$ — '1.2.3.dev' RED."""
    meta = _META_OK.replace("Version: 1.2.3\n", "Version: 1.2.3.dev\n")
    _, reds = _run(fake, tmp_path, meta)
    assert any("Version:" in r for r in reds)


def test_name_regex_anchored(fake, tmp_path):
    """^Name: sester$ — 'sesterx' RED."""
    meta = _META_OK.replace("Name: sester\n", "Name: sesterx\n")
    _, reds = _run(fake, tmp_path, meta)
    assert any("Name:" in r for r in reds)


def test_missing_license_expression_red(fake, tmp_path):
    meta = _META_OK.replace("License-Expression: Apache-2.0\n", "")
    _, reds = _run(fake, tmp_path, meta)
    assert any("License-Expression:" in r for r in reds)


def test_missing_requires_python_red(fake, tmp_path):
    meta = _META_OK.replace("Requires-Python: >=3.11\n", "")
    _, reds = _run(fake, tmp_path, meta)
    assert any("Requires-Python:" in r for r in reds)


def test_missing_summary_red(fake, tmp_path):
    meta = _META_OK.replace("Summary: Sester protocol\n", "")
    _, reds = _run(fake, tmp_path, meta)
    assert any("Summary:" in r for r in reds)


def test_empty_summary_red(fake, tmp_path):
    """^Summary: .+ — bos ozet RED."""
    meta = _META_OK.replace("Summary: Sester protocol\n", "Summary: \n")
    _, reds = _run(fake, tmp_path, meta)
    assert any("Summary:" in r for r in reds)


def test_all_missing_six_reds(fake, tmp_path):
    meta = "Metadata-Version: 2.1\n"
    _, reds = _run(fake, tmp_path, meta)
    assert len(reds) == 6


def test_red_message_has_pattern(fake, tmp_path):
    meta = _META_OK.replace("Name: sester\n", "")
    _, reds = _run(fake, tmp_path, meta)
    assert any("eksik/uyuşmuyor" in r for r in reds)


def test_red_message_includes_expected_regex(fake, tmp_path):
    meta = _META_OK.replace("Name: sester\n", "")
    _, reds = _run(fake, tmp_path, meta)
    assert any("sester" in r for r in reds)


# -- lisans ---------------------------------------------------------------------------------

def test_license_file_alternative_ok(fake, tmp_path):
    """License-File yok ama Classifier: License varsa OK."""
    meta = (_META_OK.replace("License-File: LICENSE\n", "")
            + "Classifier: License :: OSI Approved\n")
    oks, reds = _run(fake, tmp_path, meta)
    assert any("lisans-dosyası" in o for o in oks)
    assert not any("License-File" in r for r in reds)


def test_no_license_file_red(fake, tmp_path):
    meta = _META_OK.replace("License-File: LICENSE\n", "")
    _, reds = _run(fake, tmp_path, meta)
    assert any("License-File eksik" in r for r in reds)


def test_license_file_case_sensitive(fake, tmp_path):
    """'license-file' kucuk harf RED."""
    meta = _META_OK.replace("License-File: LICENSE\n", "license-file: LICENSE\n")
    _, reds = _run(fake, tmp_path, meta)
    assert any("License-File eksik" in r for r in reds)


# -- version-kaynagi ---------------------------------------------------------------------------------

def test_version_from_global(fake, tmp_path, monkeypatch):
    monkeypatch.setattr(fake, "_version", "9.9.9", raising=False)
    meta = _META_OK.replace("Version: 1.2.3\n", "Version: 9.9.9\n")
    _, reds = _run(fake, tmp_path, meta)
    assert not any("Version:" in r for r in reds)


def test_version_mismatch_after_change(fake, tmp_path, monkeypatch):
    monkeypatch.setattr(fake, "_version", "9.9.9", raising=False)
    _, reds = _run(fake, tmp_path)
    assert any("Version:" in r for r in reds)


def test_version_escaped_regex(fake, tmp_path, monkeypatch):
    """Ozel-karakterli surum regex-escape ile eslesir."""
    monkeypatch.setattr(fake, "_version", "1.2.3+local", raising=False)
    meta = _META_OK.replace("Version: 1.2.3\n",
                            "Version: 1.2.3+local\n")
    _, reds = _run(fake, tmp_path, meta)
    assert not any("Version:" in r for r in reds)


# -- meta bulma ---------------------------------------------------------------------------------

def test_meta_from_inner_path(fake, tmp_path):
    """METADATA herhangi bir .dist-info altinda olabilir."""
    p = tmp_path / "w.whl"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("any/thing.dist-info/METADATA", _META_OK)
    check_metadata(p)
    assert _Spy.reds == []


def test_meta_decode_replace(fake, tmp_path):
    """Bozuk UTF-8 'replace' ile okunur — crash YOK."""
    with zipfile.ZipFile(tmp_path / "w.whl", "w") as zf:
        raw = _META_OK.encode("utf-8") + b"\xff\xfeX"
        zf.writestr("a.dist-info/METADATA", raw)
    check_metadata(tmp_path / "w.whl")
    assert _Spy.reds == []


def test_meta_multiline_ok(fake, tmp_path):
    meta = _META_OK + "Description: cok satirli\n aciklama\n"
    _, reds = _run(fake, tmp_path, meta)
    assert reds == []


# -- esik ---------------------------------------------------------------------------------

def test_minimal_meta(fake, tmp_path):
    meta = _META_OK.replace("Summary: Sester protocol\n",
                            "Summary: x\n")
    _, reds = _run(fake, tmp_path, meta)
    assert reds == []


def test_unicode_summary(fake, tmp_path):
    meta = _META_OK.replace("Summary: Sester protocol\n",
                            "Summary: Türkçe protokol\n")
    _, reds = _run(fake, tmp_path, meta)
    assert reds == []


def test_many_extra_lines_ok(fake, tmp_path):
    meta = _META_OK + "Requires-Dist: httpx\n" * 30
    _, reds = _run(fake, tmp_path, meta)
    assert reds == []


def test_wheel_arg_path_like(fake, tmp_path):
    """Path yerine str de kabul edilir."""
    check_metadata(str(_wheel(tmp_path, _META_OK)))
    assert _Spy.reds == []


# -- tekrar ---------------------------------------------------------------------------------

def test_repeatable_ok(fake, tmp_path):
    w = _wheel(tmp_path, _META_OK)
    check_metadata(w)
    n = len(_Spy.oks)
    check_metadata(w)
    assert len(_Spy.oks) == 2 * n


def test_repeatable_red(fake, tmp_path):
    w = _wheel(tmp_path, "Metadata-Version: 2.1\n")
    check_metadata(w)
    check_metadata(w)
    assert len(_Spy.reds) == 12


def test_independent_calls(fake, tmp_path):
    check_metadata(_wheel(tmp_path, _META_OK))
    assert _Spy.reds == []
    check_metadata(_wheel(tmp_path, "Metadata-Version: 2.1\n"))
    assert _Spy.reds != []
