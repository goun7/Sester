# SESTER Policy Examples

Ready-to-edit `wallet_policy` files for the Sester payment-policy DSL. Each
one loads straight through the existing loader:

```python
from sester.policy import Policy

policy = Policy.from_dict(json.load(open("examples/business_hours_policy.json")))
decision = policy.evaluate(amount=0.01, host="/weather", agent="my-agent")
```

## Files

| File | Shape | What it shows |
|---|---|---|
| `budget_guard_policy.json` | per-request + daily ceiling, escalation | hard quota enforcement and the escalate verdict |
| `f1_policy.json` | fleet telemetry lane | host allow-list with an hour window and timezone |
| `business_hours_policy.json` | business-hours-only lane | narrow allow window, deny-everything-else |
| `fastapi_client_demo.py` | client-side agent | a real `Sester-EVM` payment against the demo API |

## Running the client demo

```bash
pip install "sester[demo]" httpx eth-account uvicorn
uvicorn sester.demo_api:app --port 8402      # in one terminal
SESTER_EXAMPLE_GATEWAY=http://127.0.0.1:8402 python examples/fastapi_client_demo.py
```

With a fresh ledger this prints `ödeme onaylandı` four times (the demo quota
is 0.20 USDC-sim at 0.05 per request) and `reddedildi` on the fifth — the
fail-closed deny path, verified against the live gateway.

## Editing rules

- **First matching rule wins.** Order matters: put the narrow rules above the
  broad ones.
- **No match ⇒ DENY.** The DSL is fail-closed by design: a request that
  satisfies no rule is denied, never allowed. The last `deny-unknown` rule
  in each example is the explicit form of that default — remove it only if
  you understand you are relying on the implicit deny.
- **`escalate` parks the request.** It does not allow the payment; it queues
  a human-approval record that an operator must clear.
- **Amount limits live in `defaults`, not only in rules.** `per_request_max`
  and `daily_max` are enforced by the meter against the ledger; `amount_gt`
  in a rule is the routing condition, not the enforcement.

## Verifying an edit

```bash
python3 -c "import json; from sester.policy import Policy; \
  p=Policy.from_dict(json.load(open('examples/business_hours_policy.json'))); \
  print('rules:', len(p.rules))"
```

If that prints without raising, the file parses and every rule validates.
