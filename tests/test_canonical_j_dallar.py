"""sester.evidence._canonical + sester.watchfeed._j dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (str-join/json saf, dis cagri YOK).
(1) _canonical: 7-alan '|' ile birlestirilmis kanonik proof-hammetni;
(2) _j: K0 kanonik JSON satir-formati (sort_keys + compact + ensure_ascii=False).
"""
import json

import pytest

from sester.evidence import _canonical
from sester.watchfeed import _j


# == _canonical =================================================================================

BASE = {"ts": 1234567890.123456, "event_type": "evt", "agent_id": "ag",
        "host": "h", "amount": 1.5, "payload": "p"}


def canon(**over):
    d = dict(BASE)
    d.update(over)
    return d


def test_canonical_returns_str():
    assert isinstance(_canonical(BASE, "prev"), str)


def test_canonical_exact_format():
    """ORTAM-ANATOMI: 'ts|event_type|agent_id|host|amount|payload|prev_proof'."""
    assert _canonical(BASE, "prev") == "1234567890.123456|evt|ag|h|1.500000|p|prev"


def test_canonical_has_7_fields_6_separators():
    assert _canonical(BASE, "prev").count("|") == 6


@pytest.mark.parametrize("ts,ts_out", [
    (0, "0.000000"), (100, "100.000000"), (-1.5, "-1.500000"),
    (1e-7, "0.000000"), (1e7, "10000000.000000"),
    ("150.0", "150.000000"), ("0", "0.000000"), (" 3 ", "3.000000"),
])
def test_canonical_ts_float_format(ts, ts_out):
    """ORTAM: float(ts):.6f — int/str/negative hepsi 6-ondalik."""
    assert _canonical(canon(ts=ts), "x").split("|")[0] == ts_out


@pytest.mark.parametrize("amount,out", [
    (0, "0.000000"), (2, "2.000000"), (-2.5, "-2.500000"), (1e-7, "0.000000"),
    (1234.567891, "1234.567891"), ("3.0", "3.000000"),
])
def test_canonical_amount_float_format(amount, out):
    assert _canonical(canon(amount=amount), "x").split("|")[4] == out


def test_canonical_ts_1e7_collides_with_0():
    """ORTAM-OGRENDI: 6-ondalik sinir — 1e-7 ile 0 AYNI kanonik (0.000000)."""
    assert _canonical(canon(ts=1e-7), "x").split("|")[0] == \
           _canonical(canon(ts=0), "x").split("|")[0]


def test_canonical_amount_1e7_collides_with_0():
    assert _canonical(canon(amount=1e-7), "x").split("|")[4] == \
           _canonical(canon(amount=0), "x").split("|")[4]


@pytest.mark.parametrize("et", ["evt", "", "TÜRKÇE", "😀", "x" * 50, "PERMISSION_DECISION"])
def test_canonical_event_type_verbatim(et):
    """ORTAM: event_type ham-karakter olarak YERLESIR (escape YOK)."""
    assert _canonical(canon(event_type=et), "x").split("|")[1] == et


def test_canonical_event_type_pipe_quirk():
    """ORTAM-OGRENDI: '|' escape EDILMEZ — 'a|b' split("|")[1]=='a' verir
    (quirk test_canonical_pipe_collision'da dokumante)."""
    assert _canonical(canon(event_type="a|b"), "x").split("|")[1] == "a"


@pytest.mark.parametrize("agent", ["ag", "", "0xabc…", "节点-1"])
def test_canonical_agent_verbatim(agent):
    assert _canonical(canon(agent_id=agent), "x").split("|")[2] == agent


@pytest.mark.parametrize("host", ["h", "", "node-1.example", "主機"])
def test_canonical_host_verbatim(host):
    assert _canonical(canon(host=host), "x").split("|")[3] == host


@pytest.mark.parametrize("payload", ["p", "", '{"k":"v"}', "ü", "x" * 100])
def test_canonical_payload_verbatim(payload):
    assert _canonical(canon(payload=payload), "x").split("|")[5] == payload


@pytest.mark.parametrize("prev", ["", "prev", "0" * 64, " genesis "])
def test_canonical_prev_proof_verbatim(prev):
    """ORTAM: prev_proof 7. alana ham-yerlesir (len-coerce YOK)."""
    assert _canonical(BASE, prev).split("|")[6] == prev


@pytest.mark.parametrize("field", ["event_type", "agent_id", "host", "payload"])
def test_canonical_pipe_in_field_not_escaped(field):
    """ORTAM: herhangi bir alanda '|' ham-yazilir (escape YOK)."""
    assert "|" in _canonical(canon(**{field: "a|b"}), "x")


def test_canonical_pipe_collision():
    """KRIPTEGRAFIK-QUIRK DOKUMANTE: '|' ESCAPE EDILMEZ — event_type='a|b'+agent='c'
    ile event_type='a'+agent='b|c' AYNI kanonik (ayni concat)."""
    left = _canonical(canon(event_type="a|b", agent_id="c"), "x")
    right = _canonical(canon(event_type="a", agent_id="b|c"), "x")
    assert left == right


def test_canonical_collision_multi_field():
    """Ortak: agent='a|b' + host='c' == agent='a' + host='b|c'."""
    l = _canonical(canon(agent_id="a|b", host="c"), "x")
    r = _canonical(canon(agent_id="a", host="b|c"), "x")
    assert l == r


@pytest.mark.parametrize("k", ["ts", "event_type", "agent_id", "host", "amount", "payload"])
def test_canonical_missing_key_raises_keyerror(k):
    """ORTAM: 6 zorunlu alanin herhangi biri EKSIK -> KeyError."""
    d = dict(BASE)
    del d[k]
    with pytest.raises(KeyError):
        _canonical(d, "x")


@pytest.mark.parametrize("bad", ["abc", "not-a-number", "", "1,2"])
def test_canonical_bad_ts_string_raises(bad):
    """ORTAM: float('abc') ValueError YAYILIR (except YOK)."""
    with pytest.raises(ValueError):
        _canonical(canon(ts=bad), "x")


@pytest.mark.parametrize("bad", ["abc", ""])
def test_canonical_bad_amount_string_raises(bad):
    with pytest.raises(ValueError):
        _canonical(canon(amount=bad), "x")


def test_canonical_ts_none_raises():
    with pytest.raises(TypeError):
        _canonical(canon(ts=None), "x")


def test_canonical_amount_none_raises():
    with pytest.raises(TypeError):
        _canonical(canon(amount=None), "x")


def test_canonical_ts_bool():
    """ORTAM: bool float-coerce True->1.0."""
    assert _canonical(canon(ts=True), "x").split("|")[0] == "1.000000"


def test_canonical_all_empty_strings():
    """ORTAM: event_type/agent/host/payload '' -> '0.000000||||0.000000||'."""
    assert _canonical(canon(ts=0, event_type="", agent_id="", host="",
                            amount=0, payload=""), "") == "0.000000||||0.000000||"


def test_canonical_deterministic():
    assert _canonical(BASE, "p") == _canonical(BASE, "p")


def test_canonical_prev_change_changes_output():
    assert _canonical(BASE, "a") != _canonical(BASE, "b")


def test_canonical_input_not_mutated():
    import copy
    before = copy.deepcopy(BASE)
    _canonical(BASE, "x")
    assert BASE == before


@pytest.mark.parametrize("floaty", [1.5, 2.25, 100.125])
def test_canonical_roundtrip_fields(floaty):
    out = _canonical(canon(ts=floaty, amount=floaty), "x")
    parts = out.split("|")
    assert float(parts[0]) == floaty
    assert float(parts[4]) == floaty


# == _j =========================================================================================

def test_j_returns_str():
    assert isinstance(_j({"a": 1}), str)


@pytest.mark.parametrize("obj,expected", [
    ({}, "{}"),
    ({"a": 1}, '{"a":1}'),
    ({"b": 1, "a": 2}, '{"a":2,"b":1}'),
    ({"z": 1, "y": 2, "x": 3}, '{"x":3,"y":2,"z":1}'),
])
def test_j_sorted_keys(obj, expected):
    """ORTAM-ANATOMI: sort_keys=True — anahtarlar ALFABETIK."""
    assert _j(obj) == expected


def test_j_compact_separators():
    """ORTAM: separators=(',',':') — bosluk YOK."""
    out = _j({"a": 1, "b": [1, 2, 3]})
    assert " " not in out
    assert out == '{"a":1,"b":[1,2,3]}'


@pytest.mark.parametrize("text", ["merhaba", "ğüşiöç", "😀", "日本語"])
def test_j_ensure_ascii_false(text):
    """ORTAM: ensure_ascii=False — unicode RAW (escape YOK)."""
    assert _j({"k": text}) == '{"k":"' + text + '"}'
    assert text in _j({"k": text})


def test_j_newline_escaped_by_json():
    """ORTAM-OGRENDI: 'a\\nb' json-dumps'ta '\\\\n' escape eder (ensure_ascii=False
    SADECE non-ascii'yi etkiler, kontrol-karakterleri hala escape)."""
    out = _j({"k": "a\nb"})
    assert out == '{"k":"a\\nb"}'
    assert "a\nb" not in out
    assert json.loads(out) == {"k": "a\nb"}


@pytest.mark.parametrize("cc", ["\t", "\r", "\x00", "\b"])
def test_j_control_chars_escaped(cc):
    """ORTAM: kontrol-karakterleri json-escape (raw YAZILMAZ)."""
    out = _j({"k": "a" + cc + "b"})
    assert json.loads(out) == {"k": "a" + cc + "b"}
    assert cc not in out or cc == "\x00"


def test_j_json_loadable():
    obj = {"b": 2, "a": [1, 2], "c": {"z": 1, "y": 2}}
    assert json.loads(_j(obj)) == obj


def test_j_nested_sorted():
    assert _j({"o": {"z": 1, "a": 2}}) == '{"o":{"a":2,"z":1}}'


def test_j_list_order_preserved():
    """ORTAM: liste-sirasi KORUNUR (sadece dict anahtarlari siralanir)."""
    assert _j({"l": [3, 1, 2]}) == '{"l":[3,1,2]}'


@pytest.mark.parametrize("v", [None, True, False, 1.5, 0, -1, 1e10, "str"])
def test_j_value_types(v):
    assert json.loads(_j({"k": v})) == {"k": v}


def test_j_deterministic():
    assert _j({"b": 1, "a": 2}) == _j({"a": 2, "b": 1})


@pytest.mark.parametrize("a,b", [({"a": 1}, {"a": 2}), ({"a": 1}, {"b": 1}), ({}, {"a": 1})])
def test_j_different_objs_differ(a, b):
    assert _j(a) != _j(b)


def test_j_deeply_nested():
    obj = {"a": {"b": {"c": {"d": {"e": [1, {"f": "g"}]}}}}}
    assert json.loads(_j(obj)) == obj


def test_j_empty_list_and_dict():
    assert _j({"l": [], "d": {}}) == '{"d":{},"l":[]}'


def test_j_turkce_emoji_mixed():
    obj = {"şehir": "İstanbul", "emoji": "🚀", "sayı": 42}
    out = _j(obj)
    assert json.loads(out) == obj
    assert "İstanbul" in out and "🚀" in out


def test_j_input_not_mutated():
    obj = {"b": 1, "a": 2}
    _j(obj)
    assert obj == {"b": 1, "a": 2}


def test_j_large_object():
    obj = {f"key_{i:04d}": i for i in range(200)}
    out = _j(obj)
    assert json.loads(out) == obj
    assert out.index('"key_0000"') < out.index('"key_0199"')


def test_j_special_chars_in_keys():
    obj = {"a|b": 1, 'a"b': 2, "a:b": 3}
    assert json.loads(_j(obj)) == obj
