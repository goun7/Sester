"""public_surface_sweep.sweep_sdist dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Dış çağrı YOK: sentetik tar.gz + monkeypatch.
"""
import io
import tarfile

import pytest

import scripts.public_surface_sweep as sweep


def _tar(members):
    """Bellek-icinde sentetik sdist olustur."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members:
            b = data.encode("utf-8")
            ti = tarfile.TarInfo(name)
            ti.size = len(b)
            tf.addfile(ti, io.BytesIO(b))
    buf.seek(0)
    return buf


@pytest.fixture
def fake(monkeypatch):
    """_sdist_members + _read_bytes sentetik."""
    state = {"members": []}

    def _members():
        return ("test-1.0.tar.gz", [m for m, _ in state["members"]])

    def _read(sdist, member):
        for name, data in state["members"]:
            if name == member:
                return data.encode("utf-8")
        raise KeyError(member)

    monkeypatch.setattr(sweep, "_sdist_members", _members)
    monkeypatch.setattr(sweep, "_read_bytes", _read)
    return state


# -- temel ---------------------------------------------------------------------------------

def test_green_when_clean(fake, capsys):
    fake["members"] = [("pkg/ok.txt", "helloworld")]
    assert sweep.sweep_sdist([__import__("re").compile("SECRET")]) == 0


def test_returns_int(fake):
    fake["members"] = [("pkg/a.txt", "temiz")]
    assert isinstance(sweep.sweep_sdist([]), int)


def test_no_members_red(monkeypatch, capsys):
    """sdist yok -> RED."""
    monkeypatch.setattr(sweep, "_sdist_members", lambda: ("", []))
    assert sweep.sweep_sdist([]) == 1


def test_no_members_message(monkeypatch, capsys):
    monkeypatch.setattr(sweep, "_sdist_members", lambda: ("", []))
    sweep.sweep_sdist([])
    out = capsys.readouterr().out
    assert "RED" in out


# -- icerik tarama ---------------------------------------------------------------------------------

def test_secret_hit_red(fake, capsys):
    fake["members"] = [("pkg/cfg.py", "API_SECRET = 'abc'")]
    import re
    assert sweep.sweep_sdist([re.compile(r"API_SECRET")]) == 1


def test_hit_printed(fake, capsys):
    fake["members"] = [("pkg/cfg.py", "API_SECRET='x'")]
    import re
    sweep.sweep_sdist([re.compile(r"API_SECRET")])
    out = capsys.readouterr().out
    assert "RED" in out


def test_member_name_shown(fake, capsys):
    fake["members"] = [("pkg/cfg.py", "API_SECRET='x'")]
    import re
    sweep.sweep_sdist([re.compile(r"API_SECRET")])
    out = capsys.readouterr().out
    assert "pkg/cfg.py" in out


def test_multiple_patterns(fake, capsys):
    fake["members"] = [("pkg/c.py", "token='1'")]
    import re
    assert sweep.sweep_sdist(
        [re.compile(r"API_SECRET"), re.compile(r"token")]) == 1


def test_multiple_hits(fake, capsys):
    fake["members"] = [("a.py", "API_SECRET"), ("b.py", "API_SECRET")]
    import re
    sweep.sweep_sdist([re.compile(r"API_SECRET")])
    out = capsys.readouterr().out
    assert out.count("API_SECRET") >= 2


def test_no_pattern_no_hit(fake, capsys):
    fake["members"] = [("pkg/c.py", "API_SECRET")]
    assert sweep.sweep_sdist([]) == 0


# -- ikili dosya ---------------------------------------------------------------------------------

def test_binary_skipped(fake, capsys):
    """Ikil (undecodable) dosyalar atlanir."""
    state = fake
    state["members"] = [("pkg/bin.dat", "")]

    def _read_bin(sdist, member):
        if member.endswith(".dat"):
            return b"\xff\xfe\x00binary"
        return b"temiz"
    sweep._read_bytes = _read_bin
    import re
    assert sweep.sweep_sdist([re.compile(r"SECRET")]) == 0


def test_missing_member_red(monkeypatch, capsys):
    """Uye okunamiyorsa (KeyError) RED."""
    monkeypatch.setattr(sweep, "_sdist_members",
                        lambda: ("t.tar.gz", ["gone.py"]))
    monkeypatch.setattr(sweep, "_read_bytes",
                        lambda s, m: (_ for _ in ()).throw(KeyError(m)))
    assert sweep.sweep_sdist([]) == 1


# -- uyke-adi tarama ---------------------------------------------------------------------------------

def test_member_name_pattern_red(fake, capsys):
    """Uye adinda gizli kelime -> RED (ikili tarama)."""
    fake["members"] = [("pkg/.env", "")]
    import re
    assert sweep.sweep_sdist([re.compile(r"\.env")]) == 1


def test_member_name_hit_reported(fake, capsys):
    fake["members"] = [("pkg/secret.key", "")]
    import re
    sweep.sweep_sdist([re.compile(r"secret")])
    out = capsys.readouterr().out
    assert "secret.key" in out


def test_case_sensitive(fake, capsys):
    fake["members"] = [("pkg/a.py", "API_SECRET")]
    import re
    assert sweep.sweep_sdist([re.compile(r"api_secret")]) == 0


# -- sinir ---------------------------------------------------------------------------------

def test_many_hits_truncated(fake, capsys):
    """40+ hit listesi kisaltilir."""
    fake["members"] = [(f"pkg/f{i}.py", "API_SECRET") for i in range(50)]
    import re
    sweep.sweep_sdist([re.compile(r"API_SECRET")])
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if "f" in l and ".py" in l]
    assert len(lines) <= 45


def test_repeatable(fake, capsys):
    fake["members"] = [("pkg/a.py", "temiz")]
    import re
    r1 = sweep.sweep_sdist([re.compile(r"X")])
    r2 = sweep.sweep_sdist([re.compile(r"X")])
    assert r1 == r2
