"""SESTER middleware — x402 el sıkışması + şema-kapısı + sayaç + kota (saf ASGI).

v0.2:
  · Karar-aritmetiği INTEGER minor-unit (6 dec): kota-kararı float-hatasız
    (0.30000000000000004 sınıfı imha edildi); saklama hâlâ gerçel — v0.3 kolon-göçü.
  · Replay-koruması KALICI: ledger.seen_nonces tablosu (restart pencere sıfırlamaz).
  · x402 `exact` (EIP-3009) zarfları: facilitator.verify → handler → settle →
    `settlement` olayı. Facilitator yok/erişilemez → fail-closed 402 (asla açık-kapı).

Akış (özet):
  X-PAYMENT yok → 402 challenge
  şemalar: "exact-sester" (EIP-191, yerel) | "pugio0" (HMAC geri-uyum, donuk) |
           "x402 <b64>" veya ham base64 zarf ("{..." ile başlarsa) → exact + facilitator
  → nonce (kalıcı) → kota (minor-int) → charge_receipt → handler
  (exact: settle → settlement olayı)
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from typing import Any

from .ledger import MINOR  # USDC 6-dec — tek-kaynak (v0.4: tam-sayı sayaç-kolonu)


class PaymentErr(Exception):
    """İç şema-çözümleme hatası (middleware-dahili)."""


class SesterMeter:
    """ASGI middleware: sarılan uygulamanın önünde ücretlendirme kapısı."""

    VERSION = "pugio0"            # HMAC şeması — DONUK kablo-alanı (identity-migration record)
    EVM_SCHEME = "exact-sester"   # EIP-191 imzalı ajan-kimliği

    def __init__(
        self,
        app: Any,
        ledger: Any,
        *,
        price: float = 0.05,
        daily_quota: float = 25.0,
        currency: str = "USDC-sim",
        secret: str = "dev-secret",
        pay_to: str = "sester:demo-seller",
        facilitator: Any | None = None,   # sester.facilitator.Facilitator (exact için)
        burst_capacity: float | None = None,
        burst_refill_per_sec: float | None = None,
        policy: Any | None = None,        # v0.7.2: Policy-DSL katmanı (None → atlanır)
        exempt_prefixes: tuple[str, ...] = (
            "/panel", "/healthz", "/agents.json", "/docs", "/openapi.json",
            "/redoc", "/favicon.ico", "/metrics",
        ),
    ) -> None:
        self.app = app
        self.ledger = ledger
        self.price_minor = int(round(float(price) * MINOR))
        self.quota_minor = int(round(float(daily_quota) * MINOR))
        self.price = self.price_minor / MINOR
        self.currency = currency
        self.secret = secret.encode()
        self.pay_to = pay_to
        self.facilitator = facilitator
        self.exempt_prefixes = exempt_prefixes
        # v0.6.0 adım-2: burst-limit (token-bucket; quota'dan bağımsız ikinci-kapı)
        # v0.7.2: artık kurucu-parametresi (None → eski-sabit-değer geri-döner)
        self.burst_capacity = 20 if burst_capacity is None else float(burst_capacity)
        self.burst_refill_per_sec = (10.0 if burst_refill_per_sec is None
                                    else float(burst_refill_per_sec))
        # v0.7.2: Policy-DSL katmanı — None ise-davranış-eskiyle-aynı.
        # Verildiğinde-ilk-eşleşen-kural-uygulanır (allow → normal-akış,
        # escalate → 402 + insan-onay, deny → 402 policy_denied).
        self.policy = policy
        self._buckets: dict[str, tuple[float, float]] = {}  # agent → (tokens, last_ts)
        self._metrics = {  # v0.6.0 adım-1: metering-metriği (0-bağımlılık sayaçlar)
            "requests_total": 0, "charges_total": 0, "replay_402_total": 0,
            "quota_402_total": 0, "rate_402_total": 0, "malformed_402_total": 0,
        }
        self._schemes: dict[str, Any] = {}
        self.register_scheme(self.VERSION, self._parse_hmac)       # "pugio0 ..."
        self.register_scheme("Sester-EVM", self._parse_evm)        # "Sester-EVM <b64>"
        self.register_scheme("x402", self._parse_exact)            # "x402 <b64 zarf>"
        self.register_scheme("exact", self._parse_exact)           # ham zarf da kabul

    # ---------- şema-kaydı ----------

    def register_scheme(self, prefix: str, parser) -> None:
        """Yeni ödeme-şeması takmak tek çağrı: ProtocolAdapter noktası."""
        self._schemes[prefix] = parser

    # ---------- yardımcılar ----------

    @staticmethod
    def _header(scope: dict, name: str) -> str | None:
        key = name.lower().encode()
        for k, v in scope.get("headers", []):
            if k == key:
                return v.decode("latin-1")
        return None

    def _mac(self, agent: str, nonce: str, amount_s: str, resource: str) -> str:
        msg = f"{agent}|{nonce}|{amount_s}|{resource}".encode()
        return hmac.new(self.secret, msg, hashlib.sha256).hexdigest()

    def _parse_hmac(self, header: str, resource: str) -> dict[str, Any]:
        token = header.strip()
        parts = token[len(self.VERSION) + 1:].split(":")
        if len(parts) != 4:
            raise PaymentErr("doz-formatı bozuk")
        agent, nonce, amount_s, mac = parts
        if not agent or not nonce or len(mac) != 64:
            raise PaymentErr("doz-alanları bozuk")
        expected = self._mac(agent, nonce, amount_s, resource)
        if not hmac.compare_digest(expected, mac.lower()):
            raise PaymentErr("HMAC uyuşmuyor")
        return {"agent": agent, "nonce": nonce, "amount": amount_s, "scheme": self.VERSION}

    def _parse_evm(self, header: str, resource: str) -> dict[str, Any]:
        from .schemes import PaymentError, verify_exact_sester

        try:
            info = verify_exact_sester(header, resource)
        except PaymentError as e:
            # fail-closed: bozuk/uyuşmayan EVM-imzası 500 değil 402 olmalı
            raise PaymentErr(f"EVM dozu reddedildi: {e}") from e
        return {"agent": info["agent"], "nonce": info["nonce"],
                "amount": info["amount"], "scheme": self.EVM_SCHEME}

    def _parse_exact(self, header: str, resource: str) -> dict[str, Any]:
        """x402 v2 exact zarfı: 'x402 <b64>' veya ham b64 (şema-önekli değil)."""
        token = header.strip()
        raw = token[len("x402 "):] if token.startswith("x402 ") else token
        try:
            padded = raw + "=" * (-len(raw) % 4)
            envelope = json.loads(base64.urlsafe_b64decode(padded))
        except (binascii.Error, ValueError, json.JSONDecodeError) as e:
            raise PaymentErr("exact zarfı base64/JSON bozuk") from e
        from .schemes import ExactSesterV2, PaymentError

        try:
            env = ExactSesterV2.parse_payment_header(
                base64.urlsafe_b64encode(json.dumps(envelope).encode()).decode().rstrip("=")
            )
            addr = ExactSesterV2.verify_local(env)
        except PaymentError as e:
            raise PaymentErr(f"exact zarfı reddedildi: {e}") from e
        value_minor = int(env["payload"]["value"])
        return {"agent": addr.lower(), "nonce": env["payload"]["nonce"],
                "amount_minor": value_minor, "envelope": env, "scheme": "exact"}

    async def _send_json(self, send, status: int, payload: dict, extra_headers: list | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        headers = [(b"content-type", b"application/json; charset=utf-8"),
                   (b"content-length", str(len(body)).encode())]
        for k, v in (extra_headers or []):
            headers.append((k.encode().lower(), v.encode()))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    def _challenge_payload(self, scope: dict, error: str) -> dict:
        return {
            "x402Version": 1,
            "error": error,
            "accepts": [
                {
                    "scheme": self.EVM_SCHEME,
                    "maxAmountRequired": f"{self.price:.6f}",
                    "currency": self.currency,
                    "resource": scope.get("path", ""),
                    "payTo": self.pay_to,
                    "extra": {
                        "sigHint": "EIP-191 personal_sign('agent|nonce|amount|resource'); agent = 0x-adres",
                        "agentHeader": "X-Sester-Agent (opsiyonel etiket)",
                    },
                },
                {
                    "scheme": self.VERSION,
                    "maxAmountRequired": f"{self.price:.6f}",
                    "currency": self.currency,
                    "resource": scope.get("path", ""),
                    "payTo": self.pay_to,
                    "extra": {
                        "sigHint": "HMAC-SHA256(secret, 'agent|nonce|amount|resource') — geri-uyum",
                        "agentHeader": "X-Sester-Agent",
                    },
                },
                {
                    "scheme": "exact",
                    "x402Version": 2,
                    "maxAmountRequired": f"{self.price:.6f}",
                    "currency": self.currency,
                    "resource": scope.get("path", ""),
                    "payTo": self.pay_to,
                    "extra": {
                        "sigHint": "EIP-3009 TransferWithAuthorization (EIP-712); facilitator verify/settle",
                        "facilitator": "required",
                    },
                },
            ],
        }

    async def _challenge(self, send, scope: dict, error: str) -> None:
        payload = self._challenge_payload(scope, error)
        b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        await self._send_json(send, 402, payload,
                              extra_headers=[("X-Payment-Required", b64)])

    # ---------- v0.6.0: burst-limit + metrics ----------

    def _burst_allow(self, agent: str) -> bool:
        """Token-bucket kapısı: fail-closed (token yoksa RED). Kota'dan bağımsız."""
        now = time.monotonic()
        tokens, last = self._buckets.get(agent,
                                         (float(self.burst_capacity), now))
        tokens = min(float(self.burst_capacity),
                     tokens + (now - last) * self.burst_refill_per_sec)
        if tokens < 1.0:
            self._buckets[agent] = (tokens, now)
            return False
        self._buckets[agent] = (tokens - 1.0, now)
        return True

    def _metrics_text(self) -> str:
        m = self._metrics
        chain = 1 if self.ledger.verify_chain() else 0
        lines = [
            "# HELP sester_requests_total metered requests seen (non-exempt)",
            "# TYPE sester_requests_total counter",
            f"sester_requests_total {m['requests_total']}",
            "# HELP sester_charges_total successful charge_receipt events",
            "# TYPE sester_charges_total counter",
            f"sester_charges_total {m['charges_total']}",
            "# HELP sester_replay_402_total replay-detected 402s",
            "# TYPE sester_replay_402_total counter",
            f"sester_replay_402_total {m['replay_402_total']}",
            "# HELP sester_quota_402_total quota-exceeded 402s",
            "# TYPE sester_quota_402_total counter",
            f"sester_quota_402_total {m['quota_402_total']}",
            "# HELP sester_rate_402_total burst/rate-limit 402s",
            "# TYPE sester_rate_402_total counter",
            f"sester_rate_402_total {m['rate_402_total']}",
            "# HELP sester_malformed_402_total malformed/unknown-scheme 402s",
            "# TYPE sester_malformed_402_total counter",
            f"sester_malformed_402_total {m['malformed_402_total']}",
            "# HELP sester_chain_valid ledger.verify_chain() — 1 sağlam, 0 kırık",
            "# TYPE sester_chain_valid gauge",
            f"sester_chain_valid {chain}",
        ]
        return "\n".join(lines) + "\n"

    # ---------- ana akış ----------

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        if any(path.startswith(p) for p in self.exempt_prefixes):
            if path == "/metrics":
                body = self._metrics_text().encode()
                await send({"type": "http.response.start", "status": 200,
                            "headers": [(b"content-type", b"text/plain; version=0.0.4"),
                                        (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
            return await self.app(scope, receive, send)
        self._metrics["requests_total"] += 1

        payment = self._header(scope, "X-Payment")
        if not payment:
            return await self._challenge(send, scope, "payment_required")

        prefix = payment.strip().split(" ", 1)[0]
        # Ham x402 zarfı (öneksiz base64, '{' ile başlayan JSON'un b64'ü) da kabul:
        if prefix not in self._schemes and prefix.startswith("ey"):
            prefix = "x402"
        parser = self._schemes.get(prefix)
        if parser is None:
            self.ledger.append("permission_decision", "bilinmeyen", path,
                               payload={"decision": "deny", "rule_id": "unknown_scheme"})
            return await self._challenge(send, scope, "unknown_scheme")

        try:
            parsed = parser(payment, path)
        except PaymentErr as e:
            self._metrics["malformed_402_total"] += 1
            self.ledger.append("permission_decision", "bilinmeyen", path,
                               payload={"decision": "deny", "rule_id": "malformed-payment",
                                        "detail": str(e)})
            return await self._challenge(send, scope, f"malformed_payment: {e}")

        agent = parsed["agent"]
        nonce = parsed["nonce"]
        # v0.6.0: burst-limit (quota'dan önce; imza-geçerli ajana uygulanır)
        if not self._burst_allow(agent):
            self._metrics["rate_402_total"] += 1
            self.ledger.append("permission_decision", agent, path,
                               payload={"decision": "deny", "rule_id": "rate_limited"})
            return await self._send_json(
                send, 402,
                {"error": "rate_limited", "agent": agent,
                 "burst_capacity": self.burst_capacity,
                 "refill_per_sec": self.burst_refill_per_sec,
                 "retry_after": 1},
            )
        # v0.7.2: Policy-DSL katmanı (varsa) — burst-sonrası, amount-öncesi.
        # İlk-eşleşen-kural: allow/escalate/deny. fail-closed: bozuk-politika
        # → deny-all (PolicyCorruptError-yakalanır).
        if self.policy is not None:
            from .policy import ALLOW, ESCALATE, PolicyCorruptError
            try:
                dec = self.policy.evaluate(self.price, path)
            except PolicyCorruptError:
                self.ledger.append("permission_decision", agent, path,
                                   payload={"decision": "deny",
                                            "rule_id": "policy_corrupt"})
                return await self._challenge(send, scope, "policy_corrupt")
            if dec.verdict == ESCALATE:
                self.ledger.append("escalation_parked", agent, path, 0.0,
                                   payload={"rule_id": dec.rule_id})
                return await self._challenge(
                    send, scope, f"escalation_required:{dec.rule_id}")
            if dec.verdict != ALLOW:
                self.ledger.append("permission_decision", agent, path,
                                   payload={"decision": "deny",
                                            "rule_id": dec.rule_id})
                return await self._challenge(
                    send, scope, f"policy_denied:{dec.rule_id}")

        amount_minor = parsed.get("amount_minor")
        if amount_minor is None:
            try:
                amount_minor = int(round(float(parsed["amount"]) * MINOR))
            except ValueError:
                return await self._challenge(send, scope, "malformed_payment: amount")
        if amount_minor < self.price_minor:
            self.ledger.append("permission_decision", agent, path,
                               payload={"decision": "deny", "rule_id": "amount_too_low",
                                        "offered_minor": amount_minor})
            return await self._challenge(send, scope, "amount_too_low")

        # x402 exact: facilitator.verify ŞART (fail-closed: unknown → ret)
        envelope = parsed.get("envelope")
        if parsed["scheme"] == "exact":
            if self.facilitator is None:
                self.ledger.append("permission_decision", agent, path,
                                   payload={"decision": "deny", "rule_id": "exact_needs_facilitator"})
                return await self._send_json(send, 402,
                                             {"error": "exact_requires_facilitator"})
            vr = self.facilitator.verify(envelope)
            if vr.status == "rejected":
                self.ledger.append("permission_decision", agent, path,
                                   payload={"decision": "deny", "rule_id": "facilitator_rejected",
                                            "detail": vr.reason})
                return await self._send_json(send, 402,
                                             {"error": "payment_rejected",
                                              "detail": vr.reason})
            if vr.status != "ok":  # unknown (ağ vb.) — fail-closed
                self.ledger.append("permission_decision", agent, path,
                                   payload={"decision": "deny", "rule_id": "facilitator_unknown",
                                            "detail": vr.reason})
                return await self._send_json(send, 402,
                                             {"error": "facilitator_unknown",
                                              "detail": "ödeme doğrulanamadı — fail-closed"})

        # Kalıcı replay-koruması: first-writer-wins (tablo restart'ı atlamaz)
        if not self.ledger.claim_nonce(agent, nonce):
            self._metrics["replay_402_total"] += 1
            self.ledger.append("permission_decision", agent, path,
                               payload={"decision": "deny", "rule_id": "replay"})
            return await self._challenge(send, scope, "replay_detected")

        # Kota: integer minor-unit kararı
        # v0.4: tam-sayı sayaç (kolondan); eski-arayüzlü ledger'lar için float-yol
        spent_minor = (self.ledger.spent_today_minor(agent)
                       if hasattr(self.ledger, "spent_today_minor")
                       else int(round(self.ledger.spent_today(agent) * MINOR)))
        if spent_minor + self.price_minor > self.quota_minor:
            self._metrics["quota_402_total"] += 1
            self.ledger.append("permission_decision", agent, path,
                               payload={"decision": "deny", "rule_id": "quota_exceeded",
                                        "spent_today_minor": spent_minor})
            return await self._send_json(
                send, 402,
                {"error": "quota_exceeded", "agent": agent,
                 "spent_today": spent_minor / MINOR, "daily_quota": self.quota_minor / MINOR,
                 "retry_after": "yerel-geceyarısı (günlük-kota sıfırlanır)"},
            )

        amount_real = self.price_minor / MINOR
        self._metrics["charges_total"] += 1
        rec = self.ledger.append("charge_receipt", agent, path, amount_real,
                                 amount_minor=self.price_minor,
                                 payload={"nonce": nonce, "paid": amount_real,
                                          "scheme": parsed["scheme"]})
        settle_once = {"done": False}

        async def send_with_receipt(message):
            if (message["type"] == "http.response.start"
                    and not getattr(send_with_receipt, "_stamped", False)):
                headers = list(message.get("headers", []))
                headers.append((b"x-sester-receipt", rec["hash"][:16].encode()))
                headers.append((b"x-sester-amount", f"{amount_real:.6f}".encode()))
                headers.append((b"x-sester-seq", str(rec["seq"]).encode()))
                message = {**message, "headers": headers}
                send_with_receipt._stamped = True  # type: ignore[attr-defined]
            await send(message)
            # exact: handler yanıtı başladıysa settle (bir kez) → settlement olayı
            if (parsed["scheme"] == "exact" and not settle_once["done"]
                    and message["type"] == "http.response.start" and self.facilitator):
                settle_once["done"] = True
                sr = self.facilitator.settle(envelope)
                if sr.status == "ok":
                    self.ledger.append("settlement", agent, path, amount_real,
                                       payload={"status": "settled",
                                                "receipt_seq": rec["seq"],
                                                "result": sr.raw})
                else:
                    self.ledger.append("settlement", agent, path, 0.0,
                                       payload={"status": "settle_failed",
                                                "receipt_seq": rec["seq"],
                                                "settle_status": sr.status,
                                                "detail": sr.reason})

        await self.app(scope, receive, send_with_receipt)
