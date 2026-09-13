# Changelog

All notable changes to PUGIO (pugio-meter) are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/) · SemVer.

## [0.3.1] — 2026-09-12

### Added
- **ACP seller-side sessions:** `issue_acp_session()` — the seller endpoint
  issues signed `ACP-Session` envelopes (JWS, same HS256/ES256 machinery);
  `SignatureRequiredError` + `require_signature`/`require_acp_signature`
  production flag (unsigned legacy envelopes fail closed in production mode)
  (tests 146–152).
- **SQLite→Postgres migration tool:** `pugio/migrate_pg.py` — hash-preserving
  replay (chain is never re-generated; same secret verifies on the target),
  nonce-window preservation, idempotent re-runs, `--plan/--dry-run/--verify`
  modes, corrupt-source refusal; `insert_event/insert_nonce/export_nonces`
  primitives on both backends (tests 153–158).
- **SPEC_FARK v3:** fourth player UCP (Google+Shopify, `/.well-known/ucp`,
  Tech Council incl. Stripe/Amazon/Meta/Microsoft/Salesforce since 24 Apr 2026)
  + layer-model confirmation ("ACP = checkout, AP2 = consent", Google Cloud,
  10 Jun 2026) — adapter thesis confirmed a fourth time; priorities unchanged,
  UCP on watchlist (§5).
- Publication checklist (`docs/PUBLICATION_CHECKLIST.md`) with completed
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
- **Signed policy + 24h relaxation gate (S3):** `pugio/policy_signed.py` —
  JWS-sealed policy envelopes; tightening applies immediately, loosening
  waits `signed_at + 86400` (KURAL_DSL §3); pending relaxation never leaks
  into decisions; corruption keeps last-good state, never loads (tests 118–128).
- **Approval panel UI:** `/approvals` brand-styled page (Pugio-Tally mark,
  Ink/Old Gold palette) with one-click approve/deny wired to
  `POST /escalations/{id}/decide` (404/409/400 fail-loud contract);
  `/escalations` exempt from metering (tests 129–135).
- **81-side native bundle reader (S4 closure):** Tamga repo's
  `tamga_pugio_ingest.py` — pure-stdlib K0 verification + deterministic
  verification receipt (`receipt_id = sha256(verdict|head|merkle|count)[:32]`);
  denial attack and header lies rejected, receipt never produced on RED
  (tests 136–140).
- **Postgres backend:** `pugio/pg_ledger.py` — identical `Ledger` interface on
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
  (`pugio/adapters.py`, tests 82–95).
- **Escalation queue:** KURAL_DSL `then: escalate` is now a real
  human-in-the-loop flow — park (402 `escalation_required:<id>`), approve/deny
  via CLI (`python -m pugio.escalation`) or `GET /escalations`, one-time
  consumption, 15-min fail-closed TTL, full ledger audit trail
  (`escalation_parked/approved/denied/consumed`) (`pugio/escalation.py`,
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
  receipt headers; HMAC (`pugio0`) and EVM (`Pugio-EVM`, EIP-191) schemes on
  a `register_scheme` registry.
- Hash-chain SQLite ledger (WAL) with refund accounting, per-agent summaries,
  `verify_chain` tamper evidence.
- Fail-closed KURAL_DSL v0 policy subset (first-match-wins, `DenyAll` on
  corrupt files, live reload on mtime).
- x402 `exact` (EIP-3009/EIP-712) envelope support with facilitator
  verify→settle lifecycle and `settlement` ledger events; unknown/error →
  fail-closed 402.
- Persistent nonce table (`seen_nonces`) — replay protection survives
  restarts; integer minor-unit quota arithmetic (float-trap killed).
- Evidence bridge: externally verifiable proof bundles (pure-sha256,
  Merkle root) + K1 Tamga anchor + K2 Veridict claims + K3 watch feed
  (`pugio/evidence.py`, `pugio/bridges.py`, `pugio/watchfeed.py`).
- Branded HTML panel, demo API (dogfood), S1 acceptance script, external
  stdlib-only verifier (`scripts/dogrula.py`), Apache-2.0 packaging,
  15-minute showcase guide.

[Unreleased]: https://github.com/pugio/pugio/compare/v0.1.0...HEAD
