# Contributing to Sester

Short, hard rules — Sester is a **fail-closed** commerce layer; PRs are
reviewed under the same discipline.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest tests/ -q          # 200+ test legs — do not open a PR with any RED
```

Postgres-parity legs (optional):

```bash
docker run -d --name sester-pg -e POSTGRES_PASSWORD=sester -p 5499:5432 postgres:16-alpine
export SESTER_PG_DSN="host=127.0.0.1 port=5499 dbname=postgres user=postgres password=sester"
pytest tests/test_pg_parity.py tests/test_minor_unit.py -q
```

## Hard rules

1. **Fail-closed is non-negotiable.** Every new rejection path must fail loud
   (RED); any PR introducing a silent fallback (fail-open) is rejected.
2. **The K0 envelope is frozen.** `canonical_line` / the evidence-bundle schema
   do not change; schema PRs require a compatibility rationale (see
   `docs/K0_SHARED_ENVELOPE_SPEC.md`). The same applies to the frozen wire
   fields (`pugio0`, `pugio_bundle_version`, `pugio_evidence_bundle`,
   `source: "sikke"`) — kept until protocol v2 (see `ESKI_KIMLIK.md`).
3. **Test-first.** Past bug-catchers prove the practice (see the changelog's
   gate-run findings) — behavior fixes arrive with a test before the fix.
4. **Zero required dependencies.** Core is stdlib-only; heavy dependencies go
   into extras (`[evm]`, `[jws]`, `[pg]`, `[demo]`, `[facilitator]`).
5. **Secrets never enter tests**; demo keys/DBs are isolated via env overrides.

## Release language

- SemVer + Keep-a-Changelog; no PR without a `CHANGELOG.md` entry.
- Breaking changes require a decision record (see `KARAR_63B.md` for format).
