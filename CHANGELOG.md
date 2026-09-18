# Changelog

All notable changes to SESTER (sester) are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/) · SemVer.

## [Unreleased]

### Added
- Added a minimal FastAPI integration example in examples/fastapi_demo.py, with usage instructions in examples/README.md.

## [0.7.0] — 2026-09-14

### Added
- **Transaction-signing interface (non-custodial contract):**
  `sester/signer.py` — `Signer` and `ResultTransport` protocols,
  `PreparingSigner` (deterministic batch → raw payload), and
  `build_signed_settlement()` (batch → prepare → optional broadcast →
  evidence). Keys never touch Sester: the signer lives on the operator's
  side and only a ready payload crosses the boundary. Fail-closed:
  prepare/broadcast failures raise `SettlementError` — a silent accept is
  impossible. Without a transport, evidence returns with `broadcast: False`
  (operator publishes through their own channel). Pinned by
  `tests/test_signer.py` (9 acceptance legs).
- **Fleet-lane dogfood example (production-ready template):**
  `examples/fleet_lane/` — a real internal endpoint behind
  `SesterMeter` with the fail-closed policy gate (`FleetPolicyMeter`),
  env-configurable secret/quota (`.env.example`), paid-request client with
  a `--replay` proof flag, systemd unit template, and operations README.
  5 integration tests (`tests/test_fleet_lane.py`) pin happy-path,
  replay, quota, policy-deny and chain integrity.
- **Dogfood report template:** `docs/DOGFOOD_REPORT_TEMPLATE.md` — monthly
  Show-and-tell format for the "we eat our own receipts" record.

### Fixed
- Launch Q&A templates added as an internal operating document
  (test-name-per-answer doctrine).

## [0.6.2] — 2026-09-14

### Fixed
- **Technical-debt sweep:** modernized the test helper to `asyncio.run()`
  (the deprecated `get_event_loop_policy` pattern is slated for removal in
  Python 3.16); added `__del__` safety nets to `Ledger` and `PgLedger` so
  unclosed database connections cannot leak ResourceWarnings into
  garbage-collected objects.
- **Warnings-as-errors discipline:** `pyproject.toml` now turns any new
  pytest warning into a test failure (fail-loud; two known third-party
  testclient deprecations from starlette/fastapi are the only exemptions —
  they are not fixable on our side). The rule immediately caught and fixed
  two real leaks (see above).

## [0.6.1] — 2026-09-14

- **Public-surface hygiene:** removed candidate-JPGs, legacy-identity brand
  files and workshop HTML from the public tree; internal planning docs moved
  to the maintainers' archive (public docs stay lean and neutral).
- **README rendering fix:** logo now renders on GitHub *and* PyPI (absolute
  asset URLs; per-theme SVG source for GitHub). OG image regenerated for 0.6.1.

## [0.6.0] — 2026-09-14

- **Metering metrics (step 1):** `GET /metrics` — Prometheus-text counters
  (requests/charges/replay-402/quota-402/rate-402/malformed-402 + chain-valid
  gauge); zero dependencies; exempt paths never bump counters
  (`tests/test_v060_metrics_rate.py`).
- **Burst limiting (step 2):** token-bucket second gate — per-agent
  `burst_capacity` (default 20) + `burst_refill_per_sec` (default 10);
  independent of the daily quota; over-burst → 402 `rate_limited` plus a
  ledger decision event (fail-closed audit trail).
- **Evidence webhooks (step 3):** `sester/webhooks.py` — charge/settlement
  events streamed out with HMAC-SHA256-timestamp signatures; receiver-side
  `verify_webhook` (timestamp window + constant-time compare) + retry
  (3× backoff) + failure log in the ledger (`webhook_delivery` event);
  zero dependencies (urllib).
- **Docker demo image:** `ghcr.io/goun7/sester-demo` (one-command demo;
  Dockerfile + GHCR workflow + healthcheck).
- **Landing page + discussions/dogfood/launch documentation** (repo
  surfaces for the public release).

## [0.5.0] — 2026-09-13

### Added
- **Hosted facilitator MVP (S5, lane-1):** `sester/facilitator_svc/` —
  `FacilitatorService` (verify/settle/refund with the SAME parser core as
  the seller-side `SesterMeter`), seller metering with free-band + %1 +
  $0.005  (auditable proof events), settlement-batch integration
  (`build_settlement_batch` fail-closed on broken chains), FastAPI surface
  (`/verify` `/settle` `/refund` `/panel` `/healthz`, constant-time auth-key
  guard → 401). Non-custodial: keys never collected. Tests 186–201.
- **S6 joint-acceptance contract:** `docs/S6_JOINT_ACCEPTANCE.md` — Tenderix
  authorize/capture/refund ↔ Sester facilitator mapping, single-ledger
  dual-evidence discipline, per-nonce cumulative refund cap; 63-side tests
  196–201 (`tests/test_s6_joint.py`).
- `[facilitator]` extra in `pyproject.toml` (core stays zero-dependency).
- **S6 field-settlement (third round):** the escrow-partner's v1.3.0 applied the rail
  migration to spec (`RAILS` `sester_*` + `RAIL_ALIASES` dual-read);
  the partner's internal joint-acceptance record freezes the counterparty-event
  field set from real source (join key `nonce`; fields `offer_id`/`auth_ref`/
  `escrow_state`/`dispute_ref` = their ledger `entry_hash`);
  `tests/test_s6_joint.py` (Tenderix side) pins their escrow/dispute halves.

### Fixed
- **Payee registry (settlement):** a free-form ledger identity is never passed
  into the ABI `address` field anymore — `register_payee` / `derive_payee_address`
  (explicit or explicit-basis derivation, registered, digest-bound); conflicting
  re-registration and non-40-hex addresses fail closed (gate-run finding:
  `SettlementError: adres 40-hex değil` on non-address seller ids).
- **Tamga receiver read-compat:** sibling receiver regressed to `pugio`-only
  and rejected the frozen primary `sikke` (gate-run finding, test_74) —
  dual-name read restored (`sikke|pugio`, unknown → RED) in the sibling AND the
  canonical copy; K0 spec §5 documents the receiver-side read-compat rule;
  pinned in `tests/test_payee_registry.py`.
- Metering credit rows (`refund_of`) excluded from the free-band transaction
  counter; EVM seller attribution verifies against the real resource.

## [0.4.0] — 2026-09-13

### Identity
- **SIKKE → SESTER rename** (project history: Pugio → Sikke → Sester, see
  the unify-log (identity history)): package `sikke` → `sester`, `SikkeMeter` → `SesterMeter`,
  `X-Sikke-*` → `X-Sester-*` headers, `exact-sikke` → `exact-sester` scheme,
  `PUGIO_*` env vars → `SESTER_*`. **Frozen wire fields preserved** for
  receiver compatibility: `pugio0` HMAC scheme, `pugio_bundle_version`,
  `pugio_evidence_bundle`, `source: sikke`, sibling receiver file names
  (`tamga_pugio_receiver.py`, `tamga_pugio_ingest.py`,
  `scripts/pugio_watch_receiver.py`) — unchanged until v2. A fail-loud
  `sikke/` tombstone package guards old imports; class alias lives in
  `sester/compat.py`.

### Added
- **UCP adapter (web-monetization):** `issue_ucp_checkout()` / `verify_ucp_checkout()`
  — the fourth protocol joins the K0 core (`UCP-Checkout <b64>` envelope,
  seller-sealed JWS, `intent_id` as persistent nonce); merchant-binding
  (`expected_merchant`) kills manifest-spoofing; `require_ucp_signature` +
  `ucp_merchant` production flags (tests 159–166). the fourth-protocol survey watchlist
  item → code.
- **On-chain settlement batches:** `sester/settlement.py` — pure-stdlib
  keccak-256 (known-vector tested), keccak-merkle root over the K0 evidence
  proofs (EVM-verifiable), canonical-ABI `settle(address,uint256,string,
  bytes32,uint64)` calldata, chain/contract/from binding in the batch digest
  (replay-on-other-contract closed); tx-signing deliberately out of scope —
  non-custodial (tests 174–181).
- **Minor-unit counter column:** `amount_minor` helper column on both
  backends (SQLite + PG) with idempotent migration, `spent_today_minor()`
  integer reads, `backfill_amount_minor()` (one-shot, hash-preserving,
  idempotent) — middleware quota decisions are now pure-integer end to end
  (tests 167–173). K0 frozen-canonical rule intact: the column never enters
  chain hashes; legacy rows stay dual-read.
- **Embedded mirror receivers for the frozen bridge contract:**
  `bridge_receivers/` — pure-stdlib, copy-ready Tamga/Veridict receivers
  (`--selftest` included) run end-to-end against the producers in
  `tests/test_bridges_mirror.py`, so the frozen wire contract
  (`source: "sikke"`, anchor_id / entry_sha formulas, claim shape) stays
  regression-pinned even when the sibling repos are absent from the machine.
- **S5 milestone design:** `docs/S5_FACILITATOR_MILESTONE.md` — hosted
  facilitator MVP (monetization lane 1) targeting v0.5.0, with acceptance
  scenarios S5.a–S5.e (code landed the same day — see [Unreleased]).
- Publication dry-run for 0.4.0 (twine PASSED) and private GitHub repo setup
  (`goun7/pugio-meter` — rename to `goun7/sester` at publish; cross-repo CI
  variables gated until siblings publish).
- **Publication gates as code:** `scripts/publish_gate.sh` (one-shot local gate:
  cleanup + full suite ×2 incl. Postgres + S1/S2 + brand PNGs + build/twine +
  live-E2E; `PUSH=1` / `REPO_RENAME=1` for remote steps) and
  `scripts/live_gate.sh` (live uvicorn E2E T0–T10: challenge, HMAC happy-path
  + replay, broken-HMAC/EVM → 402-not-500, UCP seller envelope, quota,
  policy deny, panel, closing chain).

### Fixed
- **EVM attribution (demo policy-guard):** `_agent_of` now verifies the
  `Sester-EVM` envelope against the *real request path* and extracts the
  agent string — previously it verified with an empty resource (which can
  never succeed for resource-bound signatures) and returned a dict, so every
  EVM agent's policy decision was attributed to `bilinmeyen` in the ledger.
  Pinned by `tests/test_demo_attribution.py`.
- **Broken EVM envelopes fail closed (402), not 500:** `PaymentError` from
  the scheme layer is translated to the middleware's `PaymentErr` at the
  boundary; producer-side `sign_exact_sester` now refuses envelopes whose
  agent field doesn't match the signing address (checksummed/lowercase
  asymmetry caught in live testing).
- Middleware integer-quota path keeps working with user-supplied ledgers that
  predate the v0.4 interface (duck-typed float fallback).

## [0.3.1] — 2026-09-12

### Added
- **ACP seller-side sessions:** `issue_acp_session()` — the seller endpoint
  issues signed `ACP-Session` envelopes (JWS, same HS256/ES256 machinery);
  `SignatureRequiredError` + `require_signature`/`require_acp_signature`
  production flag (unsigned legacy envelopes fail closed in production mode)
  (tests 146–152).
- **SQLite→Postgres migration tool:** `sester/migrate_pg.py` — hash-preserving
  replay (chain is never re-generated; same secret verifies on the target),
  nonce-window preservation, idempotent re-runs, `--plan/--dry-run/--verify`
  modes, corrupt-source refusal; `insert_event/insert_nonce/export_nonces`
  primitives on both backends (tests 153–158).
- **the fourth-protocol survey:** fourth player UCP (Google+Shopify, `/.well-known/ucp`,
  Tech Council incl. Stripe/Amazon/Meta/Microsoft/Salesforce since 24 Apr 2026)
  + layer-model confirmation ("ACP = checkout, AP2 = consent", Google Cloud,
  10 Jun 2026) — adapter thesis confirmed a fourth time; priorities unchanged,
  UCP on watchlist (§5).
- release-gate checklist (maintainers' internal record) with completed
  dry-run (twine PASSED, clean-venv smoke, zero forced deps).

### Fixed
- **Security:** ACP/AP2 JWS body-binding generalized — the binding now covers
  *every* envelope field (previously only AP2's fixed field list, letting a
  scraped ACP `line_item` + valid signature slip through). Caught by test 148.
- Escalation queue DB: WAL + busy_timeout (matches ledger discipline); demo
  DBs overridable via env for test isolation (conftest) — no more lock
  contention with a live server.

## [0.3.0] — 2026-09-12

### Added
- **AP2 JWS verification (RFC 7515):** mandate signatures are now cryptographically
  verified — HS256 (stdlib) and ES256 (`[jws]` extra, `cryptography`); opt-in
  `key_resolver` (production requires it), `expected_body` binding kills
  scope-scraping (tampered body + valid signature → 402), alg-allowlist
  (`none` fail-closed), `sign_mandate_jws` producer helper (tests 108–117).
- **Signed policy + 24h relaxation gate (S3):** `sester/policy_signed.py` —
  JWS-sealed policy envelopes; tightening applies immediately, loosening
  waits `signed_at + 86400` (SPEND_POLICY §3); pending relaxation never leaks
  into decisions; corruption keeps last-good state, never loads (tests 118–128).
- **Approval panel UI:** `/approvals` brand-styled page (Sester-coin mark,
  Ink/Old Gold palette) with one-click approve/deny wired to
  `POST /escalations/{id}/decide` (404/409/400 fail-loud contract);
  `/escalations` exempt from metering (tests 129–135).
- **81-side native bundle reader (S4 closure):** Tamga repo's
  `tamga_pugio_ingest.py` — pure-stdlib K0 verification + deterministic
  verification receipt (`receipt_id = sha256(verdict|head|merkle|count)[:32]`);
  denial attack and header lies rejected, receipt never produced on RED
  (tests 136–140).
- **Postgres backend:** `sester/pg_ledger.py` — identical `Ledger` interface on
  the shared hash-chain core (`canonical_line`/`seal` extracted backend-neutral);
  same secret+events+timestamps → identical chains across SQLite/PG; PG bundle
  passes the external pure-stdlib verifier; `ON CONFLICT` atomic `claim_nonce`;
  `[pg]` extra; parity suite with deterministic clock (tests 141–145).

### Fixed
- Demo policy order: escalation rule now reachable under first-match-wins;
  per-request-cap branch defers to explicit `escalate` instead of blanket deny.

## [0.2.0] — 2026-09-12

### Added
- **Protocol adapters (K4):** AP2 mandate (`AP2-Mandate <b64>`) and ACP
  checkout-session (`ACP-Session <b64>`) parsed and authorized against the
  K0 `ChargeIntent`/`ChargeReceipt` core; both land in the persistent
  replay/quotum machinery — one wallet, one counter across protocols
  (`sester/adapters.py`, tests 82–95).
- **Escalation queue:** SPEND_POLICY `then: escalate` is now a real
  human-in-the-loop flow — park (402 `escalation_required:<id>`), approve/deny
  via CLI (`python -m sester.escalation`) or `GET /escalations`, one-time
  consumption, 15-min fail-closed TTL, full ledger audit trail
  (`escalation_parked/approved/denied/consumed`) (`sester/escalation.py`,
  tests 96–106).
- **Live policy reload** honors explicit escalation even above the
  per-request cap; demo policy reordered so first-match-wins keeps escalation
  reachable.

### Fixed
- Facilitator-flow edge: `PaymentErr` translation now covers parse+verify of
  AP2/ACP envelopes (no `AdapterError` leakage to ASGI callers).
- `watchfeed`/receiver invariant pinned in K0 spec §6:
  `bundle_event_count ≥ close.entries` (mixed bundles contain receipts that
  the decision feed omits).

## [0.1.0] — 2026-09-12

### Added
- Pure-ASGI x402-style metering middleware: 402 challenge → payment →
  receipt headers; HMAC (`pugio0`) and EVM (`Sikke-EVM` → today's
  `exact-sester`/`Sester-EVM`, EIP-191) schemes on
  a `register_scheme` registry.
- Hash-chain SQLite ledger (WAL) with refund accounting, per-agent summaries,
  `verify_chain` tamper evidence.
- Fail-closed SPEND_POLICY v0 policy subset (first-match-wins, `DenyAll` on
  corrupt files, live reload on mtime).
- x402 `exact` (EIP-3009/EIP-712) envelope support with facilitator
  verify→settle lifecycle and `settlement` ledger events; unknown/error →
  fail-closed 402.
- Persistent nonce table (`seen_nonces`) — replay protection survives
  restarts; integer minor-unit quota arithmetic (float-trap killed).
- Evidence bridge: externally verifiable proof bundles (pure-sha256,
  Merkle root) + K1 Tamga anchor + K2 Veridict claims + K3 watch feed
  (`sester/evidence.py`, `sester/bridges.py`, `sester/watchfeed.py`).
- Branded HTML panel, demo API (dogfood), S1 acceptance script, external
  stdlib-only verifier (`scripts/dogrula.py`), Apache-2.0 packaging,
  15-minute showcase guide.

[Unreleased]: https://github.com/goun7/sester/compare/v0.1.0...HEAD
