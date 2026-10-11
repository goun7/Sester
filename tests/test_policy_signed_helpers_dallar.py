"""sester.policy_signed._hms + _window + _is_relaxation dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (int-aritmetik/list-iterasyon saf, dis cagri YOK).
(1) _hms: 'HH:MM' -> dakika (int(s[:2])*60 + int(s[3:]));
(2) _window: hour-between pencere-uzunlugu (gece-boyu dahil);
(3) _is_relaxation: changes listesinde 'relax' varligi.
"""
import pytest

from sester.policy_signed import _hms, _is_relaxation, _window


# == _hms =======================================================================================

@pytest.mark.parametrize("s,expected", [
    ("00:00", 0), ("00:01", 1), ("00:30", 30), ("00:59", 59),
    ("01:00", 60), ("01:01", 61), ("01:30", 90),
    ("09:00", 540), ("09:30", 570), ("10:00", 600),
    ("12:00", 720), ("12:30", 750), ("15:30", 930),
    ("23:00", 1380), ("23:59", 1439),
])
def test_hms_minutes(s, expected):
    """ORTAM-ANATOMI: int(s[:2])*60 + int(s[3:]) — saat*60+dakika."""
    assert _hms(s) == expected


@pytest.mark.parametrize("h,m", [(0, 0), (5, 5), (12, 30), (23, 59), (7, 0)])
def test_hms_formula(h, m):
    assert _hms(f"{h:02d}:{m:02d}") == h * 60 + m


def test_hms_returns_int():
    assert isinstance(_hms("01:00"), int)


@pytest.mark.parametrize("s,expected", [
    ("00:00", 0), ("01:00", 60), ("23:59", 1439), ("10:00", 600), ("00:05", 5),
])
def test_hms_zero_padding(s, expected):
    assert _hms(s) == expected


@pytest.mark.parametrize("s,expected", [
    (" 1:00", 60), ("1 :00", 60), ("01: 5", 65),
])
def test_hms_whitespace_tolerance(s, expected):
    """ORTAM-OGRENDI: int() basit/sonra bosluklar TOLERANS-LI (' 1' -> 1)
    AMA SADECE tek-bosluk (cift-bosluk s[:2]iki boler)."""
    assert _hms(s) == expected


@pytest.mark.parametrize("s", ["1  :00", " 9 : 30", "01:  59x"])
def test_hms_double_space_raises(s):
    """ORTAM-OGRENDI: cift-boslukta s[:2]='1 '/' 9' -> int('1 ')='1' ama s[3:]
    kayarak ':' veya baska-boluk verir -> ValueError."""
    with pytest.raises(ValueError):
        _hms(s)


def test_hms_double_space_minute_slot_works():
    """ORTAM-OGRENDI: '01:  5' -> s[:2]='01', s[3:]=' 5' -> int(' 5')=5 -> 65
    (int bas-bosluk tolere eder)."""
    assert _hms("01:  5") == 65


@pytest.mark.parametrize("s", [
    "0:0", "1:5", "9:09", "007:00", "ab:cd", "", ":", ":30", "30:", "1:2:3",
    "1::0", "100", "abc", "--:--", "1:",
])
def test_hms_malformed_raises(s):
    """ORTAM-OGRENDI: TEK-HANE formatlar ('0:0') ValueError — s[:2] '0:' yakalar,
    int('0:') hata. Kesin 'HH:MM' (2-hane) format beklenir."""
    with pytest.raises(ValueError):
        _hms(s)


@pytest.mark.parametrize("s", ["1:0", "9:5", "5:30"])
def test_hms_single_digit_hour_minute_raises(s):
    """ORTAM: 1-hane saat veya 1-hane dakika int('x:') ValueError."""
    with pytest.raises(ValueError):
        _hms(s)


def test_hms_single_digit_minute_29():
    """ORTAM-OGRENDI: '23:9' -> s[:2]='23', s[3:]='9' -> int('9')=9 -> 1389
    (3.karakter-atlamasi '9'u yakalar — 1-hane dakika KABUL!)."""
    assert _hms("23:9") == 1389


@pytest.mark.parametrize("s,expected", [
    ("007:00", 7 * 60), ("009:30", 9 * 60 + 30), ("012:00", 12 * 60),
])
def test_hms_three_digit_hour(s, expected):
    """ORTAM-OGRENDI: 3-hane saat s[:2] SADECE ilk-ikisini alir ('007'->'00')."""
    # '007:00' -> s[:2]='00' -> 0; s[3:]='7:00'?? int('7:00') ValueError
    with pytest.raises(ValueError):
        _hms(s)


def test_hms_leading_plus():
    """ORTAM: '+1:00' -> int('+1')=+1 calisir (Python int '+1' kabul)."""
    # '+1:00' s[:2]='+1' int('+1')=1, s[3:]='00' -> 60
    assert _hms("+1:00") == 60


@pytest.mark.parametrize("s,expected", [
    ("24:00", 1440), ("25:00", 1500), ("99:99", 99 * 60 + 99),
])
def test_hms_no_range_validation(s, expected):
    """ORTAM-OGRENDI: 24+:00 / 99:99 SINIR-KONTROLU YOK — saf int-aritmetik."""
    assert _hms(s) == expected


@pytest.mark.parametrize("s,expected", [
    ("-1:00", -60), ("00:-1", -1),
])
def test_hms_negative_values(s, expected):
    """ORTAM-OGRENDI: negatif degerler SINIR-KONTROLU YOK — '-1:00' -> -60;
    '00:-1' -> s[3:]='-1' -> int=−1 (aritmetik negatife izin verir)."""
    assert _hms(s) == expected


def test_hms_negative_hour_formula():
    """ORTAM: int('-1')=-1 -> -60 (Python int '+'/'-' kabul)."""
    assert _hms("-1:00") == -60


def test_hms_minute_truncation():
    """ORTAM: s[3:] 3.karakterden sonrasini alir — '01:059' -> int('059')=59."""
    assert _hms("01:059") == 60 + 59


def test_hms_colon_absent_raises():
    """ORTAM-OGRENDI: ':' YOKSA s[3:] 3.karakterden alir — '0100' -> s[:2]='01',
    s[3:]='0' -> 60 (hata YOK!). '01' (kisa) -> s[3:]='' -> ValueError."""
    assert _hms("0100") == 60
    with pytest.raises(ValueError):
        _hms("01")


# == _window ====================================================================================

@pytest.mark.parametrize("hb,expected", [
    (["00:00", "00:00"], 1440),
    (["12:00", "12:00"], 1440),
    (["00:00", "01:00"], 60),
    (["00:00", "00:30"], 30),
    (["01:00", "00:00"], 1380),
    (["23:00", "01:00"], 120),
    (["22:00", "06:00"], 480),
    (["00:00", "23:59"], 1439),
    (["06:00", "18:00"], 720),
    (["18:00", "06:00"], 720),
    (["23:59", "00:00"], 1),
])
def test_window_minutes(hb, expected):
    """ORTAM-ANATOMI: (end-start) % 1440 or 1440 — gece-boyu (end<start) MOD ile
    duzgun-hesaplanir; tam-gunde 0 -> 1440."""
    assert _window(hb) == expected


def test_window_returns_int():
    assert isinstance(_window(["00:00", "01:00"]), int)


@pytest.mark.parametrize("hb", [["00:00", "00:00"], ["12:00", "12:00"], ["23:00", "23:00"]])
def test_window_zero_span_is_full_day(hb):
    """ORTAM-OGRENDI: baslangic==bitis -> 0 -> 'or 1440' -> 1440 (bos-pencere
    TAM-GUN sayilir, 0 DEGIL)."""
    assert _window(hb) == 1440


@pytest.mark.parametrize("hb,expected", [
    (["23:00", "01:00"], 120), (["23:59", "00:01"], 2),
    (["22:00", "02:00"], 240), (["20:00", "04:00"], 480),
])
def test_window_overnight_wraps_mod_1440(hb, expected):
    """ORTAM: gece-yarisi gecisi (end<start) mod-1440 ile pozitif sure."""
    assert _window(hb) == expected


@pytest.mark.parametrize("hb", [[], ["00:00"]])
def test_window_short_list_raises(hb):
    """ORTAM: 0/1-elem liste -> hb[1] IndexError YAYILIR."""
    with pytest.raises(IndexError):
        _window(hb)


@pytest.mark.parametrize("hb", [["00:00", "01:00"]])
def test_window_extra_elements_ignored(hb):
    """ORTAM: hb[2+] KULLANILMAZ — sadece ilk-ikisi."""
    assert _window(hb) == 60


def test_window_non_numeric_raises():
    """ORTAM: harf-saat -> int('a') ValueError YAYILIR."""
    with pytest.raises(ValueError):
        _window(["a", "b"])


def test_window_non_list_raises():
    """ORTAM: str girdi -> _hms(str[:2]) hata dali."""
    with pytest.raises(ValueError):
        _window("00:00")


@pytest.mark.parametrize("hb,expected", [
    (["00:00", "24:00"], 1440), (["00:00", "25:00"], 60), (["00:00", "48:00"], 1440),
])
def test_window_hours_beyond_24(hb, expected):
    """ORTAM-OGRENDI: '24:00' -> 1440 % 1440 = 0 -> 1440; '25:00' -> 1500%1440=60
    (sinir-kontrolu YOK — mod dogal-duser)."""
    assert _window(hb) == expected


def test_window_calls_hms_twice():
    """ORTAM: _hms(hb[0]) + _hms(hb[1]) — delege."""
    assert _window(["01:00", "02:00"]) == 60


@pytest.mark.parametrize("start_h,end_h", [(0, 1), (6, 18), (22, 6), (12, 12)])
def test_window_symmetry_documented(start_h, end_h):
    """ORTAM: (a,b) ile (b,a) pencere-uzunluklari 1440'i tamamlar (mod-simetri)."""
    a = f"{start_h:02d}:00"
    b = f"{end_h:02d}:00"
    if _window([a, b]) == 1440:
        assert _window([b, a]) == 1440
    else:
        assert (_window([a, b]) + _window([b, a])) % 1440 == 0 or \
               _window([a, b]) + _window([b, a]) in (1440, 1440 * 2)


# == _is_relaxation =============================================================================

def test_is_relaxation_returns_bool():
    assert isinstance(_is_relaxation([]), bool)


def test_is_relaxation_empty_list_false():
    assert _is_relaxation([]) is False


@pytest.mark.parametrize("changes,expected", [
    ([{"kind": "relax"}], True),
    ([{"kind": "tighten"}], False),
    ([{"kind": "other"}], False),
])
def test_is_relaxation_single(changes, expected):
    assert _is_relaxation(changes) is expected


def test_is_relaxation_empty_dict_raises():
    """ORTAM-OGRENDI: 'kind' alani YOKSA KeyError (asagi dokumante)."""
    with pytest.raises(KeyError):
        _is_relaxation([{}])


@pytest.mark.parametrize("pos", [0, 1, 2, 3])
def test_is_relaxation_any_position(pos):
    """ORTAM: any() — listede HERHANGI bir pozisyonda 'relax' yeterli."""
    changes = [{"kind": "x"}, {"kind": "y"}, {"kind": "z"}, {"kind": "w"}]
    changes[pos] = {"kind": "relax"}
    assert _is_relaxation(changes) is True


@pytest.mark.parametrize("n", [1, 2, 5, 10, 50])
def test_is_relaxation_all_tighten_false(n):
    assert _is_relaxation([{"kind": "tighten"}] * n) is False


@pytest.mark.parametrize("n", [1, 2, 5, 10, 50])
def test_is_relaxation_all_relax_true(n):
    assert _is_relaxation([{"kind": "relax"}] * n) is True


def test_is_relaxation_mixed_true():
    assert _is_relaxation([{"kind": "tighten"}, {"kind": "relax"}, {"kind": "x"}]) is True


def test_is_relaxation_case_sensitive():
    """ORTAM: 'Relax'/'RELAX' eslesMEZ (case-sensitive tam-eslesme)."""
    assert _is_relaxation([{"kind": "Relax"}]) is False
    assert _is_relaxation([{"kind": "RELAX"}]) is False
    assert _is_relaxation([{"kind": " relax"}]) is False


def test_is_relaxation_substring_no_match():
    """ORTAM: 'relaxed'/'relax-x' eslesMEZ (tam-string karsilastirma)."""
    assert _is_relaxation([{"kind": "relaxed"}]) is False
    assert _is_relaxation([{"kind": "relax-x"}]) is False


def test_is_relaxation_missing_kind_raises():
    """ORTAM: 'kind' alani YOKSA KeyError YAYILIR (any kisa-devre yapana kadar)."""
    with pytest.raises(KeyError):
        _is_relaxation([{}])
    with pytest.raises(KeyError):
        _is_relaxation([{"other": 1}])


def test_is_relaxation_missing_kind_after_match():
    """ORTAM: any() kisa-devre — 'relax' bulunursa sonraki KeyError YAYILMAZ."""
    assert _is_relaxation([{"kind": "relax"}, {}]) is True


def test_is_relaxation_key_error_only_after_scan():
    """ORTAM: 'relax' YOKSA KeyError tarama-sonunda yükselir."""
    with pytest.raises(KeyError):
        _is_relaxation([{"kind": "x"}, {}])


@pytest.mark.parametrize("extra", [{"note": "x"}, {"ts": 1}, {"diff": 5}, {}])
def test_is_relaxation_extra_keys_ignored(extra):
    """ORTAM: SADECE 'kind' alanina bakilir."""
    assert _is_relaxation([{"kind": "relax", **extra}]) is True


def test_is_relaxation_input_not_mutated():
    changes = [{"kind": "relax"}, {"kind": "tighten"}]
    before = [dict(c) for c in changes]
    _is_relaxation(changes)
    assert changes == before


def test_is_relaxation_turkce_kind():
    assert _is_relaxation([{"kind": "gevşe"}]) is False
    assert _is_relaxation([{"kind": "relax", "ad": "gevşe"}]) is True


def test_is_relaxation_non_dict_entries_raises():
    """ORTAM: dict-olmayan entry -> c['kind'] TypeError YAYILIR."""
    with pytest.raises(TypeError):
        _is_relaxation(["relax"])
