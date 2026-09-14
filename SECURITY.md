# Security Policy

Sester is a **fail-closed** commerce layer; security findings are treated as
first-class input and handled confidentially.

## Reporting channel

Please **do not open a public issue**. Use GitHub Security Advisory:
https://github.com/goun7/sester/security/advisories/new

## In scope (priority areas)

- Replay / nonce bypass (`seen_nonces` persistence, restart behavior)
- Quota evasion (integer minor-unit metering, daily reset, refund accounting)
- JWS / attribute doctrine: `key_resolver` bypass, body-binding stripping,
  algorithm downgrade (`alg: none`), AP2/ACP/UCP envelope forgery
- Evidence-chain integrity (HMAC seal, hash-preserving migration, keccak batch)
- Policy fail-closed breakage (corrupt file → DENY_ALL; 24 h loosening gate)

## Out of scope

- Demo secrets pinned for examples (`examples/`, `scripts/`)
- Integrator deployments that use weak keys

## Version support

Only the latest minor release receives security patches (0.x discipline);
breaking changes are tracked via the changelog and decision records.
