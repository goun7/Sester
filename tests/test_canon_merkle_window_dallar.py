"""63-Sester policy_signed._hms/_window/_is_relaxation + evidence._canonical/_merkle dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (saf fonksiyonlar; network/DB YASAK).

ORTAM-ANATOMI:
- _hms(s): int(s[:2])*60 + int(s[3:]) — 'HH:MM' -> dakika
- _window(hb): (end-start) % 1440 or 1440 — gece-boyu dahil, 0 -> 1440
- _is_relaxation(changes): any(c['kind']=='relax')
- _canonical(ev, prev_proof): '|'.join([f'{ts:.6f}', event_type, agent_id,
  host, f'{amount:.6f}', payload, prev_proof])
- _merkle(leaves): bos -> GENESIS('0'*64); tek-yapraza kadar ciftleri
  sha256(a+b) ile katla; tek-yaprak son-leaf'i dup-like eder
"""
import hashlib
import sys

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "src")
from sester.evidence import GENESIS, _canonical, _merkle  # noqa: E402
from sester.policy_signed import _hms, _is_relaxation, _window  # noqa: E402


# == _hms ==============================================================================================

def test_hms_gece_yarisi():
    assert _hms("00:00") == 0


def test_hms_bir_saat():
    assert _hms("01:00") == 60


def test_hms_dakika():
    assert _hms("00:30") == 30


def test_hms_oglen():
    """ORTAM: 12:30 -> 12*60+30 = 750."""
    assert _hms("12:30") == 750


def test_hms_gece():
    assert _hms("23:59") == 1439


def test_hms_max():
    """ORTAM: 23:59 = 1439 (1440 = 24h dongusu)."""
    assert _hms("23:59") == 1439


def test_hms_donut_tipi():
    assert isinstance(_hms("01:00"), int)


def test_hms_stabil():
    assert _hms("12:30") == _hms("12:30")


def test_hms_dusuk_sifir():
    """ORTAM: '09:05' -> 9*60+5 = 545 (leading-sifir)."""
    assert _hms("09:05") == 545


@pytest.mark.parametrize("s,b", [
    ("00:00", 0), ("00:01", 1), ("01:00", 60), ("00:30", 30),
    ("09:05", 545), ("12:30", 750), ("23:59", 1439),
])
def test_hms_matrix(s, b):
    assert _hms(s) == b


# == _window ===========================================================================================

def test_window_bir_saat():
    """ORTAM: ['01:00','02:00'] -> (120-60)%1440 = 60."""
    assert _window(["01:00", "02:00"]) == 60


def test_window_yirmidort_saat():
    """ORTAM-OGRENDI: tam-gun -> (0-0)%1440 = 0 -> 'or 1440' -> 1440!"""
    assert _window(["00:00", "00:00"]) == 1440


def test_window_gece_boyu():
    """ORTAM: ['22:00','06:00'] -> (360-1320)%1440 = -960%1440 = 480
    (MODULO ile gece-boyu dogru hesaplanir)."""
    assert _window(["22:00", "06:00"]) == 480


def test_window_gece_boyu2():
    """ORTAM: ['23:00','05:00'] -> (300-1380)%1440 = -1080%1440 = 360."""
    assert _window(["23:00", "05:00"]) == 360


def test_window_sifir_sonuc_yok():
    """ORTAM-OGRENDI: (end-start)%1440 == 0 -> 1440 (0 pencere = tam-gun).
    Sadece tam-gun-ayni-saat 0 uretir."""
    assert _window(["12:00", "12:00"]) == 1440


def test_window_uzun_saatler():
    """ORTAM: ['00:00','23:59'] -> 1439."""
    assert _window(["00:00", "23:59"]) == 1439


def test_window_donut_tipi():
    assert isinstance(_window(["01:00", "02:00"]), int)


def test_window_stabil():
    assert _window(["22:00", "06:00"]) == _window(["22:00", "06:00"])


def test_window_eksik_eleman_hata():
    """ORTAM: hb[1] yok -> IndexError."""
    with pytest.raises(IndexError):
        _window(["01:00"])


def test_window_bos_hata():
    with pytest.raises(IndexError):
        _window([])


@pytest.mark.parametrize("hb,b", [
    (["00:00", "00:00"], 1440), (["00:00", "01:00"], 60), (["01:00", "02:00"], 60),
    (["00:00", "00:30"], 30), (["00:00", "23:59"], 1439),
    (["22:00", "06:00"], 480), (["23:00", "05:00"], 360), (["12:00", "12:00"], 1440),
])
def test_window_matrix(hb, b):
    assert _window(hb) == b


# == _is_relaxation ===================================================================================

def test_relax_bos():
    """ORTAM: bos liste -> any() -> False."""
    assert _is_relaxation([]) is False


def test_relax_var():
    """ORTAM: kind=='relax' var -> True."""
    assert _is_relaxation([{"kind": "relax"}]) is True


def test_relax_yok():
    assert _is_relaxation([{"kind": "tighten"}]) is False


def test_relax_arada():
    """ORTAM: arada olsa True (any)."""
    assert _is_relaxation([{"kind": "tighten"}, {"kind": "relax"}]) is True


def test_relax_sadece_sonda():
    assert _is_relaxation([{"kind": "x"}, {"kind": "relax"}]) is True


def test_relax_donut_tipi():
    assert isinstance(_is_relaxation([]), bool)


def test_relax_case_sensitive():
    """ORTAM-OGRENDI: case-SENSITIVE — 'Relax' != 'relax' -> False!"""
    assert _is_relaxation([{"kind": "Relax"}]) is False
    assert _is_relaxation([{"kind": "RELAX"}]) is False


def test_relax_diger_anahtar():
    """ORTAM: 'kind' anahtari yok -> KeyError."""
    with pytest.raises(KeyError):
        _is_relaxation([{"type": "relax"}])


def test_relax_birden_cok():
    assert _is_relaxation([{"kind": "relax"}, {"kind": "relax"}]) is True


@pytest.mark.parametrize("changes,b", [
    ([], False), ([{"kind": "relax"}], True), ([{"kind": "tighten"}], False),
    ([{"kind": "tighten"}, {"kind": "relax"}], True),
    ([{"kind": "x"}, {"kind": "y"}], False),
])
def test_relax_matrix(changes, b):
    assert _is_relaxation(changes) is b


# == _canonical =======================================================================================

EV = {
    "ts": 1000.5, "event_type": "pay", "agent_id": "A1",
    "host": "H1", "amount": 5.25, "payload": "P1",
}


def test_canonical_beklenen():
    """ORTAM: tam preimage birebir."""
    out = _canonical(EV, "prev")
    assert out == "1000.500000|pay|A1|H1|5.250000|P1|prev"


def test_canonical_ayrac():
    """ORTAM: '|' ayrici (7 alan = 6 ayrac)."""
    assert _canonical(EV, "prev").count("|") == 6


def test_canonical_ts_alti_basamak():
    """ORTAM: f'{ts:.6f}' — TAM 6 ondalik."""
    assert _canonical(EV, "p").split("|")[0] == "1000.500000"


def test_canonical_amount_alti_basamak():
    assert _canonical(EV, "p").split("|")[4] == "5.250000"


def test_canonical_ts_int():
    """ORTAM: float(ts) cast — int ts -> '.000000'."""
    ev = dict(EV, ts=1000)
    assert _canonical(ev, "p").split("|")[0] == "1000.000000"


def test_canonical_ts_eksik_anahtar_hata():
    """ORTAM: 'ts' yok -> KeyError."""
    ev = {k: v for k, v in EV.items() if k != "ts"}
    with pytest.raises(KeyError):
        _canonical(ev, "p")


def test_canonical_amount_eksik_hata():
    ev = {k: v for k, v in EV.items() if k != "amount"}
    with pytest.raises(KeyError):
        _canonical(ev, "p")


def test_canonical_donut_tipi():
    assert isinstance(_canonical(EV, "p"), str)


def test_canonical_stabil():
    assert _canonical(EV, "p") == _canonical(EV, "p")


def test_canonical_prev_degisir():
    """ORTAM: prev_proof hash'e girer (chain-link)."""
    assert _canonical(EV, "p1") != _canonical(EV, "p2")


def test_canonical_payload_degisir():
    ev = dict(EV, payload="P2")
    assert _canonical(ev, "p") != _canonical(EV, "p")


def test_canonical_float_str():
    """ORTAM-OGRENDI: float() cast — numeric STR KABUL ('5.25' -> 5.25)."""
    ev = dict(EV, amount="5.25")
    assert _canonical(ev, "p").split("|")[4] == "5.250000"


def test_canonical_float_gecersiz_hata():
    """ORTAM: float('abc') -> ValueError."""
    ev = dict(EV, amount="abc")
    with pytest.raises(ValueError):
        _canonical(ev, "p")


def test_canonical_ondalik_yuvarlama():
    """ORTAM-OGRENDI: .6f YUVARLAMA — 5.123456789 -> '5.123457'."""
    ev = dict(EV, amount=5.123456789)
    assert _canonical(ev, "p").split("|")[4] == "5.123457"


@pytest.mark.parametrize("ts,amount", [
    (0, 0), (1000, 5.25), (0.000001, 0.000001), (999999.999999, 1.0),
])
def test_canonical_matrix(ts, amount):
    ev = dict(EV, ts=ts, amount=amount)
    out = _canonical(ev, "p")
    assert len(out.split("|")) == 7


# == _merkle ==========================================================================================

def test_merkle_bos_genesis():
    """ORTAM: bos leaves -> GENESIS = '0'*64."""
    assert _merkle([]) == GENESIS


def test_merkle_genesis_degeri():
    assert GENESIS == "0" * 64


def test_merkle_tek_yaprak():
    """ORTAM: tek yaprak -> while 1>1 false -> layer[0] = yapragin kendisi
    (HASHLENMEZ, oldugu gibi doner!)."""
    assert _merkle(["abc"]) == "abc"


def test_merkle_tek_yaprak_kendisi():
    """ORTAM-OGRENDI: tek-yaprak RAW doner — sha256 UYGULANMAZ!
    produce_bundle'da leaf'ler zaten proof_hash ciktisi (hexdigest)."""
    ham = hashlib.sha256(b"x").hexdigest()
    assert _merkle([ham]) == ham


def test_merkle_iki_yaprak():
    """ORTAM: 2 yaprak -> sha256(a+b)."""
    beklenen = hashlib.sha256(("a" + "b").encode()).hexdigest()
    assert _merkle(["a", "b"]) == beklenen


def test_merkle_uc_yaprak_dup():
    """ORTAM-OGRENDI: 3 yaprak -> TEK-yaprak (layer[-1] append edilir)
    -> 4 yaprak -> 2 -> 1. Son katmanda cift-katlik saglanir."""
    layer = ["a", "b", "c", "c"]
    h1 = hashlib.sha256(("a" + "b").encode()).hexdigest()
    h2 = hashlib.sha256(("c" + "c").encode()).hexdigest()
    beklenen = hashlib.sha256((h1 + h2).encode()).hexdigest()
    assert _merkle(["a", "b", "c"]) == beklenen


def test_merkle_dort_yaprak():
    h1 = hashlib.sha256(("a" + "b").encode()).hexdigest()
    h2 = hashlib.sha256(("c" + "d").encode()).hexdigest()
    beklenen = hashlib.sha256((h1 + h2).encode()).hexdigest()
    assert _merkle(["a", "b", "c", "d"]) == beklenen


def test_merkle_bes_yaprak():
    """ORTAM: 5 -> 6 (e dup) -> 3 (c? hayir 6 cift) -> 3 -> 4 (dup) -> 2 -> 1."""
    out = _merkle(["a", "b", "c", "d", "e"])
    assert isinstance(out, str) and len(out) == 64


def test_merkle_donut_tipi():
    assert isinstance(_merkle(["a"]), str)


def test_merkle_stabil():
    assert _merkle(["a", "b"]) == _merkle(["a", "b"])


def test_merkle_sira_onemli():
    """ORTAM: (a+b) sirali -> 'a','b' != 'b','a'."""
    assert _merkle(["a", "b"]) != _merkle(["b", "a"])


def test_merkle_tekrar_kisa():
    """ORTAM: ayni yapraklar ayni kok."""
    assert _merkle(["x", "y"]) == _merkle(["x", "y"])


def test_merkle_cift_sayi_derinlik():
    """ORTAM: 4 yaprak -> 2 katman (4->2->1)."""
    assert len(_merkle(["a", "b", "c", "d"])) == 64


@pytest.mark.parametrize("leaves", [
    [], ["a"], ["a", "b"], ["a", "b", "c"], ["a", "b", "c", "d"],
    ["a", "b", "c", "d", "e"], list("abcdefgh"),
])
def test_merkle_matrix(leaves):
    out = _merkle(leaves)
    if not leaves:
        assert out == GENESIS
    elif len(leaves) == 1:
        assert out == leaves[0]
    else:
        assert len(out) == 64


# == karakterizasyon ===================================================================================

def test_window_amaci():
    """ORTAM-OGRENDI (DOCSTACK): hour_between penceresi dakika-uzunlugu —
    gece-boyu (orn. 22:00->06:00) NEGATIF cikarim yerine %1440 MODULO ile
    dogru 480 dk hesaplanir; tam-gun ayni-saat 0 degil 1440 dk sayilir
    ('or 1440'). Bu policy pencerelerini dongusel-zaman-guvenli yapar."""
    assert _window(["22:00", "06:00"]) == 480
    assert _window(["12:00", "12:00"]) == 1440


def test_is_relaxation_amaci():
    """ORTAM-OGRENDI: policy-degisiklik sınıflandırması — 'relax' kind'li
    degisiklik varsa politika GEVSEME sayilir. any() ile liste-tara;
    case-SENSITIVE whitelist ('Relax' gevseme DEGIL)."""
    assert _is_relaxation([{"kind": "relax"}]) is True
    assert _is_relaxation([{"kind": "Relax"}]) is False


def test_canonical_amaci():
    """ORTAM-OGRENDI: event kanonizasyonu — ALAN SIRASI SABIT (ts,
    event_type, agent_id, host, amount, payload, prev_proof) ve ts/amount
    .6f ile TAM 6 ondalik: kayan-nokta temsil farklari (1.5 vs 1.5000001)
    ayni kanona cikar (deterministik hash)."""
    a = _canonical(dict(EV, ts=1000.5), "p")
    b = _canonical(dict(EV, ts=1000.5000001), "p")
    assert a == b


def test_merkle_amaci():
    """ORTAM-OGRENDI (DOCSTACK): Merkle — ciftler sha256(a+b); TEK-yaprak
    kalirsa SON leaf kopyalanir (cift-katliq); bos ledger GENESIS='0'*64.
    Kok, herhangi bir yaprak degisince degisir (tampering detection).
    Tek-yaprak RAW doner cunku leaf'ler zaten hexdigest."""
    assert _merkle([]) == "0" * 64
    assert _merkle(["a", "b", "c"]) != _merkle(["a", "b", "X"])
