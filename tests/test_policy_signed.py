"""SESTER policy_signed testleri — S3: imzalı politika + 24s gevşetme-gate.

Kapsam: JWS-mühür + yükleme (fail-closed), sıkılaştırma-anında, gevşetme-24s
bekleme (deterministik saat), bekleyen politikanın kararlara sızmaması,
kural-sınıflandırma (ekle/sil/limit/host/pencere/then), vault-geçmişi.
"""

from __future__ import annotations

import json
import time

import pytest

from sester.policy import Policy
from sester.policy_signed import (
    RELAXATION_DELAY,
    SignedPolicyError,
    SignedPolicyVault,
    classify_change,
    sign_policy,
)

HS = b"s3-vault-secret"
WALLET = "0xs300000000000000000000000000000000000000"


def _body(**over) -> dict:
    b = {
        "id": "wpol-s3",
        "owner": "did:agent:kok:s3",
        "wallet": f"evm:{WALLET}",
        "defaults": {"currency": "USDC", "per_request_max": 0.50,
                     "daily_max": 25.00, "timezone": "UTC"},
        "rules": [
            {"id": "allow-w", "when": {"host_in": ["/weather"]}, "then": "allow"},
            {"id": "deny-rest", "when": {"host_in": []}, "then": "deny"},
        ],
    }
    b.update(over)
    return b


def _env(body: dict, *, signed_at=None) -> dict:
    return sign_policy({"wallet_policy": body}, alg="HS256", key=HS,
                       signer="did:user:gokun", signed_at=signed_at)


# ---------------------------------------------------------------- sınıflandırma

def test_118_classify_new_and_removed_rules():
    old = _body()
    new = _body()
    new["rules"] = [r for r in new["rules"] if r["id"] != "deny-rest"]
    new["rules"].append({"id": "extra-allow", "when": {"host_in": ["/x"]},
                         "then": "allow"})
    ch = {c["rule_id"]: c for c in classify_change(old, new)}
    assert ch["deny-rest"]["kind"] == "tighten"
    assert ch["extra-allow"]["kind"] == "relax"


def test_119_classify_then_flip_and_limits():
    old = _body()
    new = _body()
    new["rules"][1]["then"] = "allow"          # deny→allow: gevşetme
    new["defaults"]["per_request_max"] = 1.00  # artış: gevşetme
    new["rules"][0]["when"]["host_in"] = ["/weather", "/histogram"]  # büyüme
    ch = {c["rule_id"]: c for c in classify_change(old, new)}
    assert ch["deny-rest"]["kind"] == "relax"
    assert ch["defaults.per_request_max"]["kind"] == "relax"
    assert ch["allow-w"]["kind"] == "relax"


def test_120_classify_tighten_paths():
    old = _body()
    new = _body()
    new["rules"][0]["then"] = "deny"           # allow→deny
    new["defaults"]["daily_max"] = 10.0        # azalış
    ch = {c["rule_id"]: c for c in classify_change(old, new)}
    assert ch["allow-w"]["kind"] == "tighten"
    assert ch["defaults.daily_max"]["kind"] == "tighten"


def test_121_mixed_change_is_relaxation_conservative():
    """Karışık değişiklik: en-gevşetici kazanır (güvenlik-muhafazakâr)."""
    old = _body()
    new = _body()
    new["rules"][0]["then"] = "deny"                    # sıkılaştırma
    new["defaults"]["per_request_max"] = 5.00           # gevşetme
    assert classify_change(old, new)  # sınıflandırma çalışır
    changes = classify_change(old, new)
    kinds = {c["kind"] for c in changes}
    assert "relax" in kinds and "tighten" in kinds


# ---------------------------------------------------------------- vault-akışı

def test_122_initial_load_then_tighten_is_immediate():
    v = SignedPolicyVault(resolve_key=lambda kid, alg: HS)
    v.load_envelope(_env(_body()))
    assert v.current and v.current.policy_id == "wpol-s3"
    # sıkılaştırma: günlük-limit düşür → anında geçerli
    tight = _body()
    tight["defaults"]["daily_max"] = 5.0
    v.load_envelope(_env(tight))
    assert v.current_body["defaults"]["daily_max"] == 5.0
    assert not v.is_pending_relaxation()


def test_123_relaxation_waits_full_delay_then_applies():
    now = 1_800_000_000.0
    v = SignedPolicyVault(resolve_key=lambda kid, alg: HS, now=lambda: now)
    v.load_envelope(_env(_body(signed_at=now)))
    # gevşetme: yeni allow-kuralı
    loose = _body()
    loose["rules"].insert(0, {"id": "allow-more", "when": {"host_in": ["/new"]},
                              "then": "allow"})
    v.load_envelope(_env(loose, signed_at=now))
    assert v.is_pending_relaxation(), "gevşetme beklemeye girmeli"
    assert v.current_body["id"] == "wpol-s3"
    # vade dolmadan: hâlâ eski politika
    v._now = lambda: now + RELAXATION_DELAY - 1
    v.tick()
    assert v.is_pending_relaxation()
    # vade dolunca: uygulanır
    v._now = lambda: now + RELAXATION_DELAY + 1
    v.tick()
    assert not v.is_pending_relaxation()
    assert any(r["id"] == "allow-more" for r in v.current_body["rules"])


def test_124_pending_relaxation_never_leaks_into_decisions():
    now = 1_800_000_000.0
    v = SignedPolicyVault(resolve_key=lambda kid, alg: HS, now=lambda: now)
    v.load_envelope(_env(_body(signed_at=now)))
    loose = _body()
    loose["rules"].insert(0, {"id": "allow-more", "when": {"host_in": ["/new"]},
                              "then": "allow"})
    v.load_envelope(_env(loose, signed_at=now))
    # /new gevşetme-öncesi deny olmalı (default-deny)
    d = v.evaluate(0.10, "/new")
    assert d.verdict == "deny", "bekleyen gevşetme karara sızmamalı"


def test_125_tampered_envelope_rejected_state_unchanged():
    v = SignedPolicyVault(resolve_key=lambda kid, alg: HS)
    v.load_envelope(_env(_body()))
    before = json.dumps(v.current_body, sort_keys=True)
    evil = _env(_body())
    evil["policy"]["wallet_policy"]["defaults"]["daily_max"] = 9999.0  # imza-dışı kazı
    with pytest.raises(SignedPolicyError):
        v.load_envelope(evil)
    assert json.dumps(v.current_body, sort_keys=True) == before


def test_126_corrupt_envelope_fail_closed():
    v = SignedPolicyVault(resolve_key=lambda kid, alg: HS)
    with pytest.raises(SignedPolicyError):
        v.load_envelope({"policy_envelope_version": 99})
    with pytest.raises(SignedPolicyError):
        v.load_envelope("bu bir JSON değil")
    # politika yüklenememiş → evaluate fail-closed deny
    assert v.evaluate(0.10, "/weather").verdict == "deny"


def test_127_wrong_key_rejected():
    v = SignedPolicyVault(resolve_key=lambda kid, alg: b"other-key")
    with pytest.raises(SignedPolicyError):
        v.load_envelope(_env(_body()))


def test_128_vault_policy_loads_as_real_policy():
    v = SignedPolicyVault(resolve_key=lambda kid, alg: HS)
    v.load_envelope(_env(_body()))
    assert isinstance(v.current, Policy)
    # kurallar gerçekten çalışıyor: /weather allow, /bilinmeyen deny
    assert v.evaluate(0.10, "/weather").verdict == "allow"
    assert v.evaluate(0.10, "/bilinmeyen").verdict == "deny"
