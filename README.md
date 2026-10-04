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
![License](https://img.shields.io/badge/license-Apache--2.0--OR--AGPL--3.0-gold)
![Deps](https://img.shields.io/badge/forced%20deps-0-success)
[![Discussions](https://img.shields.io/github/discussions/goun7/Sester?color=informational)](https://github.com/goun7/Sester/discussions)

<p align="center"><img src="https://raw.githubusercontent.com/goun7/Sester/main/.github/assets/og.png" alt="SESTER — metering · policy · evidence" width="640"></p>

> 🪙 **"If your agent is going to pay, you set the rules."**
> Sester plugs x402-style metering, quotas, fail-closed spend policy and a
> tamper-evident hash-chain receipt ledger into your API — as one ASGI
> middleware, with zero required dependencies.

**`pip install sester`** · 649 downloads (mirrors excluded) · 528 tests (9 skipped, LEAD-verified 2026-10-03) · 0 forced deps

## Quick start

```python
from fastapi import FastAPI
from sester import SesterMeter

app = FastAPI()
app.add_middleware(
    SesterMeter,
    ledger="receipts.db",          # tamper-evident hash-chain ledger
    secret="your-server-secret",   # signs dose envelopes
    pay_to="0xYourTreasury",       # where agents pay (USDC)
    price=0.001,                   # price per paid call
    daily_quota=100,               # free daily quota per agent
    exempt_prefixes=("/healthz", "/docs"),
)

@app.get("/paid")
def paid():
    return {"data": "this call cost the agent $0.001"}
```

Agents pay with a signed dose envelope (EIP-191 personal_sign); the
middleware verifies, deducts from quota, and appends a receipt.
No payment, no response — **fail-closed by design**.

```
Agent ──(X-Payment: signed dose)──▶ SesterMeter ──▶ your route
                                      │  verify · deduct · receipt
                                      ▼
                              hash-chain ledger (SQLite)
```


**What it does, in one paragraph:** every paid request passes through a 402 →
payment → receipt handshake; spend is metered in integer minor units against
per-agent daily quotas; a fail-closed policy engine (host allow-lists, time
windows, escalation to human approval) decides *before* your handler runs; and
every decision and charge lands in a hash-chained ledger that third parties can
verify with nothing but `sha256`. Four agent-commerce protocols — **x402**,
**AP2**, **ACP**, **UCP** — compile onto one wire-format core
(`ChargeIntent`/`ChargeReceipt`), so adding a fifth protocol is one adapter, not
a rewrite.

> **A2A uyumluluğu (2026-10):** Google'ın resmi [A2A x402 Extension](https://github.com/google-agentic-commerce/a2a-x402)
> spesifikasyonu (v0.1) ile uyumlu akış. Sester'ın insan-onay kuyruğu
> (`escalation`), A2A ödeme akışına **human-in-the-loop** katar:
> `Payment Required → [Sester: insan onayı] → Payment Submitted → Payment Completed`.
> Agent'lar arası ticarette büyük tutarlar için insan onayı standart hale geliyor.

> **Post-settlement accountability (2026-10):** x402'nin en sıcak tartışması
> [#2332](https://github.com/x402-foundation/x402/issues/2332) (211+ yorum)
> tam olarak Sester'ın çözdüğü boşluk: `payment_hash` ödemenin tamamlandığını
> kanıtlar ama **agent'ın ödedikten sonra ne yaptığını kanıtlamaz**.
> **EU AI Act Madde 12** (2 Aralık 2027, Annex III) otomatik loglama zorunlu
> kılıyor — ama logların nasıl korunduğunu veya kimin doğrulayacağını söylemiyor.
> **Loglar yeniden yazılabilir; hash-chain anchor olamaz.** Sester'ın
> tamper-evident ledger'ı bu harici anchor'dur: üçüncü taraflar
> (regülatör, denetçi, karşı taraf) yalnızca `sha256` ile bağımsız doğrular.

## 30 seconds: what is this?

**Sester is a payment-metering + receipt layer for APIs that AI agents call.**
It does not move funds (non-custodial). It does three concrete things:

1. **402 gate** — every paid request must present a valid payment envelope or
   the request is rejected (fail-closed, never "free on error").
2. **Spend rules** — per-agent daily quotas, per-request price caps, host
   allow-lists, burst limits, human-escalation for large spends.
3. **Verifiable receipts** — every charge lands in a hash-chained ledger and
   yields a **receipt that anyone can verify with `sha256` alone**, no Sester
   installed, no secrets. This is the piece the x402 ecosystem is missing:
   a facilitator can say "paid", but without a receipt the receiver cannot
   *prove* it (USENIX Security 2026 found rule violations in all 15 major
   x402 facilitators — see [`docs/arastirma/`](docs/arastirma/)).

Zero required dependencies (pure stdlib ASGI middleware). Try it for **$0** —
local embedded ledger, no keys, no testnet:

```bash
pip install "sester[demo]"
uvicorn sester.demo_api:app --port 8402          # paid API up
python -m sester.demo_api --mac agent-1:n1:0.05 /weather
curl -H "X-Sester-Agent: agent-1" \
     -H "X-Payment: <envelope-from-above>" \
     "http://127.0.0.1:8402/weather?city=istanbul"   # 200 + X-Sester-Receipt
```

And the proof layer (no server needed at all):

```bash
export SESTER_LEDGER_DB=/tmp/l.sqlite3 SESTER_LEDGER_SECRET=demo
# (in your app, a charge already happened — produce its receipt:)
sester receipt 1 --out receipt.json
# ...hand receipt.json to a third party. They verify WITHOUT Sester:
sester verify receipt.json                          # KABUL (rc=0) / RED (rc=1)
```

An auditor who wants everything in one file rather than a single receipt can
export the whole ledger for one agent:

```bash
sester bundle --agent demo-agent --out bundle.json   # full evidence export
```

The bundle is self-contained — receipts plus the ledger chain segment the
agent participated in — so it can be re-verified later without the live
ledger.

AI agents can do both through an MCP server (Model Context Protocol
2025-06-18) — [`mcp/`](mcp/README.md): `pay`, `verify_receipt`, `balance`,
`history`.



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

Since v0.7.4 the paid 200 also carries `X-Sester-Receipt-Bundle` — a base64
**node-cosigned receipt** the caller can hand to a third party who verifies it
without Sester:

```bash
# 5) (optional) cosign the demo receipts; the default is cosign-free but
#    the receipt's `proof` is still independently verifiable with sha256 alone
export SESTER_DEMO_NODE_SECRET=demo-node-key
# restart uvicorn, redo the paid call, then:
curl -s -D - -o /dev/null -H "X-Sester-Agent: agent-1" \
     -H "X-Payment: $PAY" "http://127.0.0.1:8402/weather" \
  | grep -i 'receipt-bundle:' | cut -d' ' -f2 | base64 -d > receipt.json
sester verify receipt.json          # KABUL (rc=0) — receiver-side, zero deps
```

## Use it in your own app (one middleware)

```python
from sester import SesterMeter, Policy, Ledger

policy = Policy.from_dict({
    "wallet_policy": {
        "id": "my-api",
        "defaults": {
            "per_request_max": 0.10,       # one call cannot cost more than 10¢
            "daily_max": 5.00,             # ...and one agent cannot pass $5/day
        },
        "rules": [
            {"id": "allow-telemetry", "when": {"host_in": ["/telemetry"]}, "then": "allow"},
            {"id": "approve-large",   "when": {"amount_gt": 0.05}, "then": "escalate"},
            {"id": "deny-rest",       "when": {"host_in": []},     "then": "deny"},
        ],
    }
})

meter = SesterMeter(
    app=your_asgi_app,
    ledger=Ledger("usage.sqlite3", secret=SESTER_SECRET),
    policy=policy,
    price=0.01,                        # per-request price in major units
    burst_capacity=20,                 # optional: token-bucket second gate
    burst_refill_per_sec=10.0,
)
# any ASGI server: uvicorn your_module:meter
```

That one wrapper gives you: the 402 handshake, per-request pricing, the
integer-minor-unit quota, first-match-wins policy evaluation with a
fail-closed default, burst limiting independent of the daily quota, and the
hash-chained receipt ledger that any third party can verify with `sha256`
alone (see `docs/K0_SHARED_ENVELOPE_SPEC.md`). Escalation rules open a
human-approval ticket instead of denying outright (`then: "escalate"`).

## Feature map (by versions)

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
| Observability | `GET /metrics` — Prometheus-text counters (requests, charges, replay/quota/rate 402s, chain-valid gauge) | v0.6 |
| Burst limiting | Per-agent token-bucket (`burst_capacity`, `burst_refill_per_sec`) — independent of the daily quota | v0.6 |
| Evidence webhooks | HMAC-signed delivery of charge/settlement events with receiver-side verification, retry+backoff, ledger failure-log | v0.6 |
| Meter package | Single public import — `from sester import SesterMeter, Policy, Ledger, ...`; `__all__` is the locked surface | v0.7.2 |
| Evidence export | External-verifier bundles — anyone can audit with `sha256` alone, no Sester installed | v0.3+ |
| **Payment receipts** | **Node-cosigned receipt per charge: `proof` recomputable with `sha256` only; `sester verify` is the standalone receiver-side CLI** | **v0.7.4** |
| **CLI** | **`sester verify \| receipt \| history \| bundle` — receiver-side proof verification with zero deps installed** | **v0.7.4** |
| **MCP server** | **AI agents pay and verify receipts: `pay`, `verify_receipt`, `balance`, `history` (MCP 2025-06-18, stdio, stdlib)** | **v0.7.4** |

## Policy template bank

Copy a template, edit the limits, run. Every template is machine-locked by
`tests/test_policy_bank.py`: it must pass the DSL validator and carry at least
one allow rule plus one guardrail (deny/escalate).

| Template | Pattern | Key rules |
|---|---|---|
| [`examples/f1_policy.json`](examples/f1_policy.json) | human-escalation for large spends | `require-human-for-large` (escalate), `allow-demo-endpoints`, `deny-unknown-hosts` |
| [`examples/fleet_lane/policy.json`](examples/fleet_lane/policy.json) | business-hours fleet lane | `allow-telemetry` (`host_in` + `hour_between` 07:00–23:00), `deny-unknown-hosts` |
| [`examples/budget_guard_policy.json`](examples/budget_guard_policy.json) | tiered budget guard | two `amount_gt` thresholds — deny >10, escalate >1 — then host allowlist, then deny |

DSL conditions (closed set — unknown keys are rejected at load time, so a
typo like `hostt_in` fails loudly instead of silently never matching):

| Condition | Matches when | Since |
|---|---|---|
| `host_in` | request path is in the list; **empty list = catch-all** | v0.1 |
| `hour_between` | wall-clock is inside `["HH:MM","HH:MM"]` (wraps midnight) | v0.1 |
| `amount_gt` | price is strictly above the threshold | v0.1 |
| `hour_in` | wall-clock equals one of `["HH:MM", ...]` exactly — minute-sharp windows | v0.7.3 |
| `agent_in` | caller's agent id is in the list (case-insensitive); skipped when no agent is declared | v0.7.3 |

First match wins; no match → **deny** (fail-closed,
`test_bank_template_validates`).

## Payment receipts — proving "paid" without trusting the payee

The gap: x402 facilitators verify a payment and return a settlement response,
but a *receiver* (an auditor, a buyer's employer, a marketplace) gets nothing
it can independently re-check later. USENIX Security 2026
([arXiv:2607.19545](https://arxiv.org/abs/2607.19545)) found rule violations in
**all 15** major facilitators it tested. Sester's answer is a single, boring,
verifiable object:

```json
{
  "receipt_version": 1,        "iss": "sester:node",
  "sub": "agent-1",            "resource": "/weather",
  "amount": "0.050000",        "amount_minor": 50000,
  "ts": 1789456789.123456,     "seq": 7,
  "proof": "<sha256 hex>",     "prev_proof": "<prev sha256 hex>",
  "chain_head": "<sha256 hex>","node_cosign": "<HMAC hex>"
}
```

The `proof` is `sha256(ts | event_type | agent | resource | amount | payload |
prev_proof)` — recomputable with pencil and a hash function. Tampering with
*any* of those fields breaks it; tampering with the metadata breaks the
optional node co-signature. The receiver needs **nothing but `sha256`**:

```python
# receiver side — Sester is NOT installed
import hashlib, json
r = json.loads(receipt_text)
assert r["receipt_version"] == 1
manual = "|".join([f"{float(r['ts']):.6f}", r["event_type"], r["sub"],
                   r["resource"], f"{float(r['amount']):.6f}",
                   r["payload"], r["prev_proof"]])
assert hashlib.sha256(manual.encode()).hexdigest() == r["proof"]   # proved
```

```bash
# or, one command — rc=0 KABUL, rc=1 RED
sester verify receipt.json
```

Schema rationale, field-by-field security analysis and comparison against
EIP-3009 / JWS / Merkle bundles:
[`docs/arastirma/02_receipt_schema.md`](docs/arastirma/02_receipt_schema.md).

## MCP server — agents pay, agents verify

[`mcp/server.py`](mcp/server.py) speaks Model Context Protocol 2025-06-18 over
stdio (JSON-RPC 2.0, pure stdlib) and exposes four tools:

| Tool | Purpose |
|---|---|
| `pay` | charge an agent for a resource → returns the node-cosigned receipt |
| `verify_receipt` | verify any receipt independently (receiver-side) |
| `balance` | daily spend / quota / remaining per agent |
| `history` | hash-chain events |

Embedded mode runs a local ledger — **$0, no keys, no testnet**. Remote mode
(`SESTER_MCP_ENDPOINT`) pays a real Sester-protected API. Publishable to
Smithery/Arcade (`mcp/smithery.yaml`): full setup in [`mcp/README.md`](mcp/README.md).



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
| **A2A x402 Extension** | `X-Payment` | `x402-payment {base64(json)}` | intentId / deterministic nonce |
| AP2 | `AP2-Mandate` | base64 JWS mandate | HS256/ES256, body-binding |
| ACP | `ACP-Session` | base64 JWS checkout session | JWS + vendor-side issuing |
| UCP | `UCP-Checkout` | base64 JWS web-monetization | vendor-sealed, merchant-bound |

All six compile to the same `ChargeIntent`/`ChargeReceipt` core — one shared
wallet means one shared quota. Register your own via `register_scheme` /
`ProtocolAdapter`.

## x402 extension modules (ecosystem alignment)

Sester implements the x402 Foundation's most-discussed extension gaps as
separate, testable modules:

| Module | x402 issue | What it closes |
|---|---|---|
| `sester/ledger.py` (`verify_chain`) | [#2332](https://github.com/x402-foundation/x402/issues/2332) (214+) | post-settlement accountability — tamper-evident anchor |
| `sester/trust.py` | [#1777](https://github.com/x402-foundation/x402/issues/1777) (119) | agent-trust: DID parse, attestations, trust-based pricing |
| `sester/reputation.py` | [#1024](https://github.com/x402-foundation/x402/issues/1024) | reputation with **wash-trade resistance** (#2833) |
| `sester/agreement.py` | [#3646](https://github.com/x402-foundation/x402/issues/3646) | agreement-session: terms-bound lifecycle, budget, expiry |
| `sester/escalation.py` | [#2887](https://github.com/x402-foundation/x402/issues/2887) (86) | dispute layer: oracle-bound decisions |
| `sester/delivery.py` | [#1195](https://github.com/x402-foundation/x402/issues/1195) (87) | delivery attestation (SAR): settlement ≠ delivery |

Each module is read-only over the ledger where possible, adds **no new event
types** (fail-closed taxonomy stays intact), and carries its own test suite
(see `tests/test_{trust,reputation,agreement,delivery}.py`).

## Test suites & acceptance runs

```bash
.venv/bin/python -m pytest tests/ -q    # full suite: policy, ledger, middleware, EVM schemes,
                                        # evidence, facilitator, protocol adapters, escalation,
                                        # JWS, signed policy, UCP, settlement, minor units,
                                        # payee registry, S6 joint acceptance, receipts, CLI,
                                        # MCP server — 380+ passing tests
                                        # (9 env-gated skips: PG/sibling-repos/external tools)
python scripts/s1_dogfood.py            # S1 acceptance scenario → KABUL (accepted)
python scripts/dogrula.py adoption/s1-kanit-bundle.json   # receiver side — no Sester needed
sester verify receipt.json                                # standalone proof CLI (rc=0 KABUL / rc=1 RED)
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
| [`docs/arastirma/`](docs/arastirma/) | Academic security research (USENIX'26 x402 facilitator study, Tamarin analysis, AP2 whisper attacks) + receipt-schema rationale + MCP market gap |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Shipped by version, what's next, deliberate non-goals |
| Architecture decision records | Scope, doctrine, deliberate limits — see the repository's decision documents |
| Policy DSL specification | Semantics + test-vector discipline — see the repository's spec documents |
| Execution plan | Acceptance milestones (S1–S6) — see the repository's plan documents |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Hard rules for PRs (fail-closed, K0-frozen, test-first) |
| [`SECURITY.md`](SECURITY.md) | Reporting policy — replay/quota/signature-bypass bugs |

## Deliberate v0 limits

Non-goals by decision, not by omission (see the repository's decision records): transaction
signing stays out of the library (non-custodial — the signing party is yours),
live PSP certification is pending real-world traffic, and the receipt/CLI/MCP
surface covers proof-of-payment, not LLM intent binding (the third AP2
"whisper" attack is a decision-layer problem — see
[`docs/arastirma/01_x402_guvenlik_aciklari.md`](docs/arastirma/01_x402_guvenlik_aciklari.md)
§3). Everything else on the roadmap through v0.5.0 is implemented
and gated by the test suite above.

## Environment variables

All optional; every one defaults to a **demo/development value and warns when
in effect** — the production secrets never live in the repository.

| Variable | Default | Meaning |
|---|---|---|
| `SESTER_FACILITATOR_SECRET` | *(none)* | **Fail-closed, no default** — the x402 facilitator service refuses to start without it (it derives the auth key). This is the one variable with no demo fallback. |
| `SESTER_DEMO_SECRET` | `sester-demo-secret-v0` | Ledger seal for the demo; a startup warning is printed when the default is in effect. |
| `SESTER_UCP_SECRET` / `SESTER_AP2_SECRET` | `sester-demo-ucp` / `sester-demo-ap2` | Per-protocol adapter secrets for the demo's four-protocol flow. |
| `SESTER_DEMO_STRICT` | `0` | Set `1` to make the demo **fail-closed** on unsigned ACP/UCP envelopes (default tolerates them for the demo light-path). |
| `SESTER_DEMO_NODE_SECRET` / `SESTER_DEMO_NODE_ID` | *(none)* / `sester:demo-node` | Cosign-key for demo receipts. Without it the receipt's `proof` is still sha256-verifiable; with it the response also carries a node co-signature (v0.7.4). |
| `SESTER_ESCALATION_DB` / `SESTER_DEMO_LEDGER_DB` | `sester-escalation.sqlite3` / `sester-demo.sqlite3` | DB paths — also used for test isolation (`conftest` moves these into tmp dirs). |
| `SESTER_PG_DSN` | *(none)* | Postgres parity: when set, `PgLedger` is exercised (the PG test-legs are skipped otherwise). |
| `SESTER_TAMGA_REPO` / `SESTER_VERIDICT_REPO` | *(none)* | Enable the cross-repo CI job that pins K1/K2 bridge compatibility against the sibling products' current `main`. |

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

Dual-licensed **Apache-2.0 OR AGPL-3.0** — pick either per integration (see
[`LICENSE`](LICENSE)). Apache for commercial rails that cannot touch copyleft;
AGPL keeps network-service derivatives open. The frozen wire fields
(`pugio0`, `pugio_bundle_version`, `source: "sikke"`) are kept for
receiver compatibility and are documented in the repository's identity-migration record; visual and
wire identity are separate layers.
