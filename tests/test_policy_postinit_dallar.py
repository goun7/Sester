"""Policy.__post_init__ dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (dis cagri YOK).
"""
import datetime as _dt

import pytest

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sester.policy import Policy


def _policy(**kw):
    d = {"policy_id": "p1", "per_request_max": 1.0, "daily_max": 10.0}
    d.update(kw)
    return Policy(**d)


# -- varsayilan ---------------------------------------------------------------------------------

def test_default_timezone_istanbul():
    p = _policy()
    assert p.timezone == "Europe/Istanbul"


def test_tz_attribute_set():
    p = _policy()
    assert hasattr(p, "_tz")


def test_tz_is_zoneinfo():
    assert isinstance(_policy()._tz, ZoneInfo)


def test_istanbul_tz_resolved():
    assert _policy()._tz == ZoneInfo("Europe/Istanbul")


# -- gecerli-bolgeler ---------------------------------------------------------------------------------

@pytest.mark.parametrize("tz", [
    "Europe/Istanbul", "UTC", "America/New_York", "Asia/Tokyo",
    "Europe/London", "Australia/Sydney", "Pacific/Auckland",
    "America/Los_Angeles", "Asia/Dubai", "Europe/Berlin",
])
def test_valid_timezone(tz):
    assert _policy(timezone=tz)._tz == ZoneInfo(tz)


def test_utc_timezone():
    assert _policy(timezone="UTC")._tz == ZoneInfo("UTC")


def test_custom_timezone_differs():
    a = _policy(timezone="Asia/Tokyo")._tz
    b = _policy(timezone="America/New_York")._tz
    assert a != b


# -- gecersiz-bolge ---------------------------------------------------------------------------------

# ZoneInfoNotFoundError firlatanlar (UTC'ye-dusus)
_ZONE_NOT_FOUND = ["Mars/Phobos", "Nowhere/Here", "X", "Istanbul",
                   "istanbul", "EUROPE/ISTANBUL"]


@pytest.mark.parametrize("tz", _ZONE_NOT_FOUND)
def test_invalid_timezone_falls_back_utc(tz):
    """gecersiz -> ZoneInfoNotFoundError -> UTC (fail-degil)."""
    try:
        ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        pass
    else:
        pytest.skip(f"{tz!r} gecerli (zoneinfo db)")
    p = _policy(timezone=tz)
    assert p._tz == _dt.timezone.utc


# -- URETIM-SINIRI: ValueError yakalanmiyor ---------------------------------------------------------------------------------

@pytest.mark.parametrize("tz", ["Europe/", "/Istanbul", "Europe//Istanbul",
                                   "/", ""])
def test_malformed_timezone_raises(tz):
    """BILGI: ZoneInfo ValueError firlatir (ZoneInfoNotFoundError DEGIL)
    -> __post_init__ SADECE ZoneInfoNotFoundError yakalar -> ValueError YAYILIR.
    Slash-bicimi bozuk zaman-dilimleri icin UTC-fallback YOK."""
    with pytest.raises(ValueError):
        _policy(timezone=tz)


def test_invalid_no_raise():
    assert _policy(timezone="Mars/Phobos") is not None


def test_invalid_falls_to_utc_object():
    p = _policy(timezone="ZZZ/Unknown")
    assert p._tz is _dt.timezone.utc


def test_invalid_tz_string_unchanged():
    """timezone alaninin KENDI degismez (sadece _tz fallback)."""
    p = _policy(timezone="Mars/Phobos")
    assert p.timezone == "Mars/Phobos"


def test_invalid_returns_utc_not_none():
    assert _policy(timezone="Nope/Nope")._tz is not None


# -- saat-penceresi-kullanimi ---------------------------------------------------------------------------------

def test_istanbul_offset_positive():
    """Europe/Istanbul UTC+3 (yaz/kis)."""
    p = _policy()
    now = _dt.datetime(2026, 1, 1, 12, tzinfo=p._tz)
    utc = now.astimezone(_dt.timezone.utc)
    assert utc.hour in (9, 10)  # +3 (kis) veya +3 (yaz)


def test_tokyo_offset():
    p = _policy(timezone="Asia/Tokyo")
    noon = _dt.datetime(2026, 1, 1, 12, tzinfo=p._tz)
    assert noon.astimezone(_dt.timezone.utc).hour == 3  # UTC-9


def test_new_york_offset():
    p = _policy(timezone="America/New_York")
    noon = _dt.datetime(2026, 1, 1, 12, tzinfo=p._tz)
    assert noon.astimezone(_dt.timezone.utc).hour == 17  # UTC-5 (kis)


def test_utc_zero_offset():
    p = _policy(timezone="UTC")
    noon = _dt.datetime(2026, 1, 1, 12, tzinfo=p._tz)
    assert noon.astimezone(_dt.timezone.utc).hour == 12


def test_invalid_utc_zero_offset():
    p = _policy(timezone="Mars/Phobos")
    noon = _dt.datetime(2026, 1, 1, 12, tzinfo=p._tz)
    assert noon.astimezone(_dt.timezone.utc).hour == 12


# -- dataclass-alanlari ---------------------------------------------------------------------------------

def test_policy_id():
    assert _policy(policy_id="p42").policy_id == "p42"


def test_per_request_max():
    assert _policy(per_request_max=2.5).per_request_max == 2.5


def test_daily_max():
    assert _policy(daily_max=99.0).daily_max == 99.0


def test_rules_default_empty():
    assert _policy().rules == []


def test_currency_default_usdc():
    assert _policy().currency == "USDC"


def test_rules_provided():
    r = [{"k": "v"}]
    assert _policy(rules=r).rules == r


def test_currency_custom():
    assert _policy(currency="EUR").currency == "EUR"


# -- __post_init__ cagrisi ---------------------------------------------------------------------------------

def test_post_init_runs_on_construction():
    """dataclass __post_init__ otomatik cagrilir."""
    assert _policy()._tz is not None


def test_tz_recomputed_each_time():
    a = _policy(timezone="Asia/Tokyo")
    b = _policy(timezone="Asia/Tokyo")
    assert a._tz == b._tz


def test_change_timezone_after_init_no_recompute():
    """__post_init__ sadece __init__'te calisir."""
    p = _policy(timezone="UTC")
    p.timezone = "Asia/Tokyo"
    assert p._tz == ZoneInfo("UTC")


# -- tekrar ---------------------------------------------------------------------------------

def test_repeatable():
    assert _policy()._tz == _policy()._tz


def test_independent_instances():
    a, b = _policy(), _policy()
    assert a._tz is not None and b._tz is not None


def test_two_policies_different_tz():
    a = _policy(timezone="UTC")
    b = _policy(timezone="Asia/Tokyo")
    assert a._tz != b._tz
