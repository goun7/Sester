"""sester.bridges._claim_id + _payload_counts dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (sha256/json saf, dis cagri YOK).
(1) _claim_id: sha256(task_id|summary|reproducible)[:16];
(2) _payload_counts: bundle event'lerini parse-ederek (quota/replay/receipt) sayar.
"""
import hashlib
import json

import pytest

from sester.bridges import _claim_id, _payload_counts


# == _claim_id ==================================================================================

def ref_claim(task_id: str, summary: str) -> str:
    """Referans formul — uretimden BAGIMSIZ dogruluk."""
    return hashlib.sha256(f"{task_id}|{summary}|reproducible".encode()).hexdigest()[:16]


@pytest.mark.parametrize("task_id,summary", [
    ("t1", "s1"), ("", ""), ("t", ""), ("", "s"),
    ("task-123", "ozet"), ("T1", "S1"),
    ("görev-1", "özet-1"), ("😀", "emoji"),
    ("a" * 200, "b" * 200),
    ("2026-10-08T12:00:00Z", "deploy yapıldı"),
])
def test_claim_id_matches_reference(task_id, summary):
    """ORTAM-ANATOMI: sha256(f'{task_id}|{summary}|reproducible')[:16]."""
    assert _claim_id(task_id, summary) == ref_claim(task_id, summary)


def test_claim_id_length_is_16():
    assert len(_claim_id("x", "y")) == 16


def test_claim_id_is_hex():
    cid = _claim_id("x", "y")
    int(cid, 16)
    assert all(c in "0123456789abcdef" for c in cid)


@pytest.mark.parametrize("task_id,summary", [
    ("t1", "s1"), ("", ""), ("görev", "özet"), ("a" * 100, "b" * 100),
])
def test_claim_id_deterministic(task_id, summary):
    assert _claim_id(task_id, summary) == _claim_id(task_id, summary)


@pytest.mark.parametrize("a,b", [
    (("t1", "s1"), ("t1", "s2")),
    (("t1", "s1"), ("t2", "s1")),
    (("t1", "s1"), ("", "")),
    (("t", ""), ("", "t")),
])
def test_claim_id_different_inputs_differ(a, b):
    assert _claim_id(*a) != _claim_id(*b)


def test_claim_id_order_matters():
    """task_id ve summary yer-degisince baska deger."""
    assert _claim_id("aa", "bb") != _claim_id("bb", "aa")


@pytest.mark.parametrize("char", ["|", "reproducible", "\x00", "\n", "🚀"])
def test_claim_id_special_chars_in_summary(char):
    """ORTAM: separator '|' summary icinde olsa DAHA UZUN hash — cakisma quirk:
    ('a|b','c') ile ('a','b|c') ayni formul-acigi (ayni concat-string)."""
    s = f"x{char}y"
    assert _claim_id("t", s) == ref_claim("t", s)


@pytest.mark.parametrize("task_id,summary", [
    ("t1", "s1"), ("görev", "özet"), ("", "x"),
])
def test_claim_id_collision_documented(task_id, summary):
    """KRIPTEGRAFIK-QUIRK DOKUMANTE: '|' escape EDILMEZ — (task,summary) cifti
    concat belirsiz; ('a|b','c') == ('a','b|c') ayni claim-id uretir."""
    left = _claim_id("a|b", "c")
    right = _claim_id("a", "b|c")
    assert left == right
    assert left == ref_claim("a|b", "c")


def test_claim_id_unicode_bytes_utf8():
    """ORTAM: encode() varsayilan utf-8."""
    assert _claim_id("ğ", "ş") == hashlib.sha256("ğ|ş|reproducible".encode()).hexdigest()[:16]


def test_claim_id_returns_str():
    assert isinstance(_claim_id("t", "s"), str)


# == _payload_counts ===========================================================================

def ev(event_type=None, payload=...):
    """Tek event insa eder — payload ESKSIK olursa alan YOK."""
    d = {}
    if event_type is not None:
        d["event_type"] = event_type
    if payload is not ...:
        d["payload"] = payload
    return d


def deny(rule_id):
    return json.dumps({"decision": "deny", "rule_id": rule_id})


@pytest.mark.parametrize("bundle", [
    {}, {"events": []}, {"x": 1}, {"events": {}},
])
def test_payload_counts_empty_bundle_zero(bundle):
    """ORTAM: events-anahtari YOKSA/empty-dict -> (0,0,0) — .get('events',[]) guvenli."""
    assert _payload_counts(bundle) == (0, 0, 0)


def test_payload_counts_events_none_raises():
    """ORTAM-OGRENDI: events=None -> for None -> TypeError YAYILIR (None guard YOK)."""
    with pytest.raises(TypeError):
        _payload_counts({"events": None})


def test_payload_counts_events_str_raises():
    """ORTAM-OGRENDI: events=str -> str.get YOK -> AttributeError YAYILIR."""
    with pytest.raises(AttributeError):
        _payload_counts({"events": "string"})


def test_payload_counts_returns_tuple_of_3_int():
    r = _payload_counts({"events": []})
    assert isinstance(r, tuple) and len(r) == 3
    assert all(isinstance(x, int) for x in r)


@pytest.mark.parametrize("n", [1, 2, 3, 5, 10, 100])
def test_payload_counts_receipts(n):
    """ORTAM: event_type=='charge_receipt' -> receipts sayaci; continue (alt-dallar atlanir)."""
    assert _payload_counts({"events": [ev("charge_receipt")] * n}) == (0, 0, n)


@pytest.mark.parametrize("rule,count_idx", [
    ("quota_exceeded", 0), ("replay", 1),
])
def test_payload_counts_deny_rules(rule, count_idx):
    """ORTAM: decision=deny + rule_id -> ilgili sayac."""
    r = _payload_counts({"events": [ev("permission_decision", deny(rule))]})
    expected = [0, 0, 0]
    expected[count_idx] = 1
    assert r == tuple(expected)


@pytest.mark.parametrize("rule", ["other", "quota", "", "QUOTA_EXCEEDED", "replay2"])
def test_payload_counts_unknown_rule_counted_neither(rule):
    """ORTAM: bilinmeyen rule_id -> ne quota ne replay (elif zinciri)."""
    assert _payload_counts({"events": [ev("permission_decision", deny(rule))]}) == (0, 0, 0)


@pytest.mark.parametrize("decision", ["allow", "Allow", "DENY", "deny ", "", "1"])
def test_payload_counts_non_deny_ignored(decision):
    """ORTAM: SADECE decision=='deny' (case-sensitive, tam-eslesme)."""
    p = json.dumps({"decision": decision, "rule_id": "quota_exceeded"})
    assert _payload_counts({"events": [ev("permission_decision", p)]}) == (0, 0, 0)


@pytest.mark.parametrize("payload", [None, "", "   ", "not-json", "{", "[1,2"])
def test_payload_counts_bad_payload_skipped(payload):
    """ORTAM: payload None/empty/invalid-json -> except (JSONDecodeError,TypeError)
    yakalanir, event ATLANIR -> (0,0,0)."""
    assert _payload_counts({"events": [ev("permission_decision", payload)]}) == (0, 0, 0)


@pytest.mark.parametrize("payload,typ", [
    ("null", None), ("5", int), ("true", bool),
])
def test_payload_counts_json_scalar_payload_raises(payload, typ):
    """ORTAM-OGRENDI: payload JSON-skaler (null/int/bool) -> json.loads skaler
    doner -> p.get AttributeError YAYILIR (except listesinde AttributeError YOK).
    GERI-UYUM quirk: scalar-payload hata-verir, sessiz-gecer DEGIL."""
    with pytest.raises(AttributeError):
        _payload_counts({"events": [ev("permission_decision", payload)]})


def test_payload_counts_int_payload_skipped():
    """ORTAM-OGRENDI: payload=int (str DEGIL) -> json.loads(int) TypeError ->
    except YAKALAR -> event atlanir (0,0,0)."""
    assert _payload_counts({"events": [ev("permission_decision", 5)]}) == (0, 0, 0)


@pytest.mark.parametrize("et,expected", [
    ("charge_receipt", (0, 0, 1)),
    ("permission_decision", (1, 0, 0)),
    ("other", (0, 0, 0)),
    ("", (0, 0, 0)),
    ("PERMISSION_DECISION", (0, 0, 0)),
    ("charge_Receipt", (0, 0, 0)),
])
def test_payload_counts_event_type_filter(et, expected):
    """ORTAM: event_type case-sensitive tam-eslesme; charge_receipt HER ZAMAN
    receipts sayar (payload'ina bakMAZ)."""
    bundle = {"events": [ev(et, deny("quota_exceeded"))]}
    assert _payload_counts(bundle) == expected


def test_payload_counts_charge_receipt_ignores_its_payload():
    """ORTAM-OGRENDI: charge_receipt dalinda payload HIC OKUNMAZ (once continue)
    — deny/quota payload'i olsa bile SADECE receipts sayilir."""
    bundle = {"events": [ev("charge_receipt", deny("quota_exceeded"))]}
    assert _payload_counts(bundle) == (0, 0, 1)


def test_payload_counts_missing_event_type_skipped():
    """ORTAM: event_type alani YOKSA -> e.get None != her iki tip -> atlanir."""
    assert _payload_counts({"events": [ev(payload=deny("quota_exceeded"))]}) == (0, 0, 0)


def test_payload_counts_missing_payload_key_skipped():
    """ORTAM: payload alani YOKSA -> e.get None -> json.loads(None) TypeError -> atlanir."""
    assert _payload_counts({"events": [ev("permission_decision")]}) == (0, 0, 0)


def test_payload_counts_mixed_events():
    """ORTAM: tum dallar bir arada — oncelik: charge_receipt continue, sonra deny."""
    bundle = {"events": [
        ev("charge_receipt"),
        ev("permission_decision", deny("quota_exceeded")),
        ev("permission_decision", deny("replay")),
        ev("permission_decision", deny("replay")),
        ev("other"),
        ev("permission_decision", deny("unknown")),
        ev("permission_decision", json.dumps({"decision": "allow"})),
        ev("permission_decision", "bad"),
    ]}
    assert _payload_counts(bundle) == (1, 2, 1)


def test_payload_counts_quota_priority_over_receipt():
    """ORTAM: charge_receipt once gelir (continue) — permission_decision ile
    cakismaz; ayni event ikisini saymaz."""
    bundle = {"events": [
        ev("charge_receipt", deny("quota_exceeded")),
        ev("permission_decision", deny("quota_exceeded")),
    ]}
    assert _payload_counts(bundle) == (1, 0, 1)


@pytest.mark.parametrize("payload", [
    '{"decision": "deny", "rule_id": "replay"}',
    '{"rule_id": "replay", "decision": "deny"}',
    '{"a": 1, "decision": "deny", "b": 2, "rule_id": "replay"}',
])
def test_payload_counts_key_order_irrelevant(payload):
    assert _payload_counts({"events": [ev("permission_decision", payload)]}) == (0, 1, 0)


@pytest.mark.parametrize("extra", [{}, {"other": "x"}, {"nested": {"deep": 1}}])
def test_payload_counts_extra_payload_keys_ignored(extra):
    p = json.dumps({"decision": "deny", "rule_id": "quota_exceeded", **extra})
    assert _payload_counts({"events": [ev("permission_decision", p)]}) == (1, 0, 0)


def test_payload_counts_quota_before_replay():
    """ORTAM: rule_id='quota_exceeded' once (if), elif replay — ayni event ikisini
    sayamaz (mutual-exclusive)."""
    p = json.dumps({"decision": "deny", "rule_id": "quota_exceeded"})
    assert _payload_counts({"events": [ev("permission_decision", p)]}) == (1, 0, 0)


@pytest.mark.parametrize("n_quota,n_replay,n_receipt", [
    (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1),
    (3, 2, 1), (10, 10, 10), (100, 0, 0), (0, 100, 0), (0, 0, 100),
])
def test_payload_counts_bulk(n_quota, n_replay, n_receipt):
    events = []
    events += [ev("permission_decision", deny("quota_exceeded"))] * n_quota
    events += [ev("permission_decision", deny("replay"))] * n_replay
    events += [ev("charge_receipt")] * n_receipt
    assert _payload_counts({"events": events}) == (n_quota, n_replay, n_receipt)


@pytest.mark.parametrize("summary", ["s1", "s2", "x"])
def test_payload_counts_unrelated_bundle_keys_ignored(summary):
    """ORTAM: bundle'daki events-disi anahtarlar sayilmaz."""
    assert _payload_counts({"events": [ev("charge_receipt")], "summary": summary}) == (0, 0, 1)


def test_payload_counts_input_not_mutated():
    """ORTAM: bundle ve event dict'lerine mutasyon YOK."""
    bundle = {"events": [ev("permission_decision", deny("replay"))]}
    before = json.dumps(bundle, sort_keys=True)
    _payload_counts(bundle)
    assert json.dumps(bundle, sort_keys=True) == before


def test_payload_counts_events_generator_skipped_safely():
    """ORTAM: events list DEGILSE .get yine list-dongusu calismaz — tuple doner."""
    r = _payload_counts({"events": {}})
    assert r == (0, 0, 0)


def test_payload_counts_turkce_payload():
    p = json.dumps({"decision": "deny", "rule_id": "replay", "not": "ğüşiöç"})
    assert _payload_counts({"events": [ev("permission_decision", p)]}) == (0, 1, 0)
