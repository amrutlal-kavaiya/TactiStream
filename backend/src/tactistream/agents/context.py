"""Immutable per-run workflow context, deadline budgets and the append-only claim ledger."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Literal

from tactistream.agents.model_client import ModelClient, Role
from tactistream.api.evidence import EvidenceIndex
from tactistream.contracts import CandidateMoment, Claim, MatchMetadata, MetricResult, Verdict
from tactistream.contracts.trace import ClaimStatus, FixtureKind
from tactistream.contracts.ws import FallbackReason, NarrativeStage
from tactistream.narrative.templates import Catalog
from tactistream.transport.clock import Clock

__all__ = [
    "MIN_STEP_MS",
    "AgentBudgets",
    "ClaimLedger",
    "ClaimRecord",
    "ClaimStatus",
    "FallbackReason",
    "FixtureKind",
    "NarrativePrefs",
    "NarrativeStage",
    "WorkflowContext",
    "WorkflowDeps",
    "make_context",
]

MIN_STEP_MS: Mapping[Role, int] = {"analyst": 800, "verifier": 600, "producer": 600, "single_agent": 800}
_DOWNSTREAM: Mapping[Role, tuple[Role, ...]] = {
    "analyst": ("verifier", "producer"),
    "verifier": ("producer",),
    "producer": (),
    "single_agent": (),
}
_STATUS_BY_DECISION: Mapping[str, ClaimStatus] = {
    "approve": "approved",
    "reject": "rejected",
    "revise": "proposed",
}


@dataclass(frozen=True)
class AgentBudgets:
    caps_ms: Mapping[Role, int]
    min_ms: Mapping[Role, int]
    reserve_ms: int = 400
    token_budget: int | None = None
    repair_min_remaining_ms: int = 3000
    deadline_ms: int = 8000


@dataclass(frozen=True)
class NarrativePrefs:
    pinned_player_id: str | None = None


@dataclass
class ClaimRecord:
    claim: Claim
    attempt: Literal[1, 2]
    precheck: Verdict | None = None
    model_verdict: Verdict | None = None
    final: Verdict | None = None
    status: ClaimStatus = "proposed"
    superseded_by: str | None = None
    injected_fault: FixtureKind | None = None


class ClaimLedger:
    """Append-only record of every claim proposed in one run; IDs are `clm-{trigger_seq:04d}-{n}`."""

    def __init__(self, trigger_sequence: int) -> None:
        self._prefix = f"clm-{trigger_sequence:04d}-"
        self._issued = 0
        self._records: dict[str, ClaimRecord] = {}

    @classmethod
    def for_moment(cls, moment: CandidateMoment) -> ClaimLedger:
        return cls(int(moment.moment_id.removeprefix("mom-")))

    def next_claim_id(self) -> str:
        self._issued += 1
        return f"{self._prefix}{self._issued}"

    def add(self, record: ClaimRecord) -> None:
        claim_id = record.claim.claim_id
        if claim_id in self._records:
            raise ValueError(f"claim {claim_id} is already in the ledger")
        self._records[claim_id] = record

    def get(self, claim_id: str) -> ClaimRecord:
        record = self._records.get(claim_id)
        if record is None:
            raise KeyError(f"unknown claim {claim_id}")
        return record

    def set_verdicts(self, claim_id: str, pre: Verdict, model: Verdict | None, final: Verdict) -> None:
        """`approve` → approved, `reject` → rejected; `revise` stays proposed until repaired or given up."""
        record = self.get(claim_id)
        record.precheck, record.model_verdict, record.final = pre, model, final
        record.status = _STATUS_BY_DECISION[final.decision]

    def set_status(self, claim_id: str, status: ClaimStatus, *, superseded_by: str | None = None) -> None:
        record = self.get(claim_id)
        record.status = status
        if superseded_by is not None:
            record.superseded_by = superseded_by

    def approved(self) -> list[Claim]:
        return [r.claim for r in self._records.values() if r.status == "approved"]

    def needing_revision(self) -> list[ClaimRecord]:
        return [
            r
            for r in self._records.values()
            if r.status == "proposed" and r.final is not None and r.final.decision == "revise"
        ]

    def records(self) -> Sequence[ClaimRecord]:
        return tuple(self._records.values())


@dataclass(frozen=True)
class WorkflowDeps:
    client: ModelClient | None
    catalog: Catalog
    metadata: MatchMetadata
    evidence: EvidenceIndex
    clock: Clock
    session_clock_ms: Callable[[], int]
    budgets: AgentBudgets
    min_tracking_coverage: float
    on_stage: Callable[[NarrativeStage], Awaitable[None]]


@dataclass(frozen=True)
class WorkflowContext:
    match_id: str
    moment: CandidateMoment
    as_of_ms: int
    state_version: int
    metrics: Mapping[str, MetricResult]
    ledger: ClaimLedger
    prefs: NarrativePrefs
    trigger_receipt_ms: int
    deadline_ms: int
    trace_id: str
    insight_id: str
    insight_version: int
    fixture: FixtureKind | None
    deps: WorkflowDeps = field(repr=False)

    def remaining_ms(self) -> int:
        return self.deadline_ms - self.deps.clock.now_ms()

    def budget_ms(self, role: Role) -> int:
        """`min(cap, remaining - reserve - downstream minimums)`; below `min_ms[role]` skip the step."""
        budgets = self.deps.budgets
        downstream = sum(budgets.min_ms[r] for r in _DOWNSTREAM[role])
        return min(budgets.caps_ms[role], self.remaining_ms() - budgets.reserve_ms - downstream)

    def with_fixture(self, fixture: FixtureKind | None) -> WorkflowContext:
        return replace(self, fixture=fixture)


def make_context(
    moment: CandidateMoment,
    *,
    metrics: Mapping[str, MetricResult],
    deps: WorkflowDeps,
    trigger_receipt_ms: int,
    trace_id: str,
    deadline_after_ms: int | None = None,
    insight_version: int = 1,
    prefs: NarrativePrefs | None = None,
    fixture: FixtureKind | None = None,
) -> WorkflowContext:
    """Context for one run of `moment`, as of its window end; deadline = receipt + narrative deadline."""
    after = deps.budgets.deadline_ms if deadline_after_ms is None else deadline_after_ms
    sequence = moment.moment_id.removeprefix("mom-")
    return WorkflowContext(
        match_id=moment.match_id,
        moment=moment,
        as_of_ms=moment.window.end_ms,
        state_version=moment.state_version,
        metrics=metrics,
        ledger=ClaimLedger.for_moment(moment),
        prefs=prefs or NarrativePrefs(),
        trigger_receipt_ms=trigger_receipt_ms,
        deadline_ms=trigger_receipt_ms + after,
        trace_id=trace_id,
        insight_id=f"ins-{sequence}",
        insight_version=insight_version,
        fixture=fixture,
        deps=deps,
    )
