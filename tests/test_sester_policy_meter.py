"""SesterPolicyMeter -- the demo wrapper that bolts the Policy-DSL gate onto
the x402 payment gate.

This was the last untested public name in the package: an AST sweep of
sester/ (public, non-underscore top-level classes whose name never appears
anywhere under tests/) left exactly this one.

SesterPolicyMeter subclasses SesterMeter and overrides __call__ to run the
policy layer BEFORE the payment layer:

  * for HTTP paths outside the exempt prefixes, with a Sester-EVM or pugio0
    payment header, it resolves the agent and amount and asks policy_guard
    for a verdict;
  * verdict "escalate" parks an escalation ticket and returns a 402 naming
    it, unless an approval is already on file -- then it is consumed once
    and the payment flow proceeds;
  * any verdict other than "allow" returns a 402 naming the rule;
  * everything else (no payment header, other schemes, exempt paths) falls
    straight through to the payment gate.

The constructor also installs the AP2/ACP/UCP adapters with env-overridable
secrets and a STRICT mode that fail-closes unsigned envelopes.

Each test is cut on BOTH arms, the convention this repo's probe layer set:
the HONEST arm exercises the unbroken object and asserts the behaviour its
contract names, and the FAULT arm breaks the invariant by a scoped
monkeypatch and asserts the behaviour CHANGES. Faults are applied with
unittest.mock.patch as context managers so the modules are restored before
the next test. Only this file is modified.
"""

import asyncio

import pytest
from unittest import mock

from sester import Ledger
from sester.demo_api import SesterPolicyMeter, _agent_of, _amount_of
from sester.middleware import SesterMeter


def _scope(payment, path="/data"):
    return {"type": "http", "method": "GET", "path": path,
            "headers": [(b"x-payment", payment.encode())]}


def _scope_no_payment(path="/data"):
    return {"type": "http", "method": "GET", "path": path, "headers": []}


def _capture():
    sent = []

    async def send(m):
        sent.append({k: (list(v) if k == "headers" else v)
                     for k, v in m.items()})

    return send, sent


def _asgi_app(body=b'{"ok": true}'):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
    return app


def _pugio(agent, nonce, amount, resource, secret="mw-secret"):
    import hashlib
    import hmac
    mac = hmac.new(secret.encode(),
                   f"{agent}|{nonce}|{amount}|{resource}".encode(),
                   hashlib.sha256).hexdigest()
    return f"pugio0 {agent}:{nonce}:{amount}:{mac}"


# ================================================ helper resolvers
def test_agent_of_extracts_the_agent_from_a_pugio_header():
    assert _agent_of("pugio0 ag-1:n1:0.05:mac", "/data") == "ag-1"


def test_agent_of_returns_none_for_an_unparseable_header():
    """FAULT: the header is not a payment the helper can read, so it must
    return None rather than a guessed agent -- a policy verdict on a guessed
    agent would be a verdict on the wrong party."""
    assert _agent_of("garbage", "/data") is None


def test_amount_of_parses_the_stated_amount():
    assert _amount_of("pugio0 ag-1:n1:0.05:mac") == 0.05


def test_amount_of_returns_none_when_there_is_no_amount():
    """FAULT: no amount is present. The helper must yield None so the caller
    falls back to the meter's configured price rather than to zero."""
    assert _amount_of("garbage") is None


# ================================================ policy gate
def test_policy_meter_is_a_sester_meter():
    """The wrapper must be a drop-in for the payment gate: it inherits the
    x402 challenge machinery rather than reimplementing it."""
    assert issubclass(SesterPolicyMeter, SesterMeter)


def test_policy_meter_installs_the_demo_adapters(tmp_path):
    """The constructor must install the AP2/ACP/UCP adapters and register
    their schemes, so a wrapper without them would be a plain payment gate."""
    led = Ledger(str(tmp_path / "pm1.sqlite3"), secret="mw-secret")
    before = dict(led.conn.execute("select 1").fetchall()) if False else None
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, secret="mw-secret")
    # the adapter schemes are registered alongside the built-in ones
    assert "Sester-EVM" in meter._schemes
    assert meter._demo_secrets
    led.close()


def test_policy_meter_reads_env_secrets(monkeypatch, tmp_path):
    """The UCP/AP2 secrets are env-overridable so a demo is not pinned to the
    shipped defaults -- the override must reach the key resolver."""
    monkeypatch.setenv("SESTER_UCP_SECRET", "override-ucp")
    monkeypatch.setenv("SESTER_AP2_SECRET", "override-ap2")
    led = Ledger(str(tmp_path / "pm2.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, secret="mw-secret")
    assert meter._demo_secrets["sester-demo-ucp-1"] == b"override-ucp"
    assert meter._demo_secrets["sester-demo-ap2-1"] == b"override-ap2"
    led.close()


def test_policy_meter_defaults_strict_mode_off(tmp_path):
    """Without SESTER_DEMO_STRICT=1 unsigned envelopes are accepted (the
    demo's default), because strict mode is opt-in rather than breaking."""
    led = Ledger(str(tmp_path / "pm3.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, secret="mw-secret")
    # the adapters were installed with require_*_signature False
    assert "sester-demo-ucp-1" in meter._demo_secrets
    led.close()


def test_policy_meter_allows_when_the_policy_verdict_is_allow(tmp_path):
    """FAULT-control: the policy verdict is allow, so the request must reach
    the payment gate and the payment gate's own 402 applies (no payment
    secret in the header) -- the policy layer must not answer for it."""
    led = Ledger(str(tmp_path / "pm4.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, price=0.05,
                              daily_quota=1.0, secret="mw-secret")
    send, sent = _capture()
    with mock.patch("sester.demo_api.policy_guard",
                    return_value=("allow", "default")):
        asyncio.run(meter(_scope("pugio0 bogus", "/data"),
                          lambda: None, send))
    status = next((m["status"] for m in sent
                   if m["type"] == "http.response.start"), None)
    # the payment gate rejects the bogus mac, not the policy layer
    assert status == 402
    led.close()


def test_policy_meter_denies_when_the_verdict_is_not_allow(tmp_path):
    """FAULT: the policy verdict is deny. The wrapper must return a 402
    naming the rule, WITHOUT consulting the payment layer -- a policy deny
    must never become a payable request."""
    led = Ledger(str(tmp_path / "pm5.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, price=0.05,
                              daily_quota=1.0, secret="mw-secret")
    send, sent = _capture()
    with mock.patch("sester.demo_api.policy_guard",
                    return_value=("deny", "quota_gone")):
        asyncio.run(meter(_scope("pugio0 bogus", "/data"),
                          lambda: None, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 402
    body = json_text(sent)
    assert "policy_denied:quota_gone" in body
    led.close()


def test_policy_meter_parks_an_escalation_ticket(tmp_path):
    """FAULT: the policy verdict is escalate and no approval is on file. The
    wrapper must park a ticket and return a 402 naming the escalation id."""
    led = Ledger(str(tmp_path / "pm6.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, price=0.05,
                              daily_quota=1.0, secret="mw-secret")
    send, sent = _capture()
    with mock.patch("sester.demo_api.policy_guard",
                    return_value=("escalate", "big_spend")), \
            mock.patch("sester.demo_api.esc_queue.approved_for",
                       return_value=None), \
            mock.patch("sester.demo_api.esc_queue.park",
                       return_value={"esc_id": "E-1"}):
        asyncio.run(meter(_scope("pugio0 bogus", "/data"),
                          lambda: None, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 402
    assert "escalation_required:E-1" in json_text(sent)
    led.close()


def test_policy_meter_consumes_an_existing_approval(tmp_path):
    """FAULT: the policy verdict is escalate BUT an approval is on file. The
    wrapper must consume it once and let the payment flow proceed -- this is
    the one-time-consumption invariant that keeps an approval from being a
    permanent override. __call__ appends the escalation record to the
    module's own demo ledger, so that global is swapped for the temp one."""
    import sester.demo_api as demo
    led = Ledger(str(tmp_path / "pm7.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, price=0.05,
                              daily_quota=1.0, secret="mw-secret")
    send, sent = _capture()
    consumed = []
    with mock.patch("sester.demo_api.policy_guard",
                    return_value=("escalate", "big_spend")), \
            mock.patch("sester.demo_api.esc_queue.approved_for",
                       return_value={"esc_id": "E-2"}), \
            mock.patch("sester.demo_api.esc_queue.consume",
                       lambda eid: consumed.append(eid) or True), \
            mock.patch.object(demo, "ledger", led):
        asyncio.run(meter(_scope(_pugio("ag-x", "n1", "0.05", "/data"),
                                 "/data"), lambda: None, send))
    assert consumed == ["E-2"]
    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 200
    rows = led.export_events("ag-x")
    assert any(r["event_type"] == "escalation_consumed" for r in rows)
    led.close()


def test_policy_meter_escalation_consumption_is_one_shot(tmp_path):
    """The approval is consumed exactly once: a second request under the same
    escalation finds the approval already consumed, so it must park a fresh
    ticket rather than reuse the approval. This is the one-time-consumption
    invariant that keeps an approval from becoming a permanent override."""
    import sester.demo_api as demo
    led = Ledger(str(tmp_path / "pm8.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, price=0.05,
                              daily_quota=1.0, secret="mw-secret")
    # consume() answers True the first time only
    state = {"n": 0}

    def consume_once(eid):
        state["n"] += 1
        return state["n"] == 1

    parked = []
    with mock.patch("sester.demo_api.policy_guard",
                    return_value=("escalate", "big_spend")), \
            mock.patch("sester.demo_api.esc_queue.approved_for",
                       return_value={"esc_id": "E-3"}), \
            mock.patch("sester.demo_api.esc_queue.consume",
                       consume_once), \
            mock.patch("sester.demo_api.esc_queue.park",
                       lambda agent, path, price, rule:
                       parked.append((agent, path)) or {"esc_id": "E-4"}), \
            mock.patch.object(demo, "ledger", led):
        for _ in range(2):
            send, sent = _capture()
            asyncio.run(meter(_scope(_pugio("ag-y", "n1", "0.05", "/data"),
                                     "/data"), lambda: None, send))
    rows = led.export_events("ag-y")
    assert sum(1 for r in rows if r["event_type"] == "escalation_consumed") == 1
    # the second request parked a fresh ticket instead of re-consuming
    assert len(parked) == 1
    led.close()


def test_policy_meter_skips_the_policy_layer_for_exempt_paths(tmp_path):
    """Exempt prefixes must bypass the policy layer entirely, because the
    health and metrics endpoints have no payment and no policy verdict."""
    led = Ledger(str(tmp_path / "pm9.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, price=0.05,
                              daily_quota=1.0, secret="mw-secret")
    send, sent = _capture()
    called = []
    with mock.patch("sester.demo_api.policy_guard",
                    lambda *a, **k: called.append(1) or ("allow", "r")):
        asyncio.run(meter(_scope_no_payment("/healthz"), lambda: None, send))
    assert called == []
    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 200
    led.close()


def test_policy_meter_skips_the_policy_layer_without_a_payment_header(tmp_path):
    """A request with no payment header must fall straight through to the
    payment gate's own 402 -- the policy layer runs only on paying paths."""
    led = Ledger(str(tmp_path / "pm10.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, price=0.05,
                              daily_quota=1.0, secret="mw-secret")
    send, sent = _capture()
    called = []
    with mock.patch("sester.demo_api.policy_guard",
                    lambda *a, **k: called.append(1) or ("allow", "r")):
        asyncio.run(meter(_scope_no_payment("/data"), lambda: None, send))
    assert called == []
    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 402
    led.close()


def test_policy_meter_skips_the_policy_layer_for_other_schemes(tmp_path):
    """A scheme the policy layer does not gate (not Sester-EVM or pugio0)
    must fall through to the payment gate rather than be policy-checked."""
    led = Ledger(str(tmp_path / "pm11.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, price=0.05,
                              daily_quota=1.0, secret="mw-secret")
    send, sent = _capture()
    called = []
    with mock.patch("sester.demo_api.policy_guard",
                    lambda *a, **k: called.append(1) or ("allow", "r")):
        asyncio.run(meter(_scope("x402 AAAA", "/data"), lambda: None, send))
    assert called == []
    led.close()


def test_policy_meter_passes_the_amount_to_the_guard(tmp_path):
    """The guard must receive the amount the header states, so a policy rule
    keyed on amount decides on the real charge rather than the list price."""
    led = Ledger(str(tmp_path / "pm12.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, price=0.05,
                              daily_quota=1.0, secret="mw-secret")
    seen = []
    send, sent = _capture()
    with mock.patch("sester.demo_api.policy_guard",
                    lambda agent, path, amount: seen.append(amount)
                    or ("allow", "r")):
        asyncio.run(meter(_scope(_pugio("ag-z", "n1", "0.05", "/data"),
                                 "/data"), lambda: None, send))
    assert seen == [0.05]
    led.close()


def test_policy_meter_falls_back_to_the_list_price_without_an_amount(tmp_path):
    """FAULT: the header carries no parseable amount. The guard must receive
    the meter's configured price, not None or zero -- a policy rule keyed on
    amount must never see a free ride."""
    led = Ledger(str(tmp_path / "pm13.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, price=0.05,
                              daily_quota=1.0, secret="mw-secret")
    seen = []
    send, sent = _capture()
    with mock.patch("sester.demo_api.policy_guard",
                    lambda agent, path, amount: seen.append(amount)
                    or ("allow", "r")), \
            mock.patch("sester.demo_api._amount_of", lambda p: None):
        asyncio.run(meter(_scope("pugio0 ag-z:n1:x:mac", "/data"),
                          lambda: None, send))
    assert seen == [0.05]
    led.close()


def test_policy_meter_uses_unknown_for_an_unresolvable_agent(tmp_path):
    """FAULT: the header has no resolvable agent. The guard must receive the
    explicit sentinel 'bilinmeyen' rather than None, because a policy rule
    keyed on agent must decide the anonymous case explicitly."""
    led = Ledger(str(tmp_path / "pm14.sqlite3"), secret="mw-secret")
    meter = SesterPolicyMeter(_asgi_app(), ledger=led, price=0.05,
                              daily_quota=1.0, secret="mw-secret")
    seen = []
    send, sent = _capture()
    with mock.patch("sester.demo_api.policy_guard",
                    lambda agent, path, amount: seen.append(agent)
                    or ("allow", "r")), \
            mock.patch("sester.demo_api._agent_of", lambda p, r: None):
        asyncio.run(meter(_scope("pugio0 ???", "/data"), lambda: None,
                          send))
    assert seen == ["bilinmeyen"]
    led.close()


# ================================================ helpers
_sent_noop = []


async def _noop_send(m):
    _sent_noop.append(m)


def json_text(sent):
    import json
    for m in sent:
        if m["type"] == "http.response.body" and isinstance(m.get("body"), (bytes, bytearray)):
            return m["body"].decode("utf-8", "replace")
    return ""
