# SESTER — Metering, Quota, Fail-Closed Policy & Verifiable Receipts for AI-Agent APIs

![CI](https://github.com/goun7/sester/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-Apache--2.0-gold)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-informational)
![Deps](https://img.shields.io/badge/forced%20deps-0-success)

<p align="center"><img src=".github/assets/og.svg" alt="SESTER — metering · policy · evidence" width="640"></p>

> 🪙 **"If your agent is going to pay, you set the rules."**
> Sester plugs x402-style metering, quotas, fail-closed spend policy and a
> tamper-evident hash-chain receipt ledger into your API — as one ASGI
> middleware, with zero required dependencies.

**What it does, in one paragraph:** every paid request passes through a 402 →
payment → receipt handshake; spend is metered in integer minor units against
per-agent daily quotas; a fail-closed policy engine (host allow-lists, time
windows, escalation to human approval) decides *before* your handler runs; and
every decision and charge lands in a hash-chained ledger that third parties can
verify with nothing but `sha256`. Four agent-commerce protocols — **x402**,
**AP2**, **ACP**, **UCP** — compile onto one wire-format core
(`ChargeIntent`/`ChargeReceipt`), so adding a fifth protocol is one adapter, not
a rewrite.

## Why fail-closed matters

Sester is built on one doctrine: **every failure path denies spend**. A corrupt
policy file → `DENY_ALL`. An unknown payment scheme → 402. A tampered evidence
bundle → loud RED, never a receipt. A facilitator outage → 402, not a free call.
Silent fallbacks (`except: pass`) are treated as security bugs — the test suite
pins them. If you are metering money, "fail open" is not a mode, it is a leak.

## 3-minute demo

```bash
# 1) Start the demo API (port 8402)
uvicorn sester.demo_api:app --port 8402

# 2) Prepare a payment envelope (HMAC issuer)
python -m sester.demo_api --mac f1-telemetry:n1:0.05 /weather

# 3) Send the paid request (paste the envelope from step 2)
curl -H "X-Sester-Agent: f1-telemetry" \
     -H "X-Payment: pugio0 f1-telemetry:n1:0.05:<mac>" \
     "http://127.0.0.1:8402/weather?city=istanbul"

# 4) Open the panel: http://127.0.0.1:8402/panel
```

The flow: `curl` without payment → **402 + `X-Payment-Required` challenge**;
with payment → **200 + `X-Sester-Receipt`** evidence header; the 5th call →
**402 quota exceeded**; `/panel` shows who called, how much, and a live
chain-integrity badge.

## Feature map (by version)

| Area | What you get | Since |
|---|---|---|
| Metering middleware | x402-style 402 handshake, per-request pricing, quota in integer minor units | v0.1 |
| Policy engine | First-match DSL, host allow-lists, time windows, fail-closed defaults | v0.1 |
| Evidence ledger | Hash-chained SQLite (Postgres parity) receipts, HMAC-sealed, `verify_chain()` | v0.1 |
| Settlement | x402 v2 verify/settle facilitator with injectable transport, fail-closed on outage | v0.2 |
| Protocols | AP2 mandates (`AP2-Mandate`), ACP checkout sessions (`ACP-Session`), UCP web-monetization (`UCP-Checkout`) → one core | v0.2–0.4 |
| Human approval | `then: escalate` → 402 escalation ticket, one-time consumption, TTL expiry, `/approvals` panel | v0.2 |
| Signed mandates | RFC 7515 JWS: HS256 (stdlib) + ES256 (`[jws]`), body-binding, alg-allowlist | v0.3 |
| Signed policy | Owner-signed policy envelopes; tightening is instant, loosening is delayed 24 h | v0.3 |
| Postgres | Identical hash-chains across SQLite/PG (same secret + events → same head) | v0.3 |
| Migration | SQLite → PG hash-preserving replay, nonces preserved, `--plan/--dry-run/--verify` | v0.3.1 |
| On-chain batches | Pure-stdlib keccak-256, Merkle root recomputable in EVM, ABI `settle(...)` calldata, non-custodial | v0.4 |
| Minor-unit column | `amount_minor` with hash-preserving migration — quota decisions end-to-end integer | v0.4 |
| Hosted facilitator | FastAPI service: verify/settle/refund + seller metering (free band + 1% + $0.005) | v0.5 |
| Evidence export | External-verifier bundles — anyone can audit with `sha256` alone, no Sester installed | v0.3+ |

## Protocol adapters

| Protocol | Header | Envelope | Signature |
|---|---|---|---|
| x402 (HMAC compat) | `X-Payment` | `pugio0 agent:nonce:amount:mac` | HMAC-SHA256 |
| x402 v2 (EVM) | `X-Payment` | EIP-3009/EIP-712 exact scheme | wallet address = agent identity |
| AP2 | `AP2-Mandate` | base64 JWS mandate | HS256/ES256, body-binding |
| ACP | `ACP-Session` | base64 JWS checkout session | JWS + vendor-side issuing |
| UCP | `UCP-Checkout` | base64 JWS web-monetization | vendor-sealed, merchant-bound |

All four compile to the same `ChargeIntent`/`ChargeReceipt` core — one shared
wallet means one shared quota. Register your own via `register_scheme` /
`ProtocolAdapter`.

## Test suites & acceptance runs

```bash
.venv/bin/python -m pytest tests/ -q    # full suite: policy, ledger, middleware, EVM schemes,
                                        # evidence, facilitator, protocol adapters, escalation,
                                        # JWS, signed policy, UCP, settlement, minor units,
                                        # payee registry, S6 joint acceptance — 200+ test legs
python scripts/s1_dogfood.py            # S1 acceptance scenario → KABUL (accepted)
python scripts/dogrula.py adoption/s1-kanit-bundle.json   # receiver side — no Sester needed
```

> Cross-repo bridge tests (`tests/test_bridges_crossrepo.py`) run external
> evidence receivers end-to-end via subprocess (clean → ACCEPT, tampered →
> RED). They skip automatically when the counterpart repos are absent — the
> embedded pure-stdlib mirrors in `bridge_receivers/` pin the same wire
> contract in every run.

## Documentation

| Document | Contents |
|---|---|
| [`docs/K0_SHARED_ENVELOPE_SPEC.md`](docs/K0_SHARED_ENVELOPE_SPEC.md) | Shared evidence-envelope wire contract (external anchors, audit feeds) |
| [`KARAR_63B.md`](KARAR_63B.md) | Architecture decision record — scope, doctrine, deliberate limits |
| [`KURAL_DSL_V0.md`](KURAL_DSL_V0.md) | Policy DSL semantics + test-vector discipline |
| [`IS_PLANI.md`](IS_PLANI.md) | Execution plan with acceptance milestones (S1–S6) |
| [`docs/PUBLICATION_CHECKLIST.md`](docs/PUBLICATION_CHECKLIST.md) | Release gate — exactly what ships and what remains |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Hard rules for PRs (fail-closed, K0-frozen, test-first) |
| [`SECURITY.md`](SECURITY.md) | Reporting policy — replay/quota/signature-bypass bugs |

## Deliberate v0 limits

Non-goals by decision, not by omission (see `KARAR_63B.md`): transaction
signing stays out of the library (non-custodial — the signing party is yours),
live PSP certification is pending real-world traffic, and the CLI surface is
minimal by design. Everything else on the roadmap through v0.5.0 is implemented
and gated by the test suite above.

## License

Apache-2.0 — see [`LICENSE`](LICENSE). The frozen wire fields
(`pugio0`, `pugio_bundle_version`, `source: "sikke"`) are kept for
receiver compatibility and are documented in `ESKI_KIMLIK.md`; visual and
wire identity are separate layers.
