# K0 · Shared Evidence-Envelope Spec — draft v0.1 (2026-09-12)

> One-page contract that lets **independent** projects (SESTER · Tamga Protocol ·
> Veridict) anchor and audit each other's evidence **without merging**.
> Reference implementation: `sester/evidence.py` (+ `sester/bridges.py`),
> external verifier: `scripts/dogrula.py` (stdlib-only, no sester import).
> Status: DRAFT — adoption by each project is a separate decision
> (K0 row, §3 of the repo's unification review record). Every artifact carries a
> version field; readers MUST reject unknown versions.
>
> **KIMLIK-NOTU (2026-09-13):** ürün adı Pugio → Sikke → **SESTER** oldu
> (bkz. the identity-history record). Kablo-alanları DONUKTUR: `pugio_bundle_version`,
> `pugio_evidence_bundle`, `source: "sikke"` — alıcılar bu değerleri bekler;
> v2 sürüm-atılımına kadar değişmezler. Marka ≠ kablo-kimliği.

## 1) Canonical event line (the atom)

For an event with fields `ts, event_type, agent_id, host, amount, payload`,
its canonical preimage is:

```
TS|EVENT_TYPE|AGENT_ID|HOST|AMOUNT|PAYLOAD|PREV
```

- `TS` — unix seconds, fixed 6 decimals (`%.6f`)
- `AMOUNT` — fixed 6 decimals (`%.6f`)
- `PAYLOAD` — compact JSON, **sorted keys**, no spaces (`separators=(",",":")`)
- `PREV` — previous proof in hex; first event uses `GENESIS = 64 × "0"`

> **ERRATUM-K0.1 (2026-09-19):** the canonical `AMOUNT` is the **major** unit
> at fixed 6 decimals. An implementation MAY keep an auxiliary integer
> minor-unit column (e.g. SESTER's `amount_minor` for exact integer counting);
> such a column **MUST NOT** enter the canonical preimage — it is a local
> convenience, not part of the cross-project chain. Independent verifiers that
> read a producer's storage *directly* (rather than the envelope — e.g.
> Tamga's `sovereign_verify` opening the SQLite file) must derive hashes from
> the 6-decimal major amount only, or the two sides diverge silently. Pinned by
> `tests/test_sovereign_compat.py::test_207_amount_minor_column_stays_outside_hash`
> (auxiliary column changed in place → chain still valid).

> **ERRATUM-K0.2 (2026-09-19; corrected same-day):** `event_type` is a field in
> the canonical line, but its allowed values were never enumerated here — they
> lived only in code, while the envelope carries all of them. Any receiver that
> interprets `event_type` semantically must know the set. Producer-side
> taxonomy (SESTER's `Ledger.EVENT_TYPES` + `EVENT_TYPE_FAMILIES`, the single
> code source of truth, kept in sync with the SQLite schema comment and
> *enforced at the write boundary* by `test_208`):
> `charge_receipt` · `refund` · `permission_decision` · `escalation_parked` ·
> `escalation_approved` · `escalation_denied` · `escalation_consumed` ·
> `protocol_intent` · `settlement`, plus the dynamic prefix family
> `facilitator_{verify|settle|metering|refund|batch}`.
>
> **No dead entries (E1(c) mirror, 2026-09-19):** every listed value is either
> emitted by a documented producer path (tracked in Sester's
> `EVENT_TYPE_SOURCES`, machine-checked by `test_209`) or is a documented
> *caller-contract* value (`webhook_delivery` — integrators record webhook
> delivery failures for the audit trail). A value the spec lists but no
> producer ever emits is a divergence of the mirror class: it teaches a
> receiver to expect a payload shape that never comes. (`usage_event` was such
> a value — listed from a display-label assumption while the metering path
> actually writes `charge_receipt`; removed. The family enumeration also missed
> `batch`; both fixed same-day.)
>
> **Correction note (honesty, same day):** the first version of this erratum
> enumerated only eight values and missed `escalation_consumed`,
> `protocol_intent` and the `facilitator_*` family — i.e. an incomplete
> "producers MUST NOT emit values outside the declared set" clause would itself
> have made legitimate production events non-conforming. This is exactly the
> silent-divergence class the erratum was written to close. The set is now
> **fail-closed at `Ledger.append` / `PgLedger.append`**: an unknown
> `event_type` raises instead of being written, so any future gap breaks the
> producer's own test suite rather than a downstream verifier. Exhaustiveness is
> proven by the suite, not by inspection.
>
> Cross-project contracts: only `permission_decision` has a feed-level meaning
> (§6 — the watch feed carries it alone). **Spend netting:** `charge_receipt`
> contributes **+amount** and `refund` **−amount** to any running total; a
> receiver re-computing spend from the envelope must apply the same sign
> convention or the two sides diverge. Producers MUST NOT emit values outside
> the declared set/families (enforced); receivers that do not interpret
> `event_type` should treat it as opaque (§7 rule 3, additive only).
>
> **Read-side assertion (2026-09-19, Tamga AT-053-sorusu):** the producer
> guarantee covers rows written **through the library** only. An operator
> writing directly to storage (e.g. `pg_restore`/`COPY`/raw SQL) bypasses every
> write-time gate — and since the proof chain hashes `event_type` as opaque data,
> such a row still verifies GREEN. A receiver that wants to assert the taxonomy
> on data it did not itself write may call SESTER's `unknown_event_types(events)`
> helper, which returns the unknown values; the receiver then decides (abstain /
> warn / reject) per its own risk preference — mirroring VERIDICT-D13's
> verifier-abstain design. The hard reject is deliberately **not** inside the
> helper: §7 rule 3 keeps non-interpreting receivers opaque, so the choice stays
> with the receiver.

## 2) Proof chain (secretless tier)

`proof_i = SHA256(canonical_line_i)` — the **public** chain. Projects may keep an
additional sealed chain (e.g. SESTER's HMAC-sealed internal ledger); the public
chain is what crosses project boundaries. Link rule: `PREV` of event *i* equals
`proof_{i-1}`; a receiver re-hashes every line and fails on any mismatch
(drop, edit, reorder → broken link or proof mismatch).

## 3) Merkle root (batch binding)

Leaves = proof list, in `seq` order. Pair rule: `parent = SHA256(a_hex + b_hex)`;
odd last node pairs with itself; empty list → `GENESIS`. `merkle_root` is the
single root. Receivers re-fold and compare.

## 4) Bundle (evidence envelope)

```json
{ "pugio_bundle_version": 1, "generated": <unix>, "agent": "<id|null>",
  "head": "<last proof>", "merkle_root": "<root>",
  "event_count": N, "events": [ {seq, ts, event_type, agent_id, host,
  amount, payload, prev_proof, proof}, … ] }
```

Head/merkle/count are redundant on purpose: three independent checks.

## 5) Anchor envelope (cross-project write, K1)

A bundle summarized into ONE deterministic JSONL line for a foreign ledger:

```json
{ "type": "external_anchor", "bridge_version": 1, "source": "sikke",
  "agent": "<label>", "anchor_id": "<32hex>",
  "head": "<64hex>", "merkle_root": "<64hex>", "event_count": N }
```

Binding: `anchor_id = SHA256(head|merkle_root|event_count)[:32]` (hex string
concatenation, pipe separator). `generated` MUST be excluded from deterministic
renditions. Receiver verifies the binding with SHA256 only; optional full check
re-verifies the referenced bundle per §2–§4.

**Read-compat rule (2026-09-13; ACCEPTED upstream — TamgaProtocol commit
f6ee3b7, CI-green, AT-024 pin):** receivers MUST accept `source: "sikke"`
(frozen primary) and MAY accept `source: "pugio"` (pre-migration historical
output) — unknown sources still hard-reject; the `bridge_version` gate stays
independent (anchor envelope version = 1). Producers always emit `sikke`
(frozen); the read-compat is receiver-side only.

## 6) Watch feed (decision audit, K3)

JSONL stream: `watch_manifest` (watcher id + referenced bundle pointers) →
one `watch_event` per audited decision, chained with
`entry_sha = SHA256(prev_entry_sha|seq|ts|agent|host|rule_id|decision)`
(`prev_entry_sha` starts at `GENESIS`) → `watch_close` carrying the final
`watch_head`. Receiver re-hashes the chain and prints PASS/FAIL.

Count invariant: `manifest.bundle_event_count` counts **all** events in the
referenced bundle, while the feed carries **only** `permission_decision`
events (a subset — charge receipts never enter the feed). Therefore the only
sound check is `bundle_event_count ≥ close.entries`; equality is NOT required
and receivers MUST NOT reject mixed bundles where receipts make the bundle
strictly larger than the feed.

## 7) Rules of engagement (the "no-merge" guardrails)

1. **Public data only.** No secrets cross boundaries; sealing stays local.
2. **Version everything.** Unknown `*_version` → hard reject, never guess.
3. **Additive only.** A bridge must not require changes to the counterpart's
   core, schema, or CI; receivers are standalone stdlib scripts.
4. **Offline-verifiable.** Every artifact is replayable without the producer's
   code, network, or trust ("verify, don't trust").
5. **Fail loud.** Any mismatch → non-zero exit / explicit verdict; no silent
   passes (shared doctrine with Veridict).
6. **No replayed receipts (producer obligation).** A producer that gates
   payment on a nonce MUST reject a replayed nonce permanently — including
   across its own restarts — so that at most one `charge_receipt` is ever
   written per (agent, nonce). A receiver re-computing spend from the envelope
   counts each receipt once; a replayed write would silently double-count and
   the two sides would diverge. Sester enforces this with a persistent
   `seen_nonces` table (in-instance and across-reopen), pinned by
   `test_64`–`test_66`.

> **ERRATUM-K0.3 (2026-09-19):** the replay-protection obligation above was
> enforced in Sester's code (middleware gate + persistent `seen_nonces`) and
> pinned by three tests, but was **not** written as a normative rule anywhere a
> counterpart could read it — the code-only class that produced every other
> erratum in the tri-product audit (K0.1, E1, A1). Surfaced by the
> tri-product spec↔code checklist (`TRI-PRODUCT-CHECKLIST.md`, YÖN-B gap:
> code enforced, no spec needle) and closed the same day. Note the
> **failure-direction asymmetry** this rule exposes: K0.1/K0.2 violations fail
> at the producer's *write* boundary (its own `append` rejects → producer
> notices first, no artifact is ever emitted), whereas a replay violation would
> write a duplicate receipt and hit the *receivers* at read time. That is why
> this obligation belongs in the shared spec rather than a producer's internal
> note — it is the one Sester rule whose failure crosses the product boundary.
