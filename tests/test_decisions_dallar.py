"""sester.watchfeed._decisions dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (dict bundle, dis cagri YOK).
Bundle'daki permission_decision olaylarini seq-sirali cikarir.
"""
import sys

import pytest

sys.path.insert(0, ".")
from sester.watchfeed import _decisions  # noqa: E402


def ev(ts=0.0, payload=None, event_type="permission_decision",
       agent_id="a1", host="h1"):
    return {"ts": ts, "event_type": event_type,
            "agent_id": agent_id, "host": host, "payload": payload}


# -- temel ---------------------------------------------------------------------------------

def test_empty_bundle():
    assert _decisions({}) == []


def test_no_events_key():
    assert _decisions({"other": 1}) == []


def test_empty_events():
    assert _decisions({"events": []}) == []


def test_returns_list():
    assert isinstance(_decisions({}), list)


def test_single_decision():
    b = {"events": [ev(payload='{"rule_id": "r1", "decision": "allow"}')]}
    r = _decisions(b)
    assert len(r) == 1
    assert r[0]["rule_id"] == "r1" and r[0]["decision"] == "allow"


def test_record_structure():
    b = {"events": [ev(ts=1.5, payload='{"rule_id":"r","decision":"deny"}',
                       agent_id="ag", host="ho")]}
    r = _decisions(b)[0]
    assert set(r) == {"ts", "agent", "host", "rule_id", "decision"}


def test_ts_is_float():
    assert isinstance(_decisions({"events": [ev(ts=3)]})[0]["ts"], float)


def test_agent_is_str():
    assert _decisions({"events": [ev(agent_id=42)]})[0]["agent"] == "42"


def test_host_none_becomes_str_none():
    """ORTAM: str(None) -> 'None' (bos-string DEGIL)."""
    assert _decisions({"events": [ev(host=None)]})[0]["host"] == "None"


# -- filtreleme -------------------------------------------------------------------------------

def test_other_event_skipped():
    b = {"events": [ev(event_type="other")]}
    assert _decisions(b) == []


def test_none_event_type_skipped():
    b = {"events": [ev(event_type=None)]}
    assert _decisions(b) == []


def test_case_sensitive_type():
    """'Permission_Decision' eslesmez."""
    b = {"events": [ev(event_type="Permission_Decision")]}
    assert _decisions(b) == []


def test_mixed_events_order_preserved():
    b = {"events": [
        ev(payload='{"rule_id":"r1"}'),
        ev(event_type="other"),
        ev(payload='{"rule_id":"r2"}'),
    ]}
    ids = [x["rule_id"] for x in _decisions(b)]
    assert ids == ["r1", "r2"]


def test_seq_order_preserved():
    b = {"events": [ev(ts=i, payload=f'{{"rule_id":"r{i}"}}')
                    for i in range(5)]}
    assert [x["ts"] for x in _decisions(b)] == [0.0, 1.0, 2.0, 3.0, 4.0]


# -- payload -------------------------------------------------------------------------------

def test_missing_payload():
    """payload None -> '{}' -> defaults."""
    r = _decisions({"events": [ev(payload=None)]})[0]
    assert r["rule_id"] == "unknown" and r["decision"] == "unknown"


def test_empty_payload_string():
    r = _decisions({"events": [ev(payload="")]})[0]
    assert r["rule_id"] == "unknown"


def test_invalid_json_payload():
    """JSONDecodeError -> p={}."""
    r = _decisions({"events": [ev(payload="not-json")]})[0]
    assert r["rule_id"] == "unknown" and r["decision"] == "unknown"


def test_partial_payload():
    r = _decisions({"events": [ev(payload='{"rule_id":"r1"}')]})[0]
    assert r["rule_id"] == "r1" and r["decision"] == "unknown"


def test_payload_not_string():
    """payload dict -> TypeError -> p={}."""
    r = _decisions({"events": [ev(payload={"rule_id": "r1"})]})[0]
    assert r["rule_id"] == "unknown"


def test_payload_extra_fields_ignored():
    r = _decisions({"events": [ev(
        payload='{"rule_id":"r1","decision":"allow","extra":"x"}')]})[0]
    assert "extra" not in r


def test_payload_types_coerced():
    r = _decisions({"events": [ev(
        payload='{"rule_id": 42, "decision": true}')]})[0]
    assert r["rule_id"] == "42" and r["decision"] == "True"


def test_nested_payload():
    r = _decisions({"events": [ev(
        payload='{"rule_id":{"a":1},"decision":[1]}')]})[0]
    assert r["rule_id"] == "{'a': 1}"


def test_payload_null_json_raises():
    """ORTAM: json.loads('null')=None -> None.get -> AttributeError YAYILIR."""
    with pytest.raises(AttributeError):
        _decisions({"events": [ev(payload="null")]})


def test_payload_number_raises():
    """ORTAM: json.loads('5')=5 -> int.get -> AttributeError YAYILIR."""
    with pytest.raises(AttributeError):
        _decisions({"events": [ev(payload="5")]})


# -- defaults -------------------------------------------------------------------------------

def test_missing_event_fields():
    """event_type var ama ts/agent/host YOK -> defaults."""
    b = {"events": [{"event_type": "permission_decision"}]}
    r = _decisions(b)[0]
    assert r["ts"] == 0.0 and r["agent"] == "" and r["host"] == ""


def test_ts_negative():
    r = _decisions({"events": [ev(ts=-1)]})[0]
    assert r["ts"] == -1.0


def test_ts_string_coerced():
    """ORTAM: float('5') OK (str ts kabul)."""
    r = _decisions({"events": [ev(ts="5")]})[0]
    assert r["ts"] == 5.0


def test_no_payload_key():
    """payload anahtar yoksa -> e.get('payload') None -> '{}'."""
    b = {"events": [{"event_type": "permission_decision", "ts": 1}]}
    assert _decisions(b)[0]["rule_id"] == "unknown"


# -- unicode -------------------------------------------------------------------------------

def test_turkish_payload():
    r = _decisions({"events": [ev(
        payload='{"rule_id":"kural-1","decision":"izinli"}')]})[0]
    assert r["rule_id"] == "kural-1"


def test_turkish_agent_host():
    b = {"events": [ev(agent_id="Gökhan", host="İstanbul",
                       payload='{"rule_id":"r"}')]}
    r = _decisions(b)[0]
    assert r["agent"] == "Gökhan" and r["host"] == "İstanbul"


def test_emoji_payload():
    r = _decisions({"events": [ev(
        payload='{"rule_id":"😀","decision":"allow"}')]})[0]
    assert r["rule_id"] == "😀"


# -- cesitli -------------------------------------------------------------------------------

def test_many_events():
    b = {"events": [ev(payload=f'{{"rule_id":"r{i}"}}') for i in range(100)]}
    assert len(_decisions(b)) == 100


def test_repeatable():
    b = {"events": [ev(payload='{"rule_id":"r1"}')]}
    assert _decisions(b) == _decisions(b)


def test_independent():
    b = {"events": [ev(payload='{"rule_id":"r1"}')]}
    assert _decisions(b) == _decisions({"events": list(b["events"])})


def test_input_not_mutated():
    b = {"events": [ev(payload='{"rule_id":"r1"}')]}
    before = str(b)
    _decisions(b)
    assert str(b) == before


def test_all_decisions_found():
    b = {"events": [ev(payload=f'{{"rule_id":"r{i}","decision":"d{i}"}}')
                    for i in range(3)]}
    r = _decisions(b)
    assert [x["decision"] for x in r] == ["d0", "d1", "d2"]


@pytest.mark.parametrize("n", [0, 1, 2, 5, 10])
def test_counts(n):
    b = {"events": [ev(payload='{}') for _ in range(n)]}
    assert len(_decisions(b)) == n


@pytest.mark.parametrize("dec", ["allow", "deny", "unknown", "audit", ""])
def test_decision_values(dec):
    b = {"events": [ev(payload=f'{{"decision":"{dec}"}}')]}
    assert _decisions(b)[0]["decision"] == dec
