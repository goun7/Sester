"""sester.adapters._b64u_encode / _b64u_decode dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (base64 saf-matematik, dis cagri YOK).
urlsafe-base64 (RFC-4648 §5) padding'siz kodlayici/cozucu cifti.
"""
import base64

import pytest

from sester.adapters import _b64u_decode, _b64u_encode


# -- yardimci -----------------------------------------------------------------------------------

def std_b64u(raw: bytes) -> str:
    """Referans urlsafe-base64 (padding'li) — uretimden BAGIMSIZ dogruluk icin."""
    return base64.urlsafe_b64encode(raw).decode()


def std_decode(seg: str) -> bytes:
    padded = seg + "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(padded)


# -- _b64u_encode: mutlu-yol --------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    b"", b"a", b"ab", b"abc", b"abcd", b"abcde",
    b"\x00", b"\x00\x00", b"\x00\x00\x00",
    b"\xff", b"\xff\xfe", b"\xff\xfe\xfd",
    b"hello", b"hello world", b"MERHABA",
    b"x" * 100, b"y" * 255,
])
def test_encode_matches_reference(raw):
    """Kodlama referans urlsafe-b64 ile birebir (padding hariç)."""
    assert _b64u_encode(raw) == std_b64u(raw).rstrip("=")


@pytest.mark.parametrize("raw", [
    b"", b"a", b"ab", b"abc", b"abcd",
    b"\x00\x01\x02", b"\xff\xfe\xfd\xfc",
    b"turkce-gitti", b"emoji-\xf0\x9f\x98\x80",
])
def test_encode_no_padding_char(raw):
    """ORTAM: '=' padding KALDIRILIR (urlsafe segmentlerde padding yasak)."""
    assert "=" not in _b64u_encode(raw)


@pytest.mark.parametrize("raw", [
    b"\xff\xfe", b"\xfb\xff\xfe", b"\x00?", b"+/" b"~",
    b"\x3f\x3f\x3f", b"\x2b\x2f",
])
def test_encode_urlsafe_alphabet_only(raw):
    """ORTAM: '+'/'/' YERINE '-_' (urlsafe alfabe)."""
    e = _b64u_encode(raw)
    assert "+" not in e and "/" not in e
    assert set(e) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


def test_encode_returns_str():
    assert isinstance(_b64u_encode(b"x"), str)


@pytest.mark.parametrize("raw", [
    b"", b"\x00", b"\xff", b"abc", b"\x01\x02\x03\x04\x05",
    b"sester", b"\xf0\x9f\x98\x80\xe2\x9c\x93",
])
def test_encode_roundtrips_through_decode(raw):
    """encode -> decode birebir geri doner (ciftin invarianti)."""
    assert _b64u_decode(_b64u_encode(raw)) == raw


# -- _b64u_encode: belirli degerler -------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    (b"", ""),
    (b"a", "YQ"),
    (b"ab", "YWI"),
    (b"abc", "YWJj"),
    (b"abcd", "YWJjZA"),
    (b"\x00", "AA"),
    (b"\x00\x00", "AAA"),
    (b"\xff", "_w"),
    (b"\xff\xff", "__8"),
    (b"\xff\xff\xff", "____"),
    (b"Man", "TWFu"),
    (b"Ma", "TWE"),
    (b"??-~", "Pz8tfg"),
])
def test_encode_known_vectors(raw, expected):
    assert _b64u_encode(raw) == expected


@pytest.mark.parametrize("raw", [b"a", b"ab", b"abc", b"abcd", b"abcde", b"abcdef", b"abcdefg"])
def test_encode_length_formula(raw):
    """Uzunluk = ceil(len*4/3), padding'siz."""
    assert len(_b64u_encode(raw)) == -(-len(raw) * 4 // 3)


def test_encode_deterministic():
    assert _b64u_encode(b"seed") == _b64u_encode(b"seed")


@pytest.mark.parametrize("a,b", [(b"a", b"b"), (b"x", b"xx"), (b"\x00", b"\x01")])
def test_encode_different_inputs_differ(a, b):
    assert _b64u_encode(a) != _b64u_encode(b)


# -- _b64u_encode: tur/unicode -------------------------------------------------------------------

@pytest.mark.parametrize("text", ["merhaba", "ğüşiöç", "😀", "日本語", "a\nb", "tab\there"])
def test_encode_utf8_text(text):
    raw = text.encode()
    assert _b64u_decode(_b64u_encode(raw)) == raw


def test_encode_accepts_bytearray():
    assert _b64u_encode(bytearray(b"abc")) == "YWJj"


def test_encode_large_input():
    raw = bytes(range(256)) * 4
    e = _b64u_encode(raw)
    assert std_decode(e) == raw


# -- _b64u_decode: mutlu-yol ---------------------------------------------------------------------

@pytest.mark.parametrize("nbytes", [0, 1, 2, 3, 4, 5, 6, 7, 8, 16, 31, 32, 63, 64, 100, 255])
def test_decode_roundtrip_various_lengths(nbytes):
    raw = bytes((i * 7 + 3) & 0xFF for i in range(nbytes))
    seg = _b64u_encode(raw)
    assert _b64u_decode(seg) == raw


@pytest.mark.parametrize("seg,expected", [
    ("", b""),
    ("YQ", b"a"),
    ("YWI", b"ab"),
    ("YWJj", b"abc"),
    ("YWJjZA", b"abcd"),
    ("TWFu", b"Man"),
    ("TWE", b"Ma"),
    ("_w", b"\xff"),
    ("__8", b"\xff\xff"),
    ("____", b"\xff\xff\xff"),
    ("aGVsbG8", b"hello"),
    ("aGVsbG8gd29ybGQ", b"hello world"),
])
def test_decode_known_vectors(seg, expected):
    assert _b64u_decode(seg) == expected


# -- _b64u_decode: OTOMATIK-PADDING (ORTAM-OGRENDI) ----------------------------------------------

@pytest.mark.parametrize("seg", ["YQ", "YWI", "YWJj", "YWJjZA", "TWFu", "__8", "aGVsbG8"])
def test_decode_strips_then_rePads(seg):
    """ORTAM: -len%4 kadar '=' otomatik eklenir (padding'siz girdi kabul)."""
    assert _b64u_decode(seg) == std_decode(seg)


@pytest.mark.parametrize("seg", ["YQ==", "YWI=", "YWJj", "TWFu", "__8=", "TWE=", "TWFu="])
def test_decode_accepts_already_padded(seg):
    """ORTAM: padding'LI girdi de calisir (cift-tolerans)."""
    assert _b64u_decode(seg) == base64.urlsafe_b64decode(seg)


@pytest.mark.parametrize("seg", [
    "YQ", "YWI", "YWJj", "aGVsbG8", "TWFu", "__8", "Pz8tfg", "eHh4",
])
def test_decode_explicit_padding_equals(seg):
    padded = seg + "=" * (-len(seg) % 4)
    assert _b64u_decode(seg) == _b64u_decode(padded)


# -- _b64u_decode: urlsafe vs standart alfabe ----------------------------------------------------

@pytest.mark.parametrize("seg", ["__8", "____", "_w", "___", "-___", "____-w"])
def test_decode_urlsafe_chars(seg):
    """ORTAM: '-' ve '_' urlsafe-alfabe olarak cozulur (+// yerine)."""
    assert _b64u_decode(seg) == std_decode(seg)


@pytest.mark.parametrize("std,urlsafe", [("+/b", "-_b"), ("++//", "--__"), ("a+b", "a-b")])
def test_decode_standart_b64_also_works(std, urlsafe):
    """ORTAM: standart-b64 '+'/'/' girdisi de urlsafe-cozucude kabul edilir
    (base64.urlsafe_b64decode her ikisini de esler)."""
    assert _b64u_decode(std) == _b64u_decode(urlsafe)


# -- _b64u_decode: hata-dallari ------------------------------------------------------------------

@pytest.mark.parametrize("seg", ["a", "A", "abcde", "aGVsbG8gd"])
def test_decode_len_mod4_eq_1_raises(seg):
    """ORTAM-OGRENDI: len%4==1 girdi -> binance.Error (1 fazla karakter
    4'luk blok olamaz — 6-bit kalinti)."""
    with pytest.raises(Exception) as ei:
        _b64u_decode(seg)
    assert "cannot be 1 more than a multiple of 4" in str(ei.value) or \
           "number of data characters" in str(ei.value)


@pytest.mark.parametrize("seg", ["YWI ", "YWI!", "YQ!", "a b", "YWI~", "YWI\x00"])
def test_decode_trailing_garbage_raises(seg):
    """ORTAM-OGRENDI: gecerli-quantum sonrasi trailing-cop -> 'Incorrect padding'
    (CPython a2b_base64 trailing-temizleme YAPAR ama quantum sonrasi kirletirse
    padding-bozuk)."""
    with pytest.raises(Exception) as ei:
        _b64u_decode(seg)
    assert "Incorrect padding" in str(ei.value) or "data characters" in str(ei.value)


@pytest.mark.parametrize("seg", ["!", "@#", "~", "~~~", "~~>", "!!!!", "@@@@"])
def test_decode_all_invalid_chars_returns_empty(seg):
    """ORTAM-OGRENDI: TAMAMI alfabe-disi karakter -> sessizce b'' (exception YOK —
    CPython a2b_base64 non-alphabet karakterleri DISCARD eder, bos quantum -> bos)."""
    assert _b64u_decode(seg) == b""


@pytest.mark.parametrize("seg,expected", [
    ("he!!o", b"\x85\xea"),
    ("Y!W!I", b"ab"),
    ("Y  WI", b"ab"),
    ("  YWI", b"ab"),
    ("Y\n\nWI", b"ab"),
    ("hxexllo", b"\x87\x17\xb1\x96Z"),
    ("a\nb\nc", b"i\xb7"),
    ("TWFu ", b"Man"),
    ("YWIx!", b"ab1"),
])
def test_decode_middle_invalid_chars_discarded(seg, expected):
    """ORTAM-OGRENDI: alfabe-disi karakterler SESSIZCE ATILIR (validate=False
    semantigi) — '!'/'~'/bosluk/yeni-satir yok-sayilir, kalan gecerli quantum
    cozulur. GERI-UYUM/quirk: bozuk-girdi hata-vermez, sessiz-gecer."""
    assert _b64u_decode(seg) == expected


@pytest.mark.parametrize("seg", ["Y\nW\nI", "Y W I", "  YWI", "Y\n\nWI"])
def test_decode_whitespace_discarded(seg):
    """ORTAM: bosluk/yeni-satir karakterleri discard edilir (MIME-tolerans)."""
    assert _b64u_decode(seg) == b"ab"


@pytest.mark.parametrize("seg,expected", [
    ("YQ", b"a"), ("YQ=", b"a"), ("YQ==", b"a"), ("YQ===", b"a"),
    ("YWI", b"ab"), ("YWI=", b"ab"), ("YWI==", b"ab"),
    ("TWFu", b"Man"), ("TWFu=", b"Man"), ("TWFu===", b"Man"),
])
def test_decode_extra_padding_ignored(seg, expected):
    """ORTAM-OGRENDI: FAZLA '=' padding hata-verMEZ — a2b_base64 padding sayisini
    dogrulamaz (min 1 yeterli); 'YQ===' -> yine b'a'."""
    assert _b64u_decode(seg) == expected


def test_decode_returns_bytes():
    assert isinstance(_b64u_decode("YWI"), bytes)


def test_decode_empty_returns_empty():
    assert _b64u_decode("") == b""


def test_decode_invalid_quantum_still_errors():
    """ORTAM: 4-karakter ama icinde len%4==1'den baska bozukluk -> hata."""
    with pytest.raises(Exception):
        _b64u_decode("a=== ")
    with pytest.raises(Exception):
        _b64u_decode("hello!")


# -- ortak invariantlar --------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    b"", b"\x00", b"\xff", b"abc", b"\x01\x02", b"sester-demo",
    bytes(range(64)), b"\xf0\x9f\x98\x80" * 10,
])
def test_roundtrip_property(raw):
    seg = _b64u_encode(raw)
    assert isinstance(seg, str)
    assert _b64u_decode(seg) == raw


@pytest.mark.parametrize("raw", [b"", b"a", b"abc", b"\xff\xfe\xfd\xfc\xfb"])
def test_encode_is_prefix_free_of_padding(raw):
    """ORTAM: encode hicbir zaman '=' ile bitmez (padding kaldirilmis)."""
    assert not _b64u_encode(raw).endswith("=")


@pytest.mark.parametrize("seg", ["YQ", "YWI", "YWJj"])
def test_decode_does_not_depend_on_surrounding_case(seg):
    """Case-sensitive alfabe — buyuk/kucuk farkli byte'lar."""
    assert _b64u_decode(seg.lower()) == std_decode(seg.lower())
    assert _b64u_decode(seg.upper()) == std_decode(seg.upper())
