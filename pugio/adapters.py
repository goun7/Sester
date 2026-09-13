"""PUGIO adapters — K4: AP2 mandate + ACP checkout-session → ChargeIntent/Receipt.

63-A mimari tezi (KAGIT §TUR): "Protokol-galibi riskine karşı tek çekirdek".
ChargeIntent (fiyat+kimlik+kanıt-istemi) ve ChargeReceipt (ödeme-kanıtı) K0
ortak-zarfı soyutlamasıdır; her protokol bunlara çevrilir. Bu modül iki
protokolün çekirdek-akışını *yerel* taklit eder:

  AP2 (Agent Payments Protocol — Google → FIDO Alliance, Nis 2026):
    "mandate" = kullanıcı, ajanın bir harcama-yetkisini imzalamıştır.
    Auth:     "AP2-Mandate <b64(mandate)>"
    Mandate:  {mandate_id, agent (cüzdan-adresi), principal (kullanıcı),
               scope: {resource_prefixes, per_request_max_minor, currency,
                       valid_from, valid_to}, signature: <JWS-compact>}
    Doğrulama: verify_ap2_mandate — scope, pencere, para-birimi, tutar;
    imza: `signature` alanı JWS-compact (RFC 7515). Üretimde `key_resolver`
    ŞART: HS256 (stdlib) veya ES256 (opsiyonel `cryptography`) ile
    doğrulanır; resolver'sız kurulumda imza yalnız form-bağlamı yapılır
    (v0.2 uyumu — KARAR_63B: bilinçli v0.3 geçişi).

  ACP (Agentic Commerce Protocol — Stripe+OpenAI, Eyl 2025):
    "checkout_session" = satıcı-oturumu, ajan bakiyesinden tek-çekim.
    Auth:     "ACP-Session <b64(session)>"
    Session:  {session_id, buyer (cüzdan-adresi), line_item: {resource,
               amount_minor, currency}, valid_to}

Her iki adaptör de şema-Registry'sine takılır: başlık-önekinden
ChargeIntent üretir. Ortak kural: ajan-kimliği = cüzdan-adresi
(non-custodial tez), nonce = mandate_id / session_id (kalıcı
replay-koruması), kanıt = hash-chain'li charge_receipt olayı.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

# key_resolver(kid, alg) -> anahtar (HS256: bytes-secret; ES256: PEM-public-bytes)
KeyResolver = Callable[[str | None, str], Any]

JWS_SUPPORTED_ALGS = ("HS256", "ES256")


class AdapterError(Exception):
    """AP2/ACP zarfı bozuk, pencere-dışı ya da scope-dışı — ret."""


class SignatureRequiredError(AdapterError):
    """Zarf form-geçerli ama imzası doğrulanmadı (key_resolver yok/başarısız) —
    production bayrağıyla zorunlu tutulur (fail-closed)."""


# ------------------------------------------------------------------ b64url (JWS)

def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64u_decode(seg: str) -> bytes:
    padded = seg + "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(padded)


# ------------------------------------------------------------------ K0 çekirdek

@dataclass(frozen=True)
class ChargeIntent:
    """K0 §2: fiyat + kimlik + kanıt-istemi — protokol-nötr harcama-niyeti."""
    agent: str            # cüzdan-adresi (non-custodial tez)
    resource: str
    amount_minor: int     # integer minor-unit (v0.2 aritmetik-kuralı)
    currency: str
    nonce: str            # mandate_id / session_id / imza-nonce
    protocol: str         # "ap2" | "acp" | "pugio0" | "exact-pugio" | "exact"
    principal: str = ""   # AP2: imzalayan kullanıcı (boşsa ajan kendisi)
    raw: dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class ChargeReceipt:
    """K0 §2: ödeme-kanıtı — ledger'a charge_receipt olarak yazılır."""
    intent: ChargeIntent
    paid_minor: int
    currency: str
    receipt_hash: str     # ledger hash-chain halkası (tamga-köprüsü)


def _sign_object(obj: dict[str, Any], *, alg: str, key: Any,
                 kid: str | None = None) -> str:
    """Nesnenin 'signature' ALANI DIŞINDAKİ her alanını JWS ile mühürler
    (imza-yuvası çıkarılır → deterministik, tekrar-üretilebilir payload)."""
    body = {k: v for k, v in obj.items() if k != "signature"}
    return sign_mandate_jws(body, alg=alg, key=key, kid=kid)


def _b64_json(header: str, prefix: str) -> dict[str, Any]:
    tok = header.strip()
    if not tok.startswith(prefix + " "):
        raise AdapterError(f"başlık {prefix} önekiyle değil")
    raw = tok[len(prefix) + 1:]
    try:
        padded = raw + "=" * (-len(raw) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except (binascii.Error, ValueError, json.JSONDecodeError) as e:
        raise AdapterError(f"zarf base64/JSON bozuk: {e}") from e


def _check_window(obj: dict[str, Any], now: float | None) -> None:
    now = time.time() if now is None else now
    vf = obj.get("valid_from")
    vt = obj.get("valid_to")
    if vf is not None and now < float(vf):
        raise AdapterError("yetki henüz başlamadı (valid_from)")
    if vt is not None and now > float(vt):
        raise AdapterError("yetki süresi doldu (valid_to)")


# ------------------------------------------------------------------ JWS (RFC 7515)

def sign_mandate_jws(mandate_body: dict[str, Any], *, alg: str, key: Any,
                     kid: str | None = None) -> str:
    """JWS-compact üretimi (test/üretici tarafı): payload = mandate-gövdesi.
    HS256: key = bytes; ES256: key = PEM-private-bytes (cryptography gerekir)."""
    if alg not in JWS_SUPPORTED_ALGS:
        raise AdapterError(f"desteklenmeyen alg: {alg}")
    hdr = {"alg": alg, "typ": "JWS"}
    if kid:
        hdr["kid"] = kid
    signing_input = (_b64u_encode(json.dumps(hdr, sort_keys=True).encode())
                     + "." + _b64u_encode(json.dumps(mandate_body, sort_keys=True).encode()))
    if alg == "HS256":
        mac = hmac.new(key if isinstance(key, bytes) else str(key).encode(),
                       signing_input.encode(), hashlib.sha256).digest()
        return signing_input + "." + _b64u_encode(mac)
    # ES256 — opsiyonel cryptography
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import (
            decode_dss_signature,
            encode_dss_signature,
        )
    except ImportError as e:  # pragma: no cover - kurulum-bağımlı
        raise AdapterError("ES256 için 'cryptography' gerekir: pip install 'pugio-meter[jws]'") from e
    try:
        priv = serialization.load_pem_private_key(key, password=None)
        der = priv.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        return signing_input + "." + _b64u_encode(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    except Exception as e:
        raise AdapterError(f"ES256 imza-üretimi başarısız: {e}") from e


def verify_mandate_jws(jws_compact: str, *, resolve_key: KeyResolver,
                       expected_body: dict[str, Any] | None = None) -> dict[str, Any]:
    """JWS-compact doğrulaması — fail-closed: her hata AdapterError.
    expected_body verilirse JWS-payload ile zarf-gövdesinin bağlandığı
    alanlar (mandate_id, agent, principal, scope) birebir aynı olmalı."""
    try:
        hdr_seg, pay_seg, sig_seg = jws_compact.strip().split(".")
    except ValueError as e:
        raise AdapterError("JWS compact 3-segmentli değil") from e
    try:
        hdr = json.loads(_b64u_decode(hdr_seg))
        payload = json.loads(_b64u_decode(pay_seg))
    except (binascii.Error, ValueError, json.JSONDecodeError) as e:
        raise AdapterError(f"JWS header/payload bozuk: {e}") from e
    alg = hdr.get("alg")
    if alg not in JWS_SUPPORTED_ALGS:
        raise AdapterError(f"JWS alg reddedildi: {alg!r} (desteklenen: {JWS_SUPPORTED_ALGS})")
    signing_input = f"{hdr_seg}.{pay_seg}".encode()
    sig = _b64u_decode(sig_seg)
    key = resolve_key(hdr.get("kid"), alg)
    if key is None:
        raise AdapterError(f"anahtar çözülemedi: kid={hdr.get('kid')!r}")

    if alg == "HS256":
        secret = key if isinstance(key, bytes) else str(key).encode()
        expect = hmac.new(secret, signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expect, sig):
            raise AdapterError("JWS imzası uyuşmuyor (HS256)")
    else:  # ES256
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        except ImportError as e:  # pragma: no cover
            raise AdapterError("ES256 için 'cryptography' gerekir") from e
        if len(sig) != 64:
            raise AdapterError("ES256 imzası 64-byte r||s değil")
        r, s = int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big")
        try:
            pub = serialization.load_pem_public_key(key)
            pub.verify(encode_dss_signature(r, s), signing_input,
                       ec.ECDSA(hashes.SHA256()))
        except (InvalidSignature, ValueError, TypeError) as e:
            raise AdapterError("JWS imzası uyuşmuyor (ES256)") from e

    if expected_body is not None:
        # tam gövde-bağı: zarfta bulunan HER alan JWS-payload ile birebir
        # (AP2: mandate_id/agent/principal/scope; ACP: session_id/buyer/
        # line_item/pencereler) — kazıma + geçerli-imza ret edilir
        for k, v_expect in expected_body.items():
            if payload.get(k) != v_expect:
                raise AdapterError(f"JWS-payload zarf-gövdesiyle uyuşmuyor: {k}")
    return payload


# ------------------------------------------------------------------ AP2 mandate

@dataclass(frozen=True)
class Ap2Mandate:
    """AP2 mandate zarfı — kullanıcının ajana verdiği imzalı harcama-yetkisi."""
    mandate_id: str
    agent: str
    principal: str
    scope: dict[str, Any]
    signature: str        # JWS-compact (RFC 7515)
    raw: dict[str, Any]

    @classmethod
    def parse(cls, header: str) -> "Ap2Mandate":
        obj = _b64_json(header, "AP2-Mandate")
        for k in ("mandate_id", "agent", "principal", "scope", "signature"):
            if not obj.get(k):
                raise AdapterError(f"mandate.{k} eksik")
        scope = obj["scope"]
        if not isinstance(scope, dict):
            raise AdapterError("mandate.scope nesne değil")
        return cls(
            mandate_id=str(obj["mandate_id"]),
            agent=str(obj["agent"]).lower(),
            principal=str(obj["principal"]),
            scope=scope,
            signature=str(obj["signature"]),
            raw=obj,
        )

    def authorize(self, resource: str, amount_minor: int, currency: str,
                  *, now: float | None = None) -> ChargeIntent:
        """Mandate scope'una göre ChargeIntent üretir; scope-dışı → AdapterError."""
        _check_window(self.raw, now)
        prefixes = self.scope.get("resource_prefixes", [])
        res = (resource or "").lower()
        if not any(res.startswith(str(p).lower()) for p in prefixes):
            raise AdapterError(f"kaynak mandate-kapsamı dışı: {resource}")
        prm = int(self.scope.get("per_request_max_minor", 0))
        if amount_minor > prm:
            raise AdapterError(f"tutar mandate üst-sınırı aşıyor: {amount_minor} > {prm}")
        cur = str(self.scope.get("currency", "USDC"))
        if currency and currency != cur:
            raise AdapterError(f"para-birimi uyuşmuyor: {currency} ≠ {cur}")
        return ChargeIntent(
            agent=self.agent, resource=resource, amount_minor=amount_minor,
            currency=cur, nonce=self.mandate_id, protocol="ap2",
            principal=self.principal, raw=self.raw,
        )

    def verify(self, *, resolve_key: KeyResolver | None = None) -> None:
        """JWS-dogrulama. resolve_key verilirse tam-kripto (HS256/ES256);
        verilmezse yalnız form-bağlamı (v0.2 uyumu — üretimde resolver ŞART)."""
        if resolve_key is None:
            if len(self.signature) < 16:
                raise AdapterError("mandate imzası formda değil")
            return
        verify_mandate_jws(
            self.signature, resolve_key=resolve_key,
            expected_body={k: v for k, v in self.raw.items() if k != "signature"},
        )


def verify_ap2_mandate(header: str, resource: str, amount_minor: int,
                       currency: str = "USDC", *, now: float | None = None,
                       resolve_key: KeyResolver | None = None
                       ) -> ChargeIntent:
    """AP2 başlığı → ChargeIntent (yetki-kapsamı + imza doğrulanmış)."""
    m = Ap2Mandate.parse(header)
    m.verify(resolve_key=resolve_key)
    return m.authorize(resource, amount_minor, currency, now=now)


# ------------------------------------------------------------------ ACP session

@dataclass(frozen=True)
class AcpSession:
    """ACP checkout_session zarfı — satıcı-oturumu, tek-çekim bakiye-çekimi.
    v0.3.1: satıcı-tarafı imza — `signature` alanı JWS-compact; tam zarfın
    (imza-yuvası hariç) mührü. Üretici: `issue_acp_session` (satıcı-sırası)."""
    session_id: str
    buyer: str
    line_item: dict[str, Any]
    signature: str = ""     # satıcı-JWS (boş = imzasız eski-zarf)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, header: str) -> "AcpSession":
        obj = _b64_json(header, "ACP-Session")
        for k in ("session_id", "buyer", "line_item"):
            if not obj.get(k):
                raise AdapterError(f"session.{k} eksik")
        if not isinstance(obj["line_item"], dict):
            raise AdapterError("session.line_item nesne değil")
        return cls(
            session_id=str(obj["session_id"]),
            buyer=str(obj["buyer"]).lower(),
            line_item=obj["line_item"],
            signature=str(obj.get("signature", "")),
            raw=obj,
        )

    def authorize(self, resource: str, *, now: float | None = None) -> ChargeIntent:
        """Oturumun tek line_item'ı bu kaynağa değilse ret."""
        _check_window(self.raw, now)
        li = self.line_item
        if str(li.get("resource", "")).lower() != (resource or "").lower():
            raise AdapterError("line_item kaynağı istenen kaynak değil")
        try:
            amount_minor = int(li["amount_minor"])
        except (KeyError, TypeError, ValueError) as e:
            raise AdapterError("line_item.amount_minor bozuk") from e
        if amount_minor <= 0:
            raise AdapterError("line_item.amount_minor pozitif olmalı")
        return ChargeIntent(
            agent=self.buyer, resource=resource, amount_minor=amount_minor,
            currency=str(li.get("currency", "USDC")), nonce=self.session_id,
            protocol="acp", raw=self.raw,
        )

    def verify(self, *, resolve_key: KeyResolver | None = None,
               require_signature: bool = False) -> None:
        """Satıcı-imzası doğrulaması. İmzasız eski-zarf: yalnız
        require_signature=False'ta kabul (v0.2 geri-uyum); imzalıysa JWS
        tam-gövde-bağı (expected_body=imza-yuvası-hariç zarf)."""
        if not self.signature:
            if require_signature:
                raise SignatureRequiredError("ACP session imzasız — production reddi")
            return
        if resolve_key is None:
            if require_signature:
                raise SignatureRequiredError("key_resolver yok — imza doğrulanamadı")
            return
        verify_mandate_jws(
            self.signature, resolve_key=resolve_key,
            expected_body={k: v for k, v in self.raw.items() if k != "signature"},
        )


def issue_acp_session(*, session_id: str, buyer: str, resource: str,
                      amount_minor: int, currency: str = "USDC",
                      ttl_seconds: float = 3600.0, alg: str = "HS256",
                      key: Any = None, kid: str | None = None,
                      valid_from: float | None = None) -> str:
    """Satıcı-tarafı üretici: imzalı ACP-Session başlığı döndürür.
    key=None → imzasız (v0.2 uyum / iç-dogfood)."""
    t = time.time() if valid_from is None else valid_from
    obj: dict[str, Any] = {
        "session_id": session_id,
        "buyer": buyer.lower(),
        "valid_from": t,
        "valid_to": t + ttl_seconds,
        "line_item": {"resource": resource, "amount_minor": int(amount_minor),
                      "currency": currency},
    }
    if key is not None:
        obj["signature"] = _sign_object(obj, alg=alg, key=key, kid=kid)
    raw = base64.urlsafe_b64encode(json.dumps(obj, sort_keys=True).encode()
                                   ).decode().rstrip("=")
    return f"ACP-Session {raw}"


def verify_acp_session(header: str, resource: str, *, now: float | None = None,
                       resolve_key: KeyResolver | None = None,
                       require_signature: bool = False) -> ChargeIntent:
    """ACP başlığı → ChargeIntent (kaynak/tutar + imza-politikası doğrulanmış)."""
    s = AcpSession.parse(header)
    s.verify(resolve_key=resolve_key, require_signature=require_signature)
    return s.authorize(resource, now=now)


# ------------------------------------------------------------------ registry

def install_adapters(register_scheme: Any, *, price_minor: int,
                     on_intent: Any | None = None,
                     currency: str = "USDC",
                     key_resolver: KeyResolver | None = None,
                     require_acp_signature: bool = False) -> None:
    """İki protokolü middleware şema-Registry'sine takar.

    register_scheme(prefix, parser) — middleware'in mevcut kayıt-noktası;
    parser(header, resource) → parsed-dict (middleware sözleşmesi:
    agent/nonce/amount_minor/scheme). price_minor = satıcı-fiyatı
    (middleware.price_minor) — tutar-benchmark tek-kaynak.
    on_intent(intent) — protokol-niyeti olayı; PUGIO'da
    `ledger.append("protocol_intent", ...)`.
    key_resolver — AP2 JWS doğrulaması (üretimde ŞART; None → form-bağlamı).
    require_acp_signature — ACP oturum-imzasını zorunlu tutar (üretim: True);
    satıcı-ucu üretici: issue_acp_session.

    Yerel-değerlendirme: AP2 scope'u zaten 'mandate-cüzdan-kuralı'dır
    (63-A: "AP2 müşteride mandate birincil"); harici çağrı YOK — fail-closed
    ağ-bağımlılığı yalnız x402 exact/facilitator hattında kalır.
    """
    from .middleware import PaymentErr

    def _ap2(header: str, resource: str) -> dict[str, Any]:
        try:
            m = Ap2Mandate.parse(header)
            m.verify(resolve_key=key_resolver)
            intent = m.authorize(resource, price_minor, currency)
        except AdapterError as e:
            raise PaymentErr(f"AP2 mandate reddedildi: {e}") from e
        if on_intent:
            on_intent(intent)
        return {"agent": intent.agent, "nonce": intent.nonce,
                "amount_minor": intent.amount_minor, "scheme": "ap2",
                "intent": intent}

    def _acp(header: str, resource: str) -> dict[str, Any]:
        try:
            s = AcpSession.parse(header)
            s.verify(resolve_key=key_resolver,
                     require_signature=require_acp_signature)
            intent = s.authorize(resource)
        except AdapterError as e:
            raise PaymentErr(f"ACP session reddedildi: {e}") from e
        if intent.amount_minor < price_minor:
            raise PaymentErr("ACP line_item tutar satıcı-fiyatının altında")
        if on_intent:
            on_intent(intent)
        return {"agent": intent.agent, "nonce": intent.nonce,
                "amount_minor": intent.amount_minor, "scheme": "acp",
                "intent": intent}

    register_scheme("AP2-Mandate", _ap2)
    register_scheme("ACP-Session", _acp)


def protocol_intent_event(intent: ChargeIntent) -> dict[str, Any]:
    """ChargeIntent → ledger olay-payload'ı (tamga-uyumlu şema)."""
    return {
        "protocol": intent.protocol,
        "intent_id": intent.nonce,
        "agent": intent.agent,
        "resource": intent.resource,
        "amount_minor": intent.amount_minor,
        "currency": intent.currency,
        "principal": intent.principal,
    }
