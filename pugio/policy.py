"""PUGIO policy — KURAL_DSL_V0 v0 alt-kümesi, fail-closed.

Kapsam (v0):
  defaults.per_request_max / daily_max   — üst sınırlar
  rules[].when.host_in                   — host beyaz listesi
  rules[].when.hour_between              — saat aralığı (yerel saat)
  rules[].then: allow / deny / escalate  — kararlar
  İlk eşleşen kural kazanır; hiçbiri eşleşmezse → DENY (fail-closed).
  Politika dosyası bozuk/eksikse → DENY_ALL (tüm harcama durur).

Bilinçli v0-dışı (KARAR_63B): x402_payee_verified, reputation_min,
budget-per-rule, imzalı-policy + 24s gevşetme-gecikmesi, escalate kuyruğu.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ALLOW = "allow"
DENY = "deny"
ESCALATE = "escalate"


@dataclass(frozen=True)
class Decision:
    verdict: str            # allow / deny / escalate
    rule_id: str            # eşleşen kural ya da "fail-closed" / "default-deny"
    reason: str = ""


@dataclass
class Policy:
    """Yüklü ve doğrulanmış politika. Yalnız `Policy.load` üretilir —
    doğrulamadan geçemeyen dosya Policy nesnesi ÜRETMEZ."""
    policy_id: str
    per_request_max: float
    daily_max: float
    rules: list[dict[str, Any]] = field(default_factory=list)
    currency: str = "USDC"
    timezone: str = "Europe/Istanbul"

    # ---------- yükleme / doğrulama ----------

    @classmethod
    def load(cls, path: str | Path) -> "Policy":
        """Fail-closed yükleme: dosya yok/bozuk/şema-dışı → PolicyCorruptError.
        (Arayan taraf bunu DENY_ALL'a çevirir.)"""
        p = Path(path)
        if not p.exists():
            raise PolicyCorruptError(f"politika dosyası yok: {p}")
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            raise PolicyCorruptError(f"politika okunamadı: {e}") from e
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: Any) -> "Policy":
        if not isinstance(raw, dict):
            raise PolicyCorruptError("politika JSON-nesnesi değil")
        pol = raw.get("wallet_policy")
        if not isinstance(pol, dict):
            raise PolicyCorruptError("wallet_policy eksik")
        policy_id = pol.get("id")
        if not isinstance(policy_id, str) or not policy_id:
            raise PolicyCorruptError("wallet_policy.id eksik")
        defaults = pol.get("defaults")
        if not isinstance(defaults, dict):
            raise PolicyCorruptError("defaults eksik")
        try:
            per_req = float(defaults["per_request_max"])
            daily = float(defaults["daily_max"])
        except (KeyError, TypeError, ValueError) as e:
            raise PolicyCorruptError(f"defaults limitleri bozuk: {e}") from e
        if per_req < 0 or daily < 0:
            raise PolicyCorruptError("limitler negatif olamaz")
        if daily < per_req:
            raise PolicyCorruptError("daily_max < per_request_max")
        rules = pol.get("rules", [])
        if not isinstance(rules, list):
            raise PolicyCorruptError("rules liste değil")
        for i, r in enumerate(rules):
            cls._validate_rule(i, r)
        return cls(
            policy_id=policy_id,
            per_request_max=per_req,
            daily_max=daily,
            rules=rules,
            currency=str(defaults.get("currency", "USDC")),
            timezone=str(defaults.get("timezone", "Europe/Istanbul")),
        )

    @staticmethod
    def _validate_rule(i: int, r: Any) -> None:
        if not isinstance(r, dict):
            raise PolicyCorruptError(f"rules[{i}] nesne değil")
        if not isinstance(r.get("id"), str) or not r.get("id"):
            raise PolicyCorruptError(f"rules[{i}].id eksik")
        verdict = r.get("then")
        if verdict not in (ALLOW, DENY, ESCALATE):
            raise PolicyCorruptError(f"rules[{i}].then geçersiz: {verdict!r}")
        when = r.get("when", {})
        if not isinstance(when, dict):
            raise PolicyCorruptError(f"rules[{i}].when nesne değil")
        if "host_in" in when and not isinstance(when["host_in"], list):
            raise PolicyCorruptError(f"rules[{i}].when.host_in liste değil")
        if "hour_between" in when:
            hb = when["hour_between"]
            ok = (
                isinstance(hb, (list, tuple)) and len(hb) == 2
                and all(isinstance(x, str) and len(x) == 5 and x[:2].isdigit() and x[3:].isdigit()
                        for x in hb)
            )
            if not ok:
                raise PolicyCorruptError(f"rules[{i}].when.hour_between ['HH:MM','HH:MM'] olmalı")
        if "amount_gt" in when:
            try:
                float(when["amount_gt"])
            except (TypeError, ValueError) as e:
                raise PolicyCorruptError(f"rules[{i}].when.amount_gt sayı değil") from e

    # ---------- değerlendirme ----------

    def evaluate(self, amount: float, host: str, *, now: _dt.datetime | None = None) -> Decision:
        """İlk-eşleşen kural kazanır; eşleşme yoksa DENY (fail-closed).
        amount üst-sınır ihlali en dar kuraldan önce kontrol edilmez —
        limit-kontrolü middleware'de sayaçla birlikte yapılır; burada kural-
        semantiği değerlendirilir. amount_gt kuralı bunun istisnasıdır."""
        now = now or _dt.datetime.now()
        host_l = (host or "").lower()
        for r in self.rules:
            when = r.get("when", {})
            if "host_in" in when:
                allowed = [h.lower() for h in when["host_in"]]
                # boş liste = yakala-hepsini (KURAL_DSL "deny-unknown-hosts" anlamı):
                # önceki allow-kuralları bilinen hostları zaten tüketir.
                if allowed and host_l not in allowed:
                    continue
            if "hour_between" in when:
                start_s, end_s = when["hour_between"]
                cur = now.hour * 60 + now.minute
                s = int(start_s[:2]) * 60 + int(start_s[3:])
                e = int(end_s[:2]) * 60 + int(end_s[3:])
                if s <= e:
                    inside = s <= cur < e
                else:  # gece-boyu aralık (ör. 22:00–08:00)
                    inside = cur >= s or cur < e
                if not inside:
                    continue
            if "amount_gt" in when:
                if not (amount > float(when["amount_gt"])):
                    continue
            return Decision(r["then"], r["id"])
        # hiçbiri eşleşmedi → fail-closed
        return Decision(DENY, "default-deny", "eşleşen kural yok — fail-closed")


class PolicyCorruptError(Exception):
    """Politika dosyası yok/bozuk/şema-dışı — DENY_ALL'a işaret eder."""


class DenyAll:
    """Bozuk-politika hâli: her şey durur (KURAL_DSL_V0 §4 fail-closed)."""

    def evaluate(self, amount: float, host: str, *, now: _dt.datetime | None = None) -> Decision:
        return Decision(DENY, "fail-closed", "politika bozuk — tüm harcama durur")

    @property
    def per_request_max(self) -> float:
        return 0.0

    @property
    def daily_max(self) -> float:
        return 0.0
