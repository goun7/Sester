"""SESTER demo-attribution testleri — _agent_of v0.4-düzeltmesi (kaynağa-bağlı).

Kapsam: EVM zarfı GERÇEK istek-yoluyla çözülür (resource="" ile doğrulama
imkânsızdı — v0.4-öncesi her EVM ajanı 'bilinmeyen'e atfediliyordu);
HMAC etiketi aynen döner; yanlış-kaynak EVM zarfı çözülemez (None).
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod

import pytest

eth_account = pytest.importorskip("eth_account")

from eth_account import Account  # noqa: E402

from sester.demo_api import _agent_of  # noqa: E402
from sester.schemes import sign_exact_sester  # noqa: E402

SK = "0x" + "e7" * 32
AGENT = Account.from_key(SK).address.lower()


def test_evm_agent_resolved_with_real_resource():
    env = sign_exact_sester(SK, AGENT, "attr-n1", "0.05", "/weather")
    assert _agent_of(env, "/weather") == AGENT


def test_evm_agent_unresolvable_with_wrong_resource():
    # yanlış kaynak → imza doğrulamaz → None ('bilinmeyen'e akar, atıf YOK)
    env = sign_exact_sester(SK, AGENT, "attr-n2", "0.05", "/weather")
    assert _agent_of(env, "/histogram") is None


def test_hmac_agent_label_passthrough():
    payment = "pugio0 f1-telemetri:n1:0.05:" + hmac_mod.new(
        b"s", b"f1-telemetri|n1|0.05|/weather", hashlib.sha256).hexdigest()
    assert _agent_of(payment, "/weather") == "f1-telemetri"


def test_unknown_prefix_returns_none():
    assert _agent_of("weird-scheme x:y", "/weather") is None
