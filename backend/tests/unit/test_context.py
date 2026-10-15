import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from tactistream.agents.context import (
    MIN_STEP_MS,
    AgentBudgets,
    ClaimLedger,
    ClaimRecord,
    NarrativePrefs,
    WorkflowContext,
    WorkflowDeps,
    make_context,
)
from tactistream.agents.verifier import combine_verdicts
from tactistream.api.evidence import EvidenceIndex
from tactistream.contracts import AnalystOutput, CandidateMoment, Claim, MatchMetadata, Verdict
from tactistream.contracts.ws import NarrativeStage
from tactistream.narrative.templates import load_catalog
from tactistream.transport.clock import FakeClock

EXAMPLES = Path(__file__).parents[3] / "contracts" / "examples"
TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
RECEIPT_MS = 1_760_422_600_000


def example(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    return data


def claims() -> list[Claim]:
    return AnalystOutput.model_validate(example("analyst_output.json")).claims


def verdict(decision: str, *codes: str, note: str | None = None, claim_id: str = "clm-0045-2") -> Verdict:
    return Verdict.model_validate(
        {"claim_id": claim_id, "decision": decision, "reason_codes": list(codes), "note": note}
    )


def budgets() -> AgentBudgets:
    return AgentBudgets(
        caps_ms={"analyst": 3500, "verifier": 2500, "producer": 1500, "single_agent": 3500},
        min_ms=MIN_STEP_MS,
    )


async def no_stage(stage: NarrativeStage) -> None:
    return None


def context(clock: FakeClock, metadata: MatchMetadata, **overrides: Any) -> WorkflowContext:
    deps = WorkflowDeps(
        client=None,
        catalog=load_catalog(),
        metadata=metadata,
        evidence=EvidenceIndex(),
        clock=clock,
        session_clock_ms=lambda: 46_500,
        budgets=budgets(),
        min_tracking_coverage=0.8,
        on_stage=no_stage,
    )
    return make_context(
        CandidateMoment.model_validate(example("candidate_moment.json")),
        metrics={},
        deps=deps,
        trigger_receipt_ms=RECEIPT_MS,
        trace_id=TRACE_ID,
        **overrides,
    )


# --- ClaimLedger ------------------------------------------------------------------------------------------


def test_claim_ids_continue_across_attempts() -> None:
    ledger = ClaimLedger(trigger_sequence=45)
    assert [ledger.next_claim_id(), ledger.next_claim_id()] == ["clm-0045-1", "clm-0045-2"]
    assert ledger.next_claim_id() == "clm-0045-3"


def test_ledger_is_append_only() -> None:
    ledger = ClaimLedger(trigger_sequence=45)
    for claim in claims():
        ledger.add(ClaimRecord(claim=claim, attempt=1))
    assert not any(hasattr(ledger, name) for name in ("remove", "pop", "clear", "discard", "delete"))
    records = ledger.records()
    assert isinstance(records, tuple)
    assert [r.claim.claim_id for r in records] == ["clm-0045-1", "clm-0045-2"]
    with pytest.raises(ValueError, match="clm-0045-1"):
        ledger.add(ClaimRecord(claim=claims()[0], attempt=1))


def test_set_verdicts_on_unknown_claim_raises() -> None:
    ledger = ClaimLedger(trigger_sequence=45)
    with pytest.raises(KeyError, match="clm-0045-9"):
        ledger.set_verdicts("clm-0045-9", verdict("approve", "ok"), None, verdict("approve", "ok"))


def test_set_verdicts_updates_status() -> None:
    ledger = ClaimLedger(trigger_sequence=45)
    fact, interp = claims()
    ledger.add(ClaimRecord(claim=fact, attempt=1))
    ledger.add(ClaimRecord(claim=interp, attempt=1))
    ok = verdict("approve", "ok", claim_id="clm-0045-1")
    ledger.set_verdicts("clm-0045-1", ok, ok, ok)
    revise = verdict("revise", "value_mismatch")
    ledger.set_verdicts("clm-0045-2", revise, verdict("approve", "ok"), revise)
    assert ledger.get("clm-0045-1").status == "approved"
    assert ledger.get("clm-0045-2").status == "proposed"
    assert ledger.approved() == [fact]
    assert [r.claim.claim_id for r in ledger.needing_revision()] == ["clm-0045-2"]
    ledger.set_status("clm-0045-2", "revised", superseded_by="clm-0045-3")
    assert ledger.get("clm-0045-2").superseded_by == "clm-0045-3"
    assert ledger.needing_revision() == []


def test_rejected_verdict_marks_claim_rejected() -> None:
    ledger = ClaimLedger(trigger_sequence=45)
    ledger.add(ClaimRecord(claim=claims()[1], attempt=1))
    reject = verdict("reject", "future_evidence")
    ledger.set_verdicts("clm-0045-2", reject, None, reject)
    assert ledger.get("clm-0045-2").status == "rejected"
    assert ledger.approved() == []


def test_ledger_for_moment_parses_trigger_sequence() -> None:
    moment = CandidateMoment.model_validate(example("candidate_moment.json"))
    assert ClaimLedger.for_moment(moment).next_claim_id() == "clm-0045-1"


# --- combine_verdicts -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pre", "model", "decision"),
    [
        ("approve", "reject", "reject"),
        ("revise", "approve", "revise"),
        ("reject", "revise", "reject"),
        ("approve", "approve", "approve"),
        ("approve", "revise", "revise"),
    ],
)
def test_stricter_decision_wins(pre: str, model: str, decision: str) -> None:
    pre_codes = ["ok"] if pre == "approve" else ["value_mismatch"]
    model_codes = ["ok"] if model == "approve" else ["unsupported_causality"]
    combined = combine_verdicts(verdict(pre, *pre_codes), verdict(model, *model_codes))
    assert combined.decision == decision


def test_reason_codes_are_unioned_without_ok() -> None:
    combined = combine_verdicts(
        verdict("revise", "template_kind_mismatch", "value_mismatch", note="channel_gain 5.3 vs 3.4"),
        verdict("revise", "unsupported_causality", note="rationale asserts intent"),
    )
    assert combined.reason_codes == ["template_kind_mismatch", "value_mismatch", "unsupported_causality"]
    assert combined.note == "rationale asserts intent"
    assert combine_verdicts(verdict("revise", "value_mismatch"), verdict("approve", "ok")).reason_codes == [
        "value_mismatch"
    ]
    assert combine_verdicts(verdict("approve", "ok"), verdict("approve", "ok")).reason_codes == ["ok"]


def test_combine_without_model_verdict_is_the_precheck() -> None:
    pre = verdict("reject", "future_evidence", note="evt-0046 after as_of")
    assert combine_verdicts(pre, None) == pre


def test_note_falls_back_to_precheck_detail() -> None:
    combined = combine_verdicts(
        verdict("revise", "value_mismatch", note="5.3 vs 3.4"), verdict("approve", "ok")
    )
    assert combined.note == "5.3 vs 3.4"


def test_combine_rejects_different_claims() -> None:
    with pytest.raises(ValueError):
        combine_verdicts(verdict("approve", "ok"), verdict("approve", "ok", claim_id="clm-0045-1"))


# --- WorkflowContext --------------------------------------------------------------------------------------


def test_context_derives_ids_and_deadline(metadata: MatchMetadata) -> None:
    ctx = context(FakeClock(RECEIPT_MS), metadata)
    assert ctx.deadline_ms == RECEIPT_MS + 8000
    assert ctx.as_of_ms == 46_500
    assert ctx.state_version == 512
    assert ctx.insight_id == "ins-0045"
    assert ctx.insight_version == 1
    assert ctx.match_id == "demo-blue-amber-001"
    assert ctx.prefs == NarrativePrefs()
    assert ctx.fixture is None
    assert ctx.ledger.next_claim_id() == "clm-0045-1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.deadline_ms = 0  # type: ignore[misc]


def test_budgets_shrink_with_remaining_time(metadata: MatchMetadata) -> None:
    clock = FakeClock(RECEIPT_MS)
    ctx = context(clock, metadata)
    assert ctx.remaining_ms() == 8000
    assert ctx.budget_ms("analyst") == 3500
    assert ctx.budget_ms("verifier") == 2500
    assert ctx.budget_ms("producer") == 1500
    clock._now = RECEIPT_MS + 5000
    assert ctx.remaining_ms() == 3000
    assert ctx.budget_ms("analyst") == min(3500, 3000 - 400 - 600 - 600) == 1400
    assert ctx.budget_ms("producer") == min(1500, 3000 - 400)
    clock._now = RECEIPT_MS + 6000
    assert ctx.budget_ms("analyst") < ctx.deps.budgets.min_ms["analyst"]


def test_deadline_follows_the_configured_narrative_deadline(metadata: MatchMetadata) -> None:
    clock = FakeClock(RECEIPT_MS)
    ctx = context(clock, metadata, deadline_after_ms=5000, insight_version=2, fixture="bad_claim")
    assert ctx.deadline_ms == RECEIPT_MS + 5000
    assert ctx.insight_version == 2
    assert ctx.fixture == "bad_claim"
