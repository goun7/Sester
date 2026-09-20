# SESTER — Metering, Quota, Fail-Closed Policy & Verifiable Receipts for AI-Agent APIs

<!-- v2 Chain-S markası (aday-E; potrace IoU 0.9924) — açık/koyu tema-uyumlu -->
<div align="left">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="brand/sester-mark-v2-dark.svg">
  <img src="https://raw.githubusercontent.com/goun7/Sester/main/.github/assets/avatar.png" alt="SESTER Chain-S mark" width="72" align="left">
</picture>
</div>

[![CI](https://github.com/goun7/Sester/actions/workflows/ci.yml/badge.svg)](https://github.com/goun7/Sester/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sester?color=gold)](https://pypi.org/project/sester/)
[![Python](https://img.shields.io/pypi/pyversions/sester)](https://pypi.org/project/sester/)
![License](https://img.shields.io/badge/license-Apache--2.0-gold)
![Deps](https://img.shields.io/badge/forced%20deps-0-success)
[![Discussions](https://img.shields.io/github/discussions/goun7/Sester?color=informational)](https://github.com/goun7/Sester/discussions)

<p align="center"><img src="https://raw.githubusercontent.com/goun7/Sester/main/.github/assets/og.png" alt="SESTER — metering · policy · evidence" width="640"></p>

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
# 0) Install (demo extras pull in FastAPI + uvicorn)
pip install "sester[demo]"

# 1) Start the demo API (port 8402)
uvicorn sester.demo_api:app --port 8402

# — or, one command with Docker —
# docker run --rm -p 8402:8402 ghcr.io/goun7/sester-demo:latest
```

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
| Observability | `GET /metrics` — Prometheus-text counters (requests, charges, replay/quota/rate 402s, chain-valid gauge) | dev |
| Burst limiting | Per-agent token-bucket (`burst_capacity`, `burst_refill_per_sec`) — independent of the daily quota | dev |
| Evidence webhooks | HMAC-signed delivery of charge/settlement events with receiver-side verification, retry+backoff, ledger failure-log | dev |
| Evidence export | External-verifier bundles — anyone can audit with `sha256` alone, no Sester installed | v0.3+ |

## Policy template bank

Copy a template, edit the limits, run. Every template is machine-locked by
`tests/test_policy_bank.py`: it must pass the DSL validator and carry at least
one allow rule plus one guardrail (deny/escalate).

| Template | Pattern | Key rules |
|---|---|---|
| [`examples/f1_policy.json`](examples/f1_policy.json) | human-escalation for large spends | `require-human-for-large` (escalate), `allow-demo-endpoints`, `deny-unknown-hosts` |
| [`examples/fleet_lane/policy.json`](examples/fleet_lane/policy.json) | business-hours fleet lane | `allow-telemetry` (`host_in` + `hour_between` 07:00–23:00), `deny-unknown-hosts` |
| [`examples/budget_guard_policy.json`](examples/budget_guard_policy.json) | tiered budget guard | two `amount_gt` thresholds — deny >10, escalate >1 — then host allowlist, then deny |

DSL conditions: `host_in` (empty list = catch-all), `hour_between`
(`["HH:MM","HH:MM"]`, wraps midnight), `amount_gt`. First match wins; no match
→ **deny** (fail-closed, `test_bank_template_validates`).

## Sister-product bridges (OSS adapter v0.1)

Sester does not merge with its sisters — it bridges them. `sester.bridges`
emits **receiver-independent** evidence envelopes; the counterpart verifies
**without importing Sester** (stdlib-only, the `dogrula.py` discipline):

| Bridge | Direction | Function | Receiver needs |
|---|---|---|---|
| **K1 · Tamga** | Sester → Tamga ledger | `tamga_anchor()` / `tamga_anchor_json()` | nothing but the anchor JSON |
| **K2 · Veridict** | Sester → Veridict jury | `veridict_claims()` / `veridict_claims_json()` | nothing but the claims JSON |

```python
from sester.bridges import tamga_anchor_json, veridict_claims_json, BRIDGE_VERSION

anchor = tamga_anchor_json(bundle)        # deterministic JSONL envelope
claims = veridict_claims_json(bundle)     # claim_id = sha256(task|summary|v)[:16]
```

Both bridges work on **public fields only** — non-custodial and
secretless-verifiability are preserved. `BRIDGE_VERSION` pins the wire
contract; receivers reject unknown versions (K0 §7 rule 2). Cross-repo CI
(`Cross-repo bridges` job) verifies both ends on every push.

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
                                        # payee registry, S6 joint acceptance — 260+ passing tests
                                        # (25 env-gated skips: PG/sibling-repos/external tools)
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
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Shipped by version, what's next, deliberate non-goals |
| Architecture decision records | Scope, doctrine, deliberate limits — see the repository's decision documents |
| Policy DSL specification | Semantics + test-vector discipline — see the repository's spec documents |
| Execution plan | Acceptance milestones (S1–S6) — see the repository's plan documents |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Hard rules for PRs (fail-closed, K0-frozen, test-first) |
| [`SECURITY.md`](SECURITY.md) | Reporting policy — replay/quota/signature-bypass bugs |

## Deliberate v0 limits

Non-goals by decision, not by omission (see the repository's decision records): transaction
signing stays out of the library (non-custodial — the signing party is yours),
live PSP certification is pending real-world traffic, and the CLI surface is
minimal by design. Everything else on the roadmap through v0.5.0 is implemented
and gated by the test suite above.

## Docker (zero-setup demo)

The demo API — 402 challenge, HMAC/EVM/UCP payment flows, live panel — ships as a
single image. All state lives in an isolated SQLite ledger inside the container;
mount a volume to keep receipts across restarts.

```bash
docker run --rm -p 8402:8402 ghcr.io/goun7/sester-demo:latest

# persistent ledger:
docker run --rm -p 8402:8402 -v "$PWD/ledger:/data" \
  -e SESTER_DEMO_LEDGER_DB=/data/sester-demo.sqlite3 \
  ghcr.io/goun7/sester-demo:latest
```

Then run the curl flow above against `http://127.0.0.1:8402`.

## Links

- **PyPI:** <https://pypi.org/project/sester/>
- **Changelog:** [`CHANGELOG.md`](CHANGELOG.md) · Release notes per version under
  [`docs/RELEASE_NOTES/`](docs/RELEASE_NOTES/)
- **Roadmap:** metrics / burst-limit / evidence webhooks shipped in v0.6.0;
  PSP adapters, optional transaction signing and hosted-traffic hardening are
  tracked in the repository's roadmap document
- **Discussions:** <https://github.com/goun7/Sester/discussions> — integration
  questions, protocol interop, evidence-bundle verification

## License

Apache-2.0 — see [`LICENSE`](LICENSE). The frozen wire fields
(`pugio0`, `pugio_bundle_version`, `source: "sikke"`) are kept for
receiver compatibility and are documented in the repository's identity-migration record; visual and
wire identity are separate layers.
