"""tamga_pugio_receiver.verify_anchor dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Dış çağrı YOK: saf sha256 dogrulama.
"""
import hashlib
import json

import pytest

import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "tp_receiver",
    os.path.join("bridge_receivers", "tamga_pugio_receiver.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
verify_anchor = _mod.verify_anchor
BRIDGE_VERSION = _mod.BRIDGE_VERSION
GENESIS_HEAD_LEN = _mod.GENESIS_HEAD_LEN


def _hex64(seed="a"):
    return hashlib.sha256(seed.encode()).hexdigest()


def _valid(source="sikke", head=None, merkle=None, count=5,
           anchor_id=None):
    head = head or _hex64("head")
    merkle = merkle or _hex64("merkle")
    aid = anchor_id or hashlib.sha256(
        f"{head}|{merkle}|{count}".encode()).hexdigest()[:32]
    return json.dumps({
        "type": "external_anchor", "source": source,
        "bridge_version": BRIDGE_VERSION, "head": head,
        "merkle_root": merkle, "event_count": count,
        "anchor_id": aid,
    })


# -- gecerli ---------------------------------------------------------------------------------

def test_valid_returns_true():
    ok, _ = verify_anchor(_valid())
    assert ok is True


def test_valid_message_has_saglam():
    _, msg = verify_anchor(_valid())
    assert "çıpa-SAĞLAM" in msg


def test_valid_message_has_anchor_id():
    _, msg = verify_anchor(_valid())
    assert hashlib.sha256(
        f"{_hex64('head')}|{_hex64('merkle')}|5".encode()
    ).hexdigest()[:32] in msg


def test_pugio_source_valid():
    ok, _ = verify_anchor(_valid(source="pugio"))
    assert ok is True


def test_count_zero():
    line = _valid(count=0)
    ok, _ = verify_anchor(line)
    assert ok is True


def test_large_count():
    ok, _ = verify_anchor(_valid(count=1000000))
    assert ok is True


# -- JSON bozuk ---------------------------------------------------------------------------------

def test_invalid_json():
    ok, msg = verify_anchor("{not json}")
    assert ok is False
    assert "JSON bozuk" in msg


def test_empty_string():
    ok, msg = verify_anchor("")
    assert ok is False
    assert "JSON bozuk" in msg


def test_empty_object():
    ok, msg = verify_anchor("{}")
    assert ok is False


# -- zarf tipi ---------------------------------------------------------------------------------

def test_wrong_type():
    ok, msg = verify_anchor(json.dumps({"type": "other"}))
    assert ok is False
    assert "external_anchor" in msg


def test_missing_type():
    ok, _ = verify_anchor(json.dumps({"source": "sikke"}))
    assert ok is False


# -- kaynak ---------------------------------------------------------------------------------

def test_wrong_source():
    a = json.loads(_valid())
    a["source"] = "baska"
    ok, msg = verify_anchor(json.dumps(a))
    assert ok is False
    assert "kaynak" in msg


def test_missing_source():
    a = json.loads(_valid())
    del a["source"]
    ok, _ = verify_anchor(json.dumps(a))
    assert ok is False


@pytest.mark.parametrize("src", ["sikke", "pugio"])
def test_both_valid_sources(src):
    ok, _ = verify_anchor(_valid(source=src))
    assert ok is True


# -- bridge_version ---------------------------------------------------------------------------------

def test_wrong_bridge_version():
    a = json.loads(_valid())
    a["bridge_version"] = 999
    ok, msg = verify_anchor(json.dumps(a))
    assert ok is False
    assert "bridge_version" in msg


def test_missing_bridge_version():
    a = json.loads(_valid())
    del a["bridge_version"]
    ok, _ = verify_anchor(json.dumps(a))
    assert ok is False


def test_string_bridge_version():
    a = json.loads(_valid())
    a["bridge_version"] = str(BRIDGE_VERSION)
    ok, _ = verify_anchor(json.dumps(a))
    assert ok is True


# -- event_count ---------------------------------------------------------------------------------

def test_string_count_invalid():
    a = json.loads(_valid())
    a["event_count"] = "bes"
    ok, msg = verify_anchor(json.dumps(a))
    assert ok is False
    assert "event_count" in msg


def test_missing_count():
    a = json.loads(_valid())
    del a["event_count"]
    ok, _ = verify_anchor(json.dumps(a))
    assert ok is False


def test_float_count_truncated():
    """int(5.9) = 5 -> hash 5 ile eslesmeli."""
    a = json.loads(_valid(count=5))
    a["event_count"] = 5.9
    ok, _ = verify_anchor(json.dumps(a))
    assert ok is True


# -- head/merkle uzunluk ---------------------------------------------------------------------------------

def test_short_head():
    a = json.loads(_valid())
    a["head"] = "kisa"
    ok, msg = verify_anchor(json.dumps(a))
    assert ok is False
    assert "head/merkle" in msg


def test_short_merkle():
    a = json.loads(_valid())
    a["merkle_root"] = "kisa"
    ok, _ = verify_anchor(json.dumps(a))
    assert ok is False


def test_missing_head():
    a = json.loads(_valid())
    del a["head"]
    ok, _ = verify_anchor(json.dumps(a))
    assert ok is False


def test_non_hex_head_accepted():
    """uzunluk 64 -> hex-karakter kontrolu YOK."""
    head = "g" * GENESIS_HEAD_LEN
    a = json.loads(_valid(head=head))
    ok, _ = verify_anchor(json.dumps(a))
    assert ok is True


# -- anchor_id kopuklugu ---------------------------------------------------------------------------------

def test_wrong_anchor_id():
    a = json.loads(_valid())
    a["anchor_id"] = _hex64("farkli")[:32]
    ok, msg = verify_anchor(json.dumps(a))
    assert ok is False
    assert "bağı kopuk" in msg


def test_missing_anchor_id():
    a = json.loads(_valid())
    del a["anchor_id"]
    ok, _ = verify_anchor(json.dumps(a))
    assert ok is False


def test_tampered_count_breaks_id():
    a = json.loads(_valid(count=5))
    a["event_count"] = 6
    ok, _ = verify_anchor(json.dumps(a))
    assert ok is False


def test_tampered_head_breaks_id():
    a = json.loads(_valid())
    a["head"] = _hex64("baska")
    ok, _ = verify_anchor(json.dumps(a))
    assert ok is False


def test_tampered_merkle_breaks_id():
    a = json.loads(_valid())
    a["merkle_root"] = _hex64("baska")
    ok, _ = verify_anchor(json.dumps(a))
    assert ok is False


# -- return turu ---------------------------------------------------------------------------------

def test_returns_tuple():
    assert isinstance(verify_anchor(_valid()), tuple)


def test_returns_two_values():
    assert len(verify_anchor(_valid())) == 2


def test_bool_first():
    assert isinstance(verify_anchor(_valid())[0], bool)


def test_str_second():
    assert isinstance(verify_anchor(_valid())[1], str)


# -- tekrar ---------------------------------------------------------------------------------

def test_repeatable():
    line = _valid()
    assert verify_anchor(line) == verify_anchor(line)


def test_two_lines_independent():
    a = verify_anchor(_valid(head=_hex64("h1")))
    b = verify_anchor(_valid(head=_hex64("h2")))
    assert a[0] and b[0]
