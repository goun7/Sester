"""SESTER schemes — x402 ödeme-şemaları.

exact-sester (v0.1, canlı):
  X-PAYMENT: base64url(JSON{scheme:"exact-sester", agent, nonce, amount, signature})
  signature  = EIP-191 kişisel-imza: keccak(EIP-191-prefix + b"agent|nonce|amount|resource")
  adres-türetme: eth_account.recover → agent == imzalayan adres (fail-closed).

exact (x402-uyum, iskelet):
  x402 v2 "exact" şeması: X-PAYMENT base64-JSON{scheme:"exact", x402Version,
  network:"eip155:*", resource, payload}. EIP-712 transferWithAuthorization
  EIP-3009 alanlarıyla kurulur (spec: docs.x402.org/schemes/exact + EIP-3009;
  teyit 2026-09-12). settle/verify facilitator'su, Settler kontratınatransferWithAuthorization;
  v0.1'de yalnız şema-dozu + alan-kontrolü — zincir-settle 'pending_settlement'
  permit-olayıyla ledger'a yazılır (architecture decision record v0.1 §bilinçli-sınırlar).
"""

from __future__ import annotations

import base64
import binascii
import json
import time
from dataclasses import dataclass
from typing import Any

try:
    from eth_account import Account
    from eth_account.messages import encode_defunct

    HAVE_ETH = True
except ImportError:  # pragma: no cover - eth-account opsiyonel bağımlılık
    HAVE_ETH = False


class PaymentError(Exception):
    """Ödeme-dozu reddi — middleware 402'ye çevirir."""


# ---------------------------------------------------------------- exact-sester

def sign_exact_sester(secret_key: str, agent: str, nonce: str, amount: str,
                      resource: str) -> str:
    """Ajan-tarafı: EIP-191 imzalayıp X-PAYMENT header-değerini üret."""
    if not HAVE_ETH:
        raise PaymentError("eth-account kurulu değil (pip install eth-account)")
    msg = f"{agent}|{nonce}|{amount}|{resource}".encode()
    signed = Account.sign_message(encode_defunct(msg), private_key=secret_key)
    recovered = Account.recover_message(encode_defunct(msg),
                                        signature=signed.signature)
    if recovered.lower() != str(agent).lower():
        # üretici-tarafı tutarlılık: imzalayan anahtar, agent-alanındaki adres değilse
        # zarf sunucuda doğrulama-ASLA geçmez — erken ve net patla (v0.4 düzeltmesi:
        # checksummed/lowercase asimetrisi saha-testinde 500-doğurmuştu)
        raise PaymentError(
            f"agent alanı imzalayan-adresle uyuşmuyor: {agent} ≠ {recovered}")
    payload = {
        "scheme": "exact-sester",
        "agent": agent.lower(),
        "nonce": nonce,
        "amount": amount,
        "signature": signed.signature.hex(),
    }
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"Sester-EVM {b64}"


def verify_exact_sester(header: str, resource: str,
                        *, now_ts: float | None = None) -> dict[str, Any]:
    """Sunucu-tarafı: dozu çöz, imzayı adresle doğrula. agent == imzalayan.
    nonce-replay + kota middleware'de (adres = cüzdan-kimliği)."""
    if not HAVE_ETH:
        raise PaymentError("eth-account kurulu değil")
    token = (header or "").strip()
    if not token.startswith("Sester-EVM "):
        raise PaymentError("şema-önekli değil")
    raw = token[len("Sester-EVM "):]
    try:
        padded = raw + "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except (binascii.Error, ValueError) as e:
        raise PaymentError("base64/JSON bozuk") from e
    if payload.get("scheme") != "exact-sester":
        raise PaymentError("scheme exact-sester değil")
    agent = str(payload.get("agent", ""))
    nonce = str(payload.get("nonce", ""))
    amount = str(payload.get("amount", ""))
    sig = payload.get("signature", "")
    if not agent or not nonce or not amount or not sig:
        raise PaymentError("alan eksik")
    try:
        recovered = Account.recover_message(
            encode_defunct(f"{agent}|{nonce}|{amount}|{resource}".encode()),
            signature=sig if sig.startswith("0x") else "0x" + sig,
        )
    except (ValueError, TypeError, binascii.Error) as e:
        raise PaymentError("imza-formatı bozuk") from e
    if recovered.lower() != agent.lower():
        raise PaymentError("imza agent-adresiyle uyuşmuyor")
    return {"agent": agent.lower(), "nonce": nonce, "amount": amount, "address": recovered}


# ---------------------------------------------------------------- x402 exact

EIP712_AUTH_DOMAIN = {"name": "TransferWithAuthorization", "version": "2"}

EIP712_AUTH_TYPES = {
    "EIP712Domain": [
        {"name": "name", "type": "string"}, {"name": "version", "type": "string"},
    ],
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"}, {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"}, {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"}, {"name": "nonce", "type": "bytes32"},
    ],
}

EIP712_AUTH_PRIMARY = "TransferWithAuthorization"


@dataclass
class ExactSesterV2:
    """x402 'exact' dozu (EVM): şema/alan-uyumu + yerel-imza-dogrulama.
    Zincir-settle facilitator'su (Settler kontratı) — v0.1'de pending-permit."""

    @staticmethod
    def encode_amount(amount_usd: float, decimals: int = 6) -> str:
        """USDC 6-decimal: 0.05 → '50000' minor-unit."""
        return str(int(round(amount_usd * (10 ** decimals))))

    @staticmethod
    def parse_payment_header(header: str, *, now_ts: float | None = None) -> dict[str, Any]:
        """x402 v2 exact: base64url(JSON{scheme, x402Version, network, resource, payload}).
        payload = EIP-3009 TransferWithAuthorization alanları + EIP-712 imza."""
        token = (header or "").strip()
        try:
            padded = token + "=" * (-len(token) % 4)
            envelope = json.loads(base64.urlsafe_b64decode(padded))
        except (binascii.Error, ValueError) as e:
            raise PaymentError("base64/JSON bozuk") from e
        if envelope.get("scheme") != "exact":
            raise PaymentError("scheme exact değil")
        if not str(envelope.get("network", "")).startswith("eip155:"):
            raise PaymentError("network eip155 değil")
        payload = envelope.get("payload") or {}
        required = ("from", "to", "value", "validAfter", "validBefore", "nonce", "signature")
        missing = [k for k in required if not payload.get(k)]
        if missing:
            raise PaymentError(f"EIP-3009 alan-eksik: {','.join(missing)}")
        vb = int(payload["validBefore"])
        if now_ts is not None and not (int(payload["validAfter"]) <= now_ts < vb):
            raise PaymentError("zaman-penceresi dışı")
        return envelope

    @staticmethod
    def client_header(*, from_addr: str, to_addr: str, amount_usd: float,
                      private_key: str, network: str = "eip155:84532",
                      valid_after: int | None = None, valid_before: int | None = None,
                      nonce_hex: str | None = None, x402_version: int = 2,
                      resource: str = "/weather") -> str:
        """Ajan-tarafı: EIP-712 transferWithAuthorization imzala + zarfla.
        (x402-uyum testleri ve ileride gerçek facilitator akışı için.)"""
        if not HAVE_ETH:
            raise PaymentError("eth-account kurulu değil")
        now = int(time.time())
        va = valid_after if valid_after is not None else now - 60
        vb = valid_before if valid_before is not None else now + 300
        nonce_hex = nonce_hex or ("0x" + "ab" * 32)
        if not nonce_hex.startswith("0x"):
            nonce_hex = "0x" + nonce_hex  # bytes32 encoding 0x-bekler
        value = ExactSesterV2.encode_amount(amount_usd)
        msgdata = {
            "types": EIP712_AUTH_TYPES,
            "primaryType": EIP712_AUTH_PRIMARY,
            "domain": EIP712_AUTH_DOMAIN,
            "message": {"from": from_addr, "to": to_addr, "value": value,
                        "validAfter": va, "validBefore": vb, "nonce": nonce_hex},
        }
        # eth-account signable_message ile EIP-712 imzası:
        from eth_account.messages import encode_typed_data

        signable = encode_typed_data(full_message=msgdata)
        signed = Account.sign_message(signable, private_key=private_key)
        envelope = {
            "scheme": "exact",
            "x402Version": x402_version,
            "network": network,
            "resource": resource,
            "payload": {
                "from": from_addr, "to": to_addr, "value": value,
                "validAfter": va, "validBefore": vb, "nonce": nonce_hex,
                "signature": signed.signature.hex(),
            },
        }
        b64 = base64.urlsafe_b64encode(json.dumps(envelope).encode()).decode().rstrip("=")
        return b64

    @staticmethod
    def verify_local(envelope: dict[str, Any]) -> str:
        """Yerel EIP-712 dogrulama (facilitator'suz): from == recovered."""
        if not HAVE_ETH:
            raise PaymentError("eth-account kurulu değil")
        payload = envelope["payload"]
        from eth_account.messages import encode_typed_data

        msgdata = {
            "types": EIP712_AUTH_TYPES,
            "primaryType": EIP712_AUTH_PRIMARY,
            "domain": EIP712_AUTH_DOMAIN,
            "message": {"from": payload["from"], "to": payload["to"],
                        "value": payload["value"], "validAfter": int(payload["validAfter"]),
                        "validBefore": int(payload["validBefore"]), "nonce": payload["nonce"]},
        }
        recovered = Account.recover_message(encode_typed_data(full_message=msgdata),
                                            signature=payload["signature"])
        if recovered.lower() != str(payload["from"]).lower():
            raise PaymentError("EIP-712 imza from-adresiyle uyuşmuyor")
        return recovered
