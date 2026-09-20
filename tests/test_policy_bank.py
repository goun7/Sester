"""Politika-şablon-bankası — makine-kilidi (1.ay-yol-haritası-maddesi).

Her örnek-politika `examples/`-altında-dağılmış-şablonlardır; bu-test onların:
  (a) DSL-validatörden (`Policy.from_dict`) temiz-geçtiğini,
  (b) en-az-bir allow + en-az-bir sınır (deny/escalate) kuralı-içerdiğini
ölçer. Bir-şablon bozulursa (örn. yeni-bir-DSL-alanı-eşleşmeyince) RED düşer —
şablon-bankası-yarı-iş-kalmaz. Non-policy JSON'lar skip-olur.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sester.policy import ALLOW, DENY, ESCALATE, Policy

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _policy_templates() -> list[Path]:
    """examples/-altındaki tüm wallet_policy-içeren JSON'lar."""
    out: list[Path] = []
    for p in sorted(EXAMPLES.rglob("*.json")):
        try:
            if isinstance(json.loads(p.read_text(encoding="utf-8")), dict) and \
               "wallet_policy" in json.loads(p.read_text(encoding="utf-8")):
                out.append(p)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
    return out


@pytest.mark.parametrize(
    "path", _policy_templates(),
    ids=lambda p: str(p.relative_to(EXAMPLES)))
def test_bank_template_validates(path: Path) -> None:
    """(a) DSL-validatörden-geçer."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    pol = Policy.from_dict(raw)  # PolicyCorruptError fırlatırsa RED
    verdicts = {r.get("then") for r in pol.rules}
    assert ALLOW in verdicts, "şablonda-en-az-bir allow-kuralı-olmalı"
    assert verdicts & {DENY, ESCALATE}, \
        "şablonda-en-az-bir sınır-kuralı (deny/escalate) olmalı"
    # defaults-tutarlılığı: daily >= per_request (validatör-da-var, burada
    # şablon-yazarının-gözünden-kaçmaması-için-tekrar)
    assert pol.daily_max >= pol.per_request_max


def test_bank_has_multiple_templates() -> None:
    """Şablon-bankası-en-az-2-şablon-içerir — banka-tek-örnekle-başlamaz."""
    templates = _policy_templates()
    assert len(templates) >= 2, \
        f"şablon-bankası-en-az-2-şablon-bekler, bulundu: {len(templates)}"


def _budget_guard() -> Policy:
    """examples/budget_guard_policy.json'i-yükler (semantik-testleri-için)."""
    import datetime as _dt
    raw = json.loads(
        (EXAMPLES / "budget_guard_policy.json").read_text(encoding="utf-8"))
    pol = Policy.from_dict(raw)
    # hour-window-yok, o-yüzden herhangi-bir-saat-güvenli
    pol._noon = _dt.datetime(2026, 9, 20, 12, 0)
    return pol


def test_budget_guard_semantics() -> None:
    """Üçüncü-şablon budget-guard: iki amount_gt-eşiği + allowlist + fail-closed.
    Sıralama-önemli-testi: $15 deny-kuralında-yakalanır, $5 escalate'a-düşer,
    $0.50-bilinen-host allow, bilinmeyen-host deny."""
    pol = _budget_guard()
    noon = pol._noon

    assert pol.evaluate(15.0, "/telemetry", now=noon).verdict == "deny"
    assert pol.evaluate(5.0, "/telemetry", now=noon).verdict == "escalate"
    assert pol.evaluate(0.50, "/telemetry", now=noon).verdict == "allow"
    # bilinmeyen-host: allow-kuralı-atlar → deny-unknown-hosts
    assert pol.evaluate(0.10, "/admin", now=noon).verdict == "deny"
    # yüksek-tutar + bilinmeyen-host: deny-large-önce-eşleşir (sıra-önemli)
    d = pol.evaluate(50.0, "/admin", now=noon)
    assert d.verdict == "deny" and d.rule_id == "deny-large"


def test_budget_guard_is_fail_closed() -> None:
    """Hiçbir-kural-eşleşmeyen-durum DENY — fail-closed-default şablonda
    görünür-kılındı (deny-unknown-hosts boş-listeyle-hepsini-yakalar)."""
    pol = _budget_guard()
    # allowlist-dışındaki-host için deny-kuralı-olmasaydı default-deny-ye-düşerdi;
    # şablon bunu açık-kural-yapmış — hem-açık-hem-de-default-fail-closed.
    d = pol.evaluate(0.01, "/unknown", now=pol._noon)
    assert d.verdict == "deny"
