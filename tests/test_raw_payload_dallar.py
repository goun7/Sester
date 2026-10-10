"""sester.signer._raw_payload dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (dataclass ile sabit-yapi, dis cagri YOK).
Standart ham-yuk: batch'in kanit-cifti + calldata, deterministik.
"""
import sys

import pytest

sys.path.insert(0, ".")
from sester.settlement import SettlementBatch  # noqa: E402
from sester.signer import _raw_payload  # noqa: E402


def batch(**kw):
    base = {
        "agent": "agent-1", "payee_address": "0xabc", "chain_id": 8453,
        "contract": "0xcontract", "from_address": "0xfrom",
        "total_minor": 1000, "currency": "USDC", "event_count": 5,
        "merkle_root": "0x" + "a" * 64, "leaves": ["l1", "l2"],
        "calldata": "0xdata", "sha_digest": "0x" + "b" * 64,
    }
    base.update(kw)
    return SettlementBatch(**base)


# -- yapi ------------------------------------------------------------------------------------

def test_returns_dict():
    assert isinstance(_raw_payload(batch()), dict)


def test_returns_8_keys():
    assert set(_raw_payload(batch())) == {
        "to", "from", "chain_id", "data", "value",
        "sester_batch_digest", "sester_merkle_root", "sester_event_count",
    }


def test_key_mapping():
    """to=contract, from=from_address, data=calldata."""
    r = _raw_payload(batch(contract="0xC", from_address="0xF",
                           calldata="0xD"))
    assert r["to"] == "0xC" and r["from"] == "0xF" and r["data"] == "0xD"


def test_value_constant():
    assert _raw_payload(batch())["value"] == "0x0"


def test_chain_id_int():
    assert _raw_payload(batch(chain_id=1))["chain_id"] == 1


def test_chain_id_field():
    assert _raw_payload(batch(chain_id=8453))["chain_id"] == 8453


def test_digest_field():
    d = "0x" + "c" * 64
    assert _raw_payload(batch(sha_digest=d))["sester_batch_digest"] == d


def test_merkle_field():
    m = "0x" + "d" * 64
    assert _raw_payload(batch(merkle_root=m))["sester_merkle_root"] == m


def test_event_count_field():
    assert _raw_payload(batch(event_count=42))["sester_event_count"] == 42


# -- degerler ----------------------------------------------------------------------------------

def test_all_string_fields():
    r = _raw_payload(batch())
    assert isinstance(r["to"], str) and isinstance(r["from"], str)
    assert isinstance(r["data"], str) and isinstance(r["value"], str)
    assert isinstance(r["sester_batch_digest"], str)
    assert isinstance(r["sester_merkle_root"], str)


def test_chain_id_type():
    assert isinstance(_raw_payload(batch())["chain_id"], int)


def test_event_count_type():
    assert isinstance(_raw_payload(batch())["sester_event_count"], int)


def test_no_agent_field():
    """agent ham-yukte YOK (denetim-iz disinda)."""
    assert "agent" not in _raw_payload(batch())


def test_no_payee_field():
    assert "payee_address" not in _raw_payload(batch())


def test_no_leaves_field():
    assert "leaves" not in _raw_payload(batch())


def test_no_total_minor_field():
    assert "total_minor" not in _raw_payload(batch())


def test_no_currency_field():
    assert "currency" not in _raw_payload(batch())


# -- deterministik -----------------------------------------------------------------------------

def test_repeatable():
    b = batch()
    assert _raw_payload(b) == _raw_payload(b)


def test_independent_batches():
    a = batch(sha_digest="0x" + "1" * 64)
    b = batch(sha_digest="0x" + "2" * 64)
    assert _raw_payload(a) != _raw_payload(b)


def test_batch_digest_changes_output():
    b = batch()
    r1 = _raw_payload(b)
    b2 = batch(sha_digest="0x" + "9" * 64)
    assert _raw_payload(b2)["sester_batch_digest"] != r1["sester_batch_digest"]


def test_merkle_changes_output():
    b1 = batch(merkle_root="0x" + "1" * 64)
    b2 = batch(merkle_root="0x" + "2" * 64)
    assert _raw_payload(b1) != _raw_payload(b2)


def test_contract_changes_to():
    assert _raw_payload(batch(contract="0x1"))["to"] != \
        _raw_payload(batch(contract="0x2"))["to"]


# -- frozen-dataclass ---------------------------------------------------------------------------

def test_frozen_batch():
    """dataclass(frozen=True) — batch degisemez."""
    b = batch()
    with pytest.raises(Exception):
        b.agent = "degisti"


def test_calldata_empty():
    r = _raw_payload(batch(calldata=""))
    assert r["data"] == ""


def test_turkish_agent_ignored():
    """agent ham-yukte olmadigi icin Turkce etkisi yok."""
    assert _raw_payload(batch(agent="Gökhan"))["to"] == "0xcontract"


def test_unicode_calldata():
    r = _raw_payload(batch(calldata="0xİstanbul"))
    assert r["data"] == "0xİstanbul"


def test_zero_event_count():
    assert _raw_payload(batch(event_count=0))["sester_event_count"] == 0


def test_large_event_count():
    assert _raw_payload(batch(event_count=10**9))["sester_event_count"] == 10**9


def test_chain_id_zero():
    assert _raw_payload(batch(chain_id=0))["chain_id"] == 0


def test_empty_fields():
    r = _raw_payload(batch(contract="", from_address="", calldata=""))
    assert r["to"] == "" and r["from"] == "" and r["data"] == ""


def test_json_serializable():
    """ham-yuk JSON'a serialize edilebilir (tum tipler)."""
    import json
    json.dumps(_raw_payload(batch()))


@pytest.mark.parametrize("cid", [1, 8453, 137, 11155111])
def test_chain_ids(cid):
    assert _raw_payload(batch(chain_id=cid))["chain_id"] == cid


@pytest.mark.parametrize("ec", [0, 1, 10, 1000])
def test_event_counts(ec):
    assert _raw_payload(batch(event_count=ec))["sester_event_count"] == ec
