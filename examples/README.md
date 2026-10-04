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
