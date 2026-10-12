r"""Sester scripts.s2_protocol_parity._hmac_header + mcp.server._json_out + scripts.make_brand_assets._spaced_width + scripts.public_surface_sweep._compile dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory + capsys + fake-font ( HMAC/regex/JSON; PIL-
font STUB'u; DIS-AG/ledger/UCP CAGRILMAZ).

ORTAM-ANATOMI:
- _hmac_header(nonce): 'pugio0 <wallet>:<nonce>:<amount>:<hmac>' ( HMAC-SHA256)
- _json_out(obj): MCP stdio'ya JSON-RPC yazimi ( stdout)
- _spaced_width(text, font, tracking): harf-aralikli metin-genisligi
- _compile(): FORBIDDEN regex-derlemesi ( re.IGNORECASE)
"""
import hashlib
import hmac
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
from make_brand_assets import _spaced_width  # noqa: E402
from public_surface_sweep import FORBIDDEN, _compile  # noqa: E402
from s2_protocol_parity import (  # noqa: E402
    PRICE,
    RESOURCE,
    SECRET,
    WALLET,
    _hmac_header,
)

# ORTAM-OGRENDI: kurulu 'mcp' PyPI-paketi yerel mcp/ dizinini GOLGELER
# ( site-packages mcp/server/__init__.py). Bu yuzden modul DOSYADAN yuklenir.
_spec = importlib.util.spec_from_file_location(
    "sester_mcp_server", Path("mcp/server.py").resolve())
_sester_mcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sester_mcp)
_json_out = _sester_mcp._json_out


class FakeFont:
    """PIL ImageFont stub ( getlength)."""

    def __init__(self, w=10.0):
        self.w = w

    def getlength(self, c):
        return self.w * len(c)


# == _hmac_header ======================================================================================

def _parts(nonce):
    """'pugio0 <wallet>:<nonce>:<amount>:<mac>' -> [wallet, nonce, amount, mac]."""
    return _hmac_header(nonce)[0][len("pugio0 "):].split(":")


def test_hmac_yapi():
    """ORTAM: 'pugio0 <wallet>:<nonce>:<amount>:<hmac>'."""
    h, n = _hmac_header("nonce-1")
    assert h.startswith("pugio0 ")
    parts = _parts("nonce-1")
    assert parts[0] == WALLET
    assert parts[1] == "nonce-1"
    assert parts[2] == f"{PRICE:.2f}"
    assert len(parts[3]) == 64


def test_hmac_nonce_ikinci_eleman():
    """ORTAM: tuple[1] = nonce ( zarf-ici intent_id)."""
    assert _hmac_header("abc-123")[1] == "abc-123"


def test_hmac_deger_dogrulama():
    """ORTAM: HMAC-SHA256( SECRET, '{wallet}|{nonce}|{amount}|{resource}')."""
    amount_s = f"{PRICE:.2f}"
    bek = hmac.new(SECRET.encode(),
                   f"{WALLET}|nonce-1|{amount_s}|{RESOURCE}".encode(),
                   hashlib.sha256).hexdigest()
    assert _parts("nonce-1")[3] == bek


def test_hmac_oncek():
    """ORTAM: 'pugio0' oneki ( S2 protokol-scheme)."""
    assert _hmac_header("x")[0].startswith("pugio0 ")


def test_hmac_tutar_sabit_genislik():
    """ORTAM: amount ':.2f' ( 2-basamak)."""
    assert _parts("x")[2] == f"{PRICE:.2f}"
    assert len(_parts("x")[2].split(".")[1]) == 2


def test_hmac_mac_64_hex():
    """ORTAM: SHA-256 hex 64-karakter."""
    mac = _parts("x")[3]
    assert len(mac) == 64
    assert all(c in "0123456789abcdef" for c in mac)


def test_hmac_nonce_degisir_mac():
    """ORTAM: farkli nonce -> farkli HMAC."""
    a = _parts("n1")[3]
    b = _parts("n2")[3]
    assert a != b


def test_hmac_stabil():
    """ORTAM: ayni nonce -> ayni HMAC ( deterministik)."""
    assert _hmac_header("n1")[0] == _hmac_header("n1")[0]


def test_hmac_turkce_nonce():
    """ORTAM: UTF-8 nonce ( 'çeşit-1' -> encode)."""
    h, n = _hmac_header("çeşit-1")
    assert n == "çeşit-1"
    assert "çeşit-1" in h


def test_hmac_bos_nonce():
    """ORTAM: bos nonce -> bos-alan."""
    h, n = _hmac_header("")
    assert n == ""
    assert "::" in h


def test_hmac_ozel_karakter_nonce():
    """ORTAM: ':' iceren nonce header'i BOZAR ( split(':') kullanimda
    dikkat — nonce icinde ':' AYIRAC ile karisir)."""
    h, n = _hmac_header("a:b")
    assert n == "a:b"
    parts = _parts("a:b")
    # ':' nonce'u header-ayiraci ile KARISIR: parts[1]=='a', parts[2]=='b'
    assert parts[1] == "a"
    assert parts[2] == "b"


def test_hmac_donut_tuple():
    r = _hmac_header("x")
    assert isinstance(r, tuple) and len(r) == 2


def test_hmac_donut_str():
    assert isinstance(_hmac_header("x")[0], str)


def test_hmac_mac_hesaplanabilir():
    """ORTAM: HMAC SECRET ile bağımsız doğrulanabilir ( alıcı-taraf)."""
    wallet, nonce, amount, mac = _parts("dogrula-beni")
    bek = hmac.new(SECRET.encode(),
                   f"{wallet}|{nonce}|{amount}|{RESOURCE}".encode(),
                   hashlib.sha256).hexdigest()
    assert mac == bek


# == _json_out =========================================================================================

def test_json_out_yazar(capsys):
    """ORTAM: stdout'a JSON + yeni-satir."""
    _json_out({"a": 1})
    out = capsys.readouterr()
    assert out.out == '{"a": 1}\n'


def test_json_out_stderr_temiz(capsys):
    """ORTAM: stderr'e HICBIR sey ( MCP stdio)."""
    _json_out({"a": 1})
    assert capsys.readouterr().err == ""


def test_json_out_turkce_ensure_ascii_false(capsys):
    """ORTAM-OGRENDI: ensure_ascii=False — Türkçe kaçış YAPILMAZ
    ( 'ç' -> 'ç', '\\u00e7' DEGIL)."""
    _json_out({"mesaj": "çğıöşü"})
    assert capsys.readouterr().out == '{"mesaj": "çğıöşü"}\n'


def test_json_out_geri_okuma(capsys):
    """ORTAM: json.loads ile geri-okuma ( MCP client taraf)."""
    _json_out({"b": [1, 2], "c": None})
    assert json.loads(capsys.readouterr().out) == {"b": [1, 2], "c": None}


def test_json_out_coklu(capsys):
    """ORTAM: her-cagri yeni-satir ( line-delimited JSON-RPC)."""
    _json_out({"a": 1})
    _json_out({"b": 2})
    lines = capsys.readouterr().out.strip().split("\n")
    assert len(lines) == 2


def test_json_out_flush(capsys):
    """ORTAM: sys.stdout.flush() ( anlik-teslim)."""
    _json_out({"a": 1})
    capsys.readouterr()


def test_json_out_ic_ice(capsys):
    _json_out({"content": [{"type": "text", "text": "merhaba"}],
               "isError": False})
    out = capsys.readouterr().out
    assert json.loads(out)["content"][0]["text"] == "merhaba"


def test_json_out_bos_dict(capsys):
    _json_out({})
    assert capsys.readouterr().out == "{}\n"


def test_json_out_stabil(capsys):
    _json_out({"x": 1})
    a = capsys.readouterr().out
    _json_out({"x": 1})
    assert capsys.readouterr().out == a


# == _spaced_width =====================================================================================

def test_spaced_temel():
    """ORTAM: sum(getlength(c)+tracking) - tracking."""
    assert _spaced_width("abc", FakeFont(10), 2) == 34.0


def test_spaced_hesap():
    """ORTAM: 3-harf * (10+2) - 2 = 34."""
    assert _spaced_width("abc", FakeFont(10.0), 2) == 3 * 12 - 2


def test_spaced_tek_harf():
    """ORTAM: 1-harf -> getlength ( tracking CIKILMAZ)."""
    assert _spaced_width("a", FakeFont(10), 5) == 10.0


def test_spaced_bos_metin():
    """ORTAM-OGRENDI: '' -> -tracking ( NEGATIF! sum([])=0 - tracking)."""
    assert _spaced_width("", FakeFont(10), 2) == -2


def test_spaced_sifir_tracking():
    """ORTAM: tracking=0 -> toplam-getlength."""
    assert _spaced_width("abc", FakeFont(10), 0) == 30.0


def test_spaced_negatif_tracking():
    """ORTAM: negatif tracking -> daralma."""
    assert _spaced_width("abc", FakeFont(10), -2) == 26.0


def test_spaced_turkce_karakter():
    """ORTAM: 'ç' 1-char sayilir ( font.getlength)."""
    assert _spaced_width("ç", FakeFont(10), 2) == 10.0


def test_spaced_donut_float():
    """ORTAM: PIL getlength float doner ( gercek-font)."""
    assert isinstance(_spaced_width("a", FakeFont(10.0), 0), float)


def test_spaced_stabil():
    assert _spaced_width("abc", FakeFont(10), 2) == \
        _spaced_width("abc", FakeFont(10), 2)


def test_spaced_genis_font():
    """ORTAM: font-genisligi dogru-toplanir ( 20-width font)."""
    assert _spaced_width("ab", FakeFont(20), 0) == 40.0


def test_spaced_uzun_metin():
    """ORTAM: 100-harf * (10+1) - 1 = 1099."""
    assert _spaced_width("a" * 100, FakeFont(10), 1) == 1099.0


# == _compile ==========================================================================================

def test_compile_sayi():
    """ORTAM: FORBIDDEN listesinin tamamini derler."""
    assert len(_compile()) == len(FORBIDDEN)


def test_compile_donut_pattern_listesi():
    """ORTAM: list[re.Pattern]."""
    pats = _compile()
    assert all(isinstance(p, re.Pattern) for p in pats)


def test_compile_ignorecase():
    """ORTAM-OGRENDI: re.IGNORECASE ( 34) — BUYUK/kucuk harf duyarsiz;
    'GOKUN' ve 'gokun' ikisi de eslesir."""
    pats = _compile()
    assert all(p.flags & re.IGNORECASE for p in pats)
    assert pats[0].search("GOKUN")
    assert pats[0].search("gokun")


def test_compile_stabil():
    assert _compile() == _compile()


def test_compile_eslesme_gokun():
    """ORTAM: 'gokun' FORBIDDEN."""
    pats = _compile()
    assert pats[0].pattern == "gokun"
    assert pats[0].search("kullanici: gokun")


def test_compile_eslesme_uni_dizin():
    """ORTAM: '01_unicorn' / '02_sahis' ( dizin-adleri)."""
    pats = _compile()
    assert pats[1].search("yol/01_unicorn/x")
    assert pats[2].search("02_sahis")


def test_compile_eslesme_hat_defter():
    """ORTAM-OGRENDI: 'HAT[_ ]?DEFTER' — '_' VEYA ' ' opsiyonel
    ( 'HATDEFTER' ve 'HAT DEFTER' ikisi de)."""
    p = _compile()[4]
    assert p.pattern == r"HAT[_ ]?DEFTER"
    assert p.search("HATDEFTER")
    assert p.search("HAT_DEFTER")
    assert p.search("HAT DEFTER")
    assert not p.search("HAT--DEFTER")


def test_compile_eslesme_agent_mesh():
    """ORTAM: 'AGENT[_ ]?MESH'."""
    p = _compile()[5]
    assert p.search("AGENT_MESH")
    assert p.search("AGENTMESH")
    assert p.search("agent mesh")


def test_compile_eslesme_kagit():
    """ORTAM: 'KAGIT\\.md' ( nokta-escape)."""
    p = _compile()[8]
    assert p.search("KAGIT.md")
    assert not p.search("KAGITXmd")


def test_compile_eslesme_arastirma_sayi():
    """ORTAM: 'ARASTIRMA_\\d{4}' ( 4-hane zorunlu)."""
    p = _compile()[13]
    assert p.search("ARASTIRMA_2026")
    assert not p.search("ARASTIRMA_26")


def test_compile_eslesme_sester_yol():
    """ORTAM: '63-Sester' / '64-Tenderix' ( son-iki)."""
    pats = _compile()
    assert pats[-2].search("63-Sester/README")
    assert pats[-1].search("64-Tenderix")


def test_compile_eslesmeyen():
    """ORTAM: temiz-metin eslesmez."""
    pats = _compile()
    text = "bu tamamen normal bir metindir"
    assert not any(p.search(text) for p in pats)


def test_compile_hazir_pattern():
    """ORTAM: her-pattern derlenmis-hazir ( re.compile her-seferinde
    yeniden-derlemez)."""
    pats = _compile()
    m1 = pats[0].search("gokun")
    m2 = pats[0].search("gokun")
    assert m1.span() == m2.span()


@pytest.mark.parametrize("i,kelime", [(0, "gokun"), (1, "01_unicorn"),
                                      (6, "AjanTicaret"), (7, "AjanGuvence"),
                                      (11, "KURAL_DSL"), (16, "ESKI_KIMLIK")])
def test_compile_tablo(i, kelime):
    """ORTAM: FORBIDDEN katalogu ( dizin-adi + belge-adleri)."""
    assert _compile()[i].pattern == kelime


# == karakterizasyon ===================================================================================

def test_hmac_amaci():
    r"""ORTAM-OGRENDI (DOCSTACK): S2 protokol 'pugio0' scheme; HMAC-SHA256
SECRET ile; mesaj '{wallet}|{nonce}|{amount}|{resource}'; amount ':.2f'
sabit-genislik; nonce = intent_id ( zarf-ici); alici-taraf ayni HMAC'i
hesaplayip dogrular; NONCE-ICINDE ':' HEADER-AYIRACI ILE KARISIR."""
    assert _parts("n")[3] == hmac.new(
        SECRET.encode(),
        f"{WALLET}|n|{PRICE:.2f}|{RESOURCE}".encode(),
        hashlib.sha256).hexdigest()


def test_compile_amaci():
    r"""ORTAM-OGRENDI (DOCSTACK): FORBIDDEN listesi ( 19 member) her-
cagri re.IGNORECASE ile derlenir; buyuk/kucuk duyarsiz; '_' VEYA ' '
opsiyyonel-ayrac ('HAT[_ ]?DEFTER'); '.' escape ('KAGIT\\.md'); '\d{4}'
zorunlu-4-hane ('ARASTIRMA_\d{4}')."""
    assert len(_compile()) == 19
    assert _compile()[4].search("HAT DEFTER")
