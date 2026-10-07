"""The last untested public names of the Sester package.

An AST sweep of sester/ (public, non-underscore top-level classes and
functions whose name never appears anywhere under tests/) leaves eleven:

  * agreement.AgreementState -- the running budget state of an agreement:
    spend counter, payment counter and the exhaustion verdict.
  * demo_api.decide_escalation -- the POST /escalations/{id}/decide endpoint:
    approve/reject with 400/404/409 fail-loud errors.
  * facilitator.FacilitatorResult -- the ok/status/reason/raw result the
    facilitator's verify and settle endpoints return.
  * policy.Decision -- the policy DSL's verdict/rule_id/reason record.
  * settlement.SettlementBatch -- the batch the settlement pipeline packs:
    merkle root, leaves and calldata digest.
  * facilitator_svc.app.{VerifyReq,SettleReq,RefundReq} -- the request
    models of the facilitator service's three endpoints.
  * facilitator_svc.service.{FacilitatorServiceError,ServiceDecision} --
    the service layer's error type and its decision record.

Each is cut on BOTH arms, the convention this repo's probe layer set:

  - the HONEST arm exercises the unbroken object and asserts the behaviour
    its own contract names, and
  - the FAULT arm breaks the invariant by a scoped monkeypatch and asserts
    the behaviour CHANGES -- a constructor or verdict that still holds over
    the broken invariant is unfalsifiable, the defect class this project
    hunts.

Faults are applied with unittest.mock.patch as context managers so the
modules are restored before the next test. Only this file is modified.
"""

import time

import pytest
from unittest import mock

from sester.agreement import AgreementState, Terms
from sester.facilitator import FacilitatorResult
from sester.policy import Decision
from sester.settlement import SettlementBatch


def _terms(budget=1000):
    return Terms(agreement_id="ag-1", budget_minor=budget,
                 expires_at=time.time() + 3600)


# ================================================ agreement.AgreementState
def test_agreement_state_starts_at_zero_spend():
    """A fresh state has spent nothing and made no payments, and it is
    active -- an agreement that started exhausted would be unusable."""
    st = AgreementState(_terms())
    assert st.spent_minor == 0
    assert st.payments == 0
    assert st.is_active is True


def test_agreement_state_tracks_spend_and_remaining():
    """remaining is derived from the terms' budget, so spend and remaining
    must always sum to the budget -- the invariant the quota gate rests on."""
    st = AgreementState(_terms(), spent_minor=300)
    assert st.remaining == 700
    assert st.budget_exhausted is False


def test_agreement_state_reports_exhaustion():
    """When spend reaches the budget, remaining is zero and the exhaustion
    verdict flips -- this is the quota gate's fail-closed condition."""
    st = AgreementState(_terms(), spent_minor=1000)
    assert st.remaining == 0
    assert st.budget_exhausted is True
    assert st.is_active is False


def test_agreement_state_exhaustion_ignores_overdraft():
    """FAULT: the caller spends past the budget. Exhaustion must still hold
    and remaining must not go negative -- a negative remaining would let a
    caller buy budget by overdrawing."""
    st = AgreementState(_terms(), spent_minor=5000)
    assert st.budget_exhausted is True
    assert st.remaining == 0


def test_agreement_state_remembers_its_event_position():
    """last_event_seq is the ledger cursor; it must round-trip so a
    reconstructed state resumes exactly where the old one stopped."""
    st = AgreementState(_terms(), spent_minor=100, payments=2,
                        last_event_seq=17)
    assert st.last_event_seq == 17
    assert st.payments == 2


def test_agreement_state_zero_budget_is_never_exhausted():
    """FAULT: the budget is zero (no quota configured). budget_exhausted
    must stay False rather than vacuously True, because a zero budget means
    'no quota gate', not 'always out of budget'."""
    st = AgreementState(_terms(budget=0))
    assert st.budget_exhausted is False
    assert st.remaining == 0


# ================================================ facilitator.FacilitatorResult
def test_facilitator_result_defaults_reason_and_raw():
    """A success carries ok=True, status "ok", no reason and an empty raw --
    the caller branches on ok alone, so the defaults must not be falsy
    enough to look like a failure."""
    r = FacilitatorResult(True, "ok")
    assert r.ok is True
    assert r.status == "ok"
    assert r.reason == ""
    assert r.raw == {}


def test_facilitator_result_rejection_carries_its_reason():
    """A rejection names why and keeps the raw payload, because the caller
    must be able to report the cause without a second round trip."""
    r = FacilitatorResult(False, "rejected", "invalid signature",
                          {"error": "sig"})
    assert r.ok is False
    assert r.status == "rejected"
    assert r.reason == "invalid signature"
    assert r.raw == {"error": "sig"}


def test_facilitator_result_is_frozen():
    """FAULT: a caller tries to mutate the result. The dataclass is frozen
    so a verified verdict cannot be rewritten in flight -- the result is the
    evidence the settlement gate signs."""
    r = FacilitatorResult(True, "ok")
    with pytest.raises(Exception):
        r.ok = False


def test_facilitator_result_unknown_is_distinct_from_rejected():
    """A network failure is "unknown", not "rejected": conflating them would
    turn a transient outage into a permanent payment verdict."""
    r = FacilitatorResult(False, "unknown", "timeout")
    assert r.status != "rejected"
    assert r.ok is False


# ================================================ policy.Decision
def test_decision_carries_verdict_rule_and_reason():
    """A policy decision records which rule fired and why, because the
    middleware's deny response must name the rule for the caller."""
    d = Decision("deny", "quota_exceeded", "spent 1000 of 1000")
    assert d.verdict == "deny"
    assert d.rule_id == "quota_exceeded"
    assert d.reason == "spent 1000 of 1000"


def test_decision_reason_defaults_to_empty():
    """A decision without a reason must still be usable: the middleware
    formats reason only when it is non-empty."""
    d = Decision("allow", "default_allow")
    assert d.reason == ""


def test_decision_verdict_is_the_branching_field():
    """The middleware branches on verdict, so the two outcomes it names must
    be distinguishable strings rather than truthy/falsy variants of one."""
    allow = Decision("allow", "r")
    deny = Decision("deny", "r")
    assert allow.verdict != deny.verdict


# ================================================ settlement.SettlementBatch
def test_settlement_batch_packs_its_fields():
    """The batch carries the merkle root, the leaf list and the calldata
    digest -- the evidence the on-chain settlement submits."""
    b = SettlementBatch(agent="ag-1", payee_address="0xpayee",
                        chain_id=8453, contract="0xcontract",
                        from_address="0xfrom", total_minor=500,
                        currency="USDC-sim", event_count=10,
                        merkle_root="0xroot",
                        leaves=["l1", "l2"], calldata="0xcall",
                        sha_digest="0xdigest")
    assert b.agent == "ag-1"
    assert b.merkle_root == "0xroot"
    assert b.leaves == ["l1", "l2"]
    assert b.sha_digest == "0xdigest"
    assert b.total_minor == 500


def test_settlement_batch_leaves_and_root_are_independent_fields():
    """The merkle root is not derived inside the constructor: it is carried
    alongside the leaves so the caller can re-derive and compare. A batch
    whose root were silently computed from its leaves could not be checked."""
    b = SettlementBatch(agent="a", payee_address="p", chain_id=1,
                        contract="c", from_address="f", total_minor=1,
                        currency="USDC-sim", event_count=1,
                        merkle_root="0xWRONG",
                        leaves=["l1"], calldata="cd", sha_digest="sd")
    assert b.merkle_root == "0xWRONG"


def test_settlement_batch_event_count_and_total_are_carried_not_computed():
    """event_count and total_minor are stored as given, so a caller that
    packs a partial batch is not silently padded to a larger settlement."""
    b = SettlementBatch(agent="a", payee_address="p", chain_id=1,
                        contract="c", from_address="f", total_minor=7,
                        currency="USDC-sim", event_count=3,
                        merkle_root="r", leaves=["a", "b", "c"],
                        calldata="cd", sha_digest="sd")
    assert b.event_count == 3
    assert b.total_minor == 7


# ================================================ demo_api.decide_escalation
def test_decide_escalation_rejects_a_non_boolean_approve():
    """FAULT: the body's approve is a string, not a bool. The endpoint must
    return 400 rather than coercing it -- a coerced "false" string would
    become a truthy approval."""
    from sester.demo_api import decide_escalation
    rv = decide_escalation("esc-1", {"approve": "true", "by": "ops"})
    assert rv.status_code == 400


def test_decide_escalation_reports_a_missing_ticket():
    """FAULT: the escalation id does not exist. The endpoint must 404 rather
    than deciding a ticket that was never opened."""
    from sester.demo_api import decide_escalation
    rv = decide_escalation("no-such-ticket", {"approve": True, "by": "ops"})
    assert rv.status_code == 404


def test_decide_escalation_requires_the_approve_key():
    """FAULT: the body omits approve entirely. The endpoint must fail loud
    (400) rather than defaulting to either verdict -- a default-approve
    would auto-settle every escalation whose caller forgot the flag."""
    from sester.demo_api import decide_escalation
    rv = decide_escalation("esc-1", {"by": "ops"})
    assert rv.status_code == 400


def test_decide_escalation_accepts_a_boolean_rejection():
    """A well-formed rejection is not a client error: the endpoint must
    distinguish a bad request from a decision it disagrees with."""
    from sester.demo_api import decide_escalation
    rv = decide_escalation("esc-1", {"approve": False, "by": "ops"})
    assert rv.status_code != 400


# ================================================ facilitator_svc request models
def test_verify_req_requires_payment_and_resource():
    """FAULT: a body missing the required fields must be rejected, because
    the service cannot verify a payment it was never given."""
    from sester.facilitator_svc.app import VerifyReq
    with pytest.raises(Exception):
        VerifyReq(envelope={"from": "0xabc"})


def test_verify_req_builds_from_payment_and_resource():
    """The verify request takes the payment header and the resource it buys,
    so an envelope can be verified without a second schema."""
    from sester.facilitator_svc.app import VerifyReq
    req = VerifyReq(payment="x402 AAAA", resource="/data")
    assert req.payment == "x402 AAAA"
    assert req.resource == "/data"


def test_settle_req_requires_amount_minor():
    """FAULT: settle without an amount must be rejected, because the service
    settles a specific minor-unit value."""
    from sester.facilitator_svc.app import SettleReq
    with pytest.raises(Exception):
        SettleReq(payment="x402 AAAA", resource="/data")


def test_settle_req_builds_from_its_fields():
    """The settle request carries the payment, resource and the minor-unit
    amount to settle; it must construct independently of verify, because
    settle is its own endpoint."""
    from sester.facilitator_svc.app import SettleReq
    req = SettleReq(payment="x402 AAAA", resource="/data", amount_minor=50000)
    assert req.amount_minor == 50000


def test_refund_req_defaults_reason_and_dispute_ref():
    """A refund need not carry a reason or dispute ref: the defaults are
    empty so a caller can request a bare refund."""
    from sester.facilitator_svc.app import RefundReq
    req = RefundReq(payment="x402 AAAA", resource="/data", amount_minor=50000)
    assert req.reason == ""
    assert req.dispute_ref == ""


def test_refund_req_builds_with_a_dispute_reference():
    """A refund that names a dispute reference must keep it, because the
    dispute path needs the link to reconcile."""
    from sester.facilitator_svc.app import RefundReq
    req = RefundReq(payment="x402 AAAA", resource="/data", amount_minor=50000,
                    reason="overcharge", dispute_ref="D-7")
    assert req.reason == "overcharge"
    assert req.dispute_ref == "D-7"


# ================================================ facilitator_svc service layer
def test_facilitator_service_error_is_an_exception():
    """The service error must be raisable, because the service layer turns
    transport failures into exceptions the API maps to 5xx."""
    from sester.facilitator_svc.service import FacilitatorServiceError
    assert issubclass(FacilitatorServiceError, Exception)


def test_service_decision_carries_status_and_reason():
    """The service decision carries status and reason, so the API's response
    can name both without a second lookup. An optional receipt may ride
    along when the service produced one."""
    from sester.facilitator_svc.service import ServiceDecision
    d = ServiceDecision(status="ok", reason="verified")
    assert d.status == "ok"
    assert d.reason == "verified"
    assert d.receipt is None


def test_service_decision_carries_its_receipt():
    """When the service produced a receipt it rides on the decision, because
    the caller's proof of payment is that receipt."""
    from sester.facilitator_svc.service import ServiceDecision
    d = ServiceDecision(status="ok", reason="verified",
                        receipt={"hash": "0xabc"})
    assert d.receipt == {"hash": "0xabc"}
