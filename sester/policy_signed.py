"""SESTER policy_signed — S3 (IS_PLANI §7): imzalı politika + 24s gevşetme-gate.

KURAL_DSL_V0 §3 değişim-yönetimi:
  · Politika dosyası **imzalı** değişir (sahip anahtarı) — imza bozuksa
    politika YÜKLENMEZ (SignedPolicyError → fail-closed DenyAll).
  · "Kural gevşetme" (deny→allow, limit-artışı, kapsam-genişletme)
    değişiklikleri **24 saat gecikmeli** geçerlilik kazanır (acele-gevşetme
    saldırısına karşı); **sıkılaştırma anında** geçer.

Şema (policy-envelope):
  { "policy_envelope_version": 1,
    "signed_at": <unix>, "signer": "did:…",
    "signature": <JWS-compact(HS256/ES256)>,
    "policy": {…wallet_policy-gövdesi…} }

JWS-payload = policy-gövdesi → gövde-imza bağı verify_mandate_jws ile
(bağ-alanları: id, defaults, rules) denetlenir.

Gevşetme-sınıflandırma (kural-bazlı, id-eş):
  · kural eklendi  → gevşetme (yeni harcama-kapısı)
  · kural silindi  → sıkılaştırma
  · then: deny→allow            → gevşetme
  · then: allow→deny/escalate   → sıkılaştırma
  · per_request_max/daily_max arttı → gevşetme; azaldı → sıkılaştırma
  · host_in kümesi büyüdü       → gevşetme; küçüldü → sıkılaştırma
  · hour_between penceresi genişledi → gevşetme; daraldı → sıkılaştırma
  · aynı kuralın karışık alanları → en-gevşetici sınıf kazanır (güvenlik-
    muhafazakâr: karışık değişiklik beklemez)
Kural: gevşetici değişiklik `effective_at = signed_at + 86400`; sıkılaştırıcı
`signed_at` (anında). Bekleyen gevşetme için eski (sıkı) politika geçerli kalır.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .adapters import AdapterError, KeyResolver, sign_mandate_jws, verify_mandate_jws
from .policy import Policy, PolicyCorruptError

ENVELOPE_VERSION = 1
RELAXATION_DELAY = 86400.0  # 24 saat (KURAL_DSL §3)

# JWS-payload ↔ zarf-gövdesi bağı: bu alanlar imzayla kilitli
_BOUND_FIELDS = ("id", "defaults", "rules")


class SignedPolicyError(Exception):
    """İmzalı politika zarfı bozuk — fail-closed'a işaret eder."""


# ------------------------------------------------------------------ üretim

def sign_policy(policy_dict: dict[str, Any], *, alg: str, key: Any,
                signer: str, kid: str | None = None,
                signed_at: float | None = None) -> dict[str, Any]:
    """wallet_policy-gövdesini JWS ile mühürleyip zarf üretir."""
    body = policy_dict.get("wallet_policy", policy_dict)
    if "id" not in body:
        raise SignedPolicyError("policy-gövdesinde wallet_policy.id yok")
    sig = sign_mandate_jws(body, alg=alg, key=key, kid=kid)
    return {
        "policy_envelope_version": ENVELOPE_VERSION,
        "signed_at": time.time() if signed_at is None else float(signed_at),
        "signer": signer,
        "signature": sig,
        "policy": {"wallet_policy": body},
    }


def signed_policy_json(envelope: dict[str, Any]) -> str:
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


# ------------------------------------------------------------------ sınıflandırma

def _hms(s: str) -> int:
    return int(s[:2]) * 60 + int(s[3:])


def _window(hb: list[str]) -> int:
    """hour_between pencerisinin dakika-uzunluğu (gece-boyu dahil)."""
    start, end = _hms(hb[0]), _hms(hb[1])
    return (end - start) % 1440 or 1440


def classify_change(old: dict[str, Any], new: dict[str, Any],
                    ) -> list[dict[str, Any]]:
    """İki wallet_policy gövdesi arasındaki değişiklikleri kural-bazlı
    sınıflandırır. Dönüş: [{rule_id, kind: relax|tighten|same, detail}]."""
    out: list[dict[str, Any]] = []
    old_rules = {r.get("id"): r for r in old.get("rules", [])}
    new_rules = {r.get("id"): r for r in new.get("rules", [])}

    for rid in old_rules.keys() | new_rules.keys():
        o, n = old_rules.get(rid), new_rules.get(rid)
        if o is not None and n is None:
            out.append({"rule_id": rid, "kind": "tighten",
                        "detail": "kural silindi"})
            continue
        if o is None and n is not None:
            out.append({"rule_id": rid, "kind": "relax",
                        "detail": "yeni kural eklendi"})
            continue
        kind = "same"
        detail: list[str] = []
        if o.get("then") != n.get("then"):
            was_allow = o.get("then") == "allow"
            now_allow = n.get("then") == "allow"
            kind = "relax" if (not was_allow and now_allow) else "tighten"
            detail.append(f"then: {o.get('then')}→{n.get('then')}")
        od, nd = o.get("when", {}), n.get("when", {})
        for lim in ("amount_gt",):
            if lim in od or lim in nd:
                ov, nv = od.get(lim), nd.get(lim)
                if ov != nv and (ov is None or nv is None or float(nv) < float(ov)):
                    kind = "relax" if kind != "relax" else kind
                    detail.append(f"{lim}: {ov}→{nv}")
        if "host_in" in od or "host_in" in nd:
            oh = {h.lower() for h in od.get("host_in", []) if h}
            nh = {h.lower() for h in nd.get("host_in", []) if h}
            if oh != nh:
                # boş = yakala-hepsini (bilinmeyenleri) — büyüme/küçülme yerine
                # boş-luğa geçiş en-gevşeticidir
                if nh and not oh:
                    k = "tighten"  # yakala-hepsini → liste: daralma
                elif not nh and oh:
                    k = "relax"    # liste → yakala-hepsini: genişleme
                else:
                    k = "relax" if nh - oh else "tighten"
                kind = k if kind == "same" or (k == "relax") else kind
                detail.append(f"host_in: {sorted(oh)}→{sorted(nh)}")
        if "hour_between" in od or "hour_between" in nd:
            ow = _window(od["hour_between"]) if "hour_between" in od else None
            nw = _window(nd["hour_between"]) if "hour_between" in nd else None
            if ow != nw and (ow is None or nw is None or nw > ow):
                kind = "relax" if kind != "relax" else kind
                detail.append(f"hour_between: {od.get('hour_between')}→{nd.get('hour_between')}")
        out.append({"rule_id": rid, "kind": kind,
                    "detail": "; ".join(detail) or "değişiklik yok"})

    # defaults-limitleri (kural-dışı): artış gevşetme, azalış sıkılaştırma
    od, nd = old.get("defaults", {}), new.get("defaults", {})
    for lim in ("per_request_max", "daily_max", "monthly_max"):
        ov, nv = od.get(lim), nd.get(lim)
        if ov is not None and nv is not None and float(nv) != float(ov):
            kind = "relax" if float(nv) > float(ov) else "tighten"
            out.append({"rule_id": f"defaults.{lim}", "kind": kind,
                        "detail": f"{lim}: {ov}→{nv}"})
    return out


def _is_relaxation(changes: list[dict[str, Any]]) -> bool:
    return any(c["kind"] == "relax" for c in changes)


# ------------------------------------------------------------------ yükleme

class SignedPolicyVault:
    """İmzalı politika-deposu: imza + gevşetme-gate'i ile geçerli-politika.

    load(path): zarfı doğrula; değişiklik-sınıfına göre:
      sıkılaştırma / ilk-yükleme → anında geçerli
      gevşetme → effective_at = signed_at + 86400; o saate kadar ESKİ politika
                 geçerli kalır (bilinçli bekleme — pending durumu görünür).
    Fail-closed: zarf/imza/gövde bozuk → SignedPolicyError; mevcut politika
    *değişmez* (sıkı durumu koru), arayan DenyAll'a düşebilir.
    """

    def __init__(self, *, resolve_key: KeyResolver, now: Any = None) -> None:
        self._resolve_key = resolve_key
        self._now = now or time.time
        self.current: Policy | None = None
        self.current_body: dict[str, Any] | None = None
        self.pending_body: dict[str, Any] | None = None
        self.pending_effective_at: float | None = None
        self.pending_signed_at: float | None = None
        self.history: list[dict[str, Any]] = []

    def load(self, source: str | Path) -> dict[str, Any]:
        """Zarf-yolunu (veya JSON-dizgesini) yükle; geçerli-politikayı döndür."""
        p = Path(source)
        try:
            raw = p.read_text(encoding="utf-8") if p.exists() and p.suffix else source
            env = json.loads(raw)
        except (json.JSONDecodeError, OSError) as e:
            raise SignedPolicyError(f"zarf okunamadı: {e}") from e
        return self.load_envelope(env)

    def load_envelope(self, env: Any) -> dict[str, Any]:
        if not isinstance(env, dict):
            raise SignedPolicyError("zarf JSON-nesnesi değil")
        if int(env.get("policy_envelope_version", 0)) != ENVELOPE_VERSION:
            raise SignedPolicyError("zarf-sürümü bilinmiyor")
        for k in ("signed_at", "signer", "signature", "policy"):
            if k not in env:
                raise SignedPolicyError(f"zarf.{k} eksik")
        body = env["policy"].get("wallet_policy") if isinstance(env["policy"], dict) else None
        if not isinstance(body, dict) or not body.get("id"):
            raise SignedPolicyError("zarf.policy.wallet_policy bozuk")
        try:
            payload = verify_mandate_jws(
                env["signature"], resolve_key=self._resolve_key,
                expected_body={k: body.get(k) for k in _BOUND_FIELDS},
            )
        except AdapterError as e:
            raise SignedPolicyError(f"politika-imzası reddedildi: {e}") from e
        # payload ↔ gövde bağı: JWS-payload'u kendisi gövde olmalı
        if any(payload.get(k) != body.get(k) for k in _BOUND_FIELDS):
            raise SignedPolicyError("JWS-payload gövdeyle uyuşmuyor")

        prev = self.current_body
        if prev is None:
            # ilk-yükleme: anında geçerli
            self._activate(body, env, "initial", immediate=True)
        else:
            changes = classify_change(prev, body)
            relax = _is_relaxation(changes)
            if relax:
                eff = float(env["signed_at"]) + RELAXATION_DELAY
                if self._now() >= eff:
                    self._activate(body, env, "relax-applied", immediate=True)
                else:
                    self.pending_body = body
                    self.pending_effective_at = eff
                    self.pending_signed_at = float(env["signed_at"])
                    self.history.append({
                        "at": self._now(), "kind": "relax-pending",
                        "effective_at": eff, "changes": changes,
                        "signed_at": env["signed_at"], "signer": env["signer"],
                    })
            else:
                self._activate(body, env, "tighten", immediate=True)
        return self._active_body()

    def tick(self) -> Policy | None:
        """Bekleyen gevşetme vadesi dolduysa uygula (zamanla-çağır)."""
        if (self.pending_body is not None
                and self._now() >= (self.pending_effective_at or 0)):
            body = self.pending_body
            signed_at = self.pending_signed_at or (
                (self.pending_effective_at or self._now()) - RELAXATION_DELAY)
            self.pending_body, self.pending_effective_at = None, None
            self.pending_signed_at = None
            self._activate(body, {"signed_at": signed_at, "signer": ""},
                           "relax-applied", immediate=True)
        return self.current

    def _activate(self, body: dict[str, Any], env: dict[str, Any], kind: str,
                  *, immediate: bool) -> None:
        pol = Policy.from_dict({"wallet_policy": body})
        self.current = pol
        self.current_body = body
        self.history.append({
            "at": self._now(), "kind": kind if immediate else "pending",
            "signed_at": env.get("signed_at"), "signer": env.get("signer"),
            "policy_id": body.get("id"),
        })

    def _active_body(self) -> dict[str, Any]:
        return self.current_body or {}

    def is_pending_relaxation(self) -> bool:
        return self.pending_body is not None

    def evaluate(self, amount: float, host: str, *, now: Any = None):
        """Mevcut (sıkı) politika üzerinden karar — bekleyen gevşetme ASLA
        karar-vericiye sızmaz. Politika yoksa fail-closed deny."""
        self.tick()
        if self.current is None:
            from .policy import DENY, Decision

            return Decision(DENY, "fail-closed", "imzalı politika yüklü değil")
        return self.current.evaluate(amount, host, now=now)
