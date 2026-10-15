"""`AgentTrace` mirroring `contracts/schemas/agent_trace.schema.json`; decisions, never reasoning."""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from tactistream.contracts.claim import AnalystOutput, Claim, ProducerOutput, Verdict
from tactistream.contracts.common import (
    ClaimId,
    ContractModel,
    InsightId,
    Language,
    MatchId,
    Milliseconds,
    MomentId,
    SchemaVersion,
    TraceId,
    ViewerMode,
)
from tactistream.contracts.ws import FallbackReason

RunnerKind = Literal["three_agent", "single_agent", "deterministic"]
RunOutcome = Literal["released", "fallback", "abstained", "superseded", "cancelled"]
FixtureKind = Literal["bad_claim", "model_timeout"]
StepRole = Literal[
    "gate",
    "analyst",
    "verifier_precheck",
    "verifier",
    "producer",
    "checks",
    "fallback",
    "single_agent",
    "deterministic",
]
StepStatus = Literal["ok", "timeout", "model_error", "skipped", "failed"]
ToolName = Literal[
    "get_match_snapshot", "get_event_window", "get_metric", "inspect_geometry", "build_recap_candidates"
]
ToolErrorCode = Literal[
    "future_evidence",
    "unknown_metric",
    "unknown_event",
    "invalid_window",
    "invalid_params",
    "insufficient_tracking",
]
ClaimStatus = Literal["proposed", "approved", "rejected", "revised", "superseded", "unused"]
CheckCode = Literal[
    "unsupported_number",
    "unsupported_player",
    "unknown_evidence",
    "invalid_timing",
    "expired",
    "unapproved_claim",
    "unrequested_annotation",
    "unresolvable_annotation",
    "future_evidence",
    "title_mismatch",
    "unknown_template",
    "causal_overreach",
    "variant_inconsistent",
    "schema_invalid",
]
Attempt = Annotated[int, Field(ge=1, le=2)]
NonNegative = Annotated[int, Field(ge=0)]


class Usage(ContractModel):
    _required_nullable: ClassVar[tuple[str, ...]] = ("tokens_in", "tokens_out")

    model_calls: NonNegative
    tokens_in: NonNegative | None = None
    tokens_out: NonNegative | None = None


class ToolCallRecord(ContractModel):
    tool: ToolName
    args: dict[str, Any]
    status: Literal["ok", "error"]
    error_code: ToolErrorCode | None = None
    result_ids: list[str]
    latency_ms: NonNegative


class TraceCheckFailure(ContractModel):
    code: CheckCode
    detail: Annotated[str, StringConstraints(max_length=200)]
    mode: ViewerMode | None = None
    language: Language | None = None


class TraceStep(ContractModel):
    index: NonNegative
    role: StepRole
    attempt: Attempt
    prompt_version: Annotated[str, StringConstraints(pattern=r"^[a-z_]+\.v[0-9]+$")] | None = None
    started_ms: NonNegative
    latency_ms: NonNegative
    budget_ms: NonNegative | None = None
    status: StepStatus
    error: Annotated[str, StringConstraints(max_length=200)] | None = None
    injected_fault: FixtureKind | None = None
    input_ids: list[str]
    tool_calls: list[ToolCallRecord]
    analyst_output: AnalystOutput | None = None
    verdicts: list[Verdict] | None = None
    producer_output: ProducerOutput | None = None
    check_failures: list[TraceCheckFailure] | None = None
    usage: Usage | None = None


class ClaimTraceEntry(ContractModel):
    claim: Claim
    attempt: Attempt
    precheck: Verdict | None = None
    model_verdict: Verdict | None = None
    final: Verdict | None = None
    status: ClaimStatus
    superseded_by: ClaimId | None = None
    injected_fault: Literal["bad_claim"] | None = None


class AgentTrace(ContractModel):
    schema_version: SchemaVersion
    trace_id: TraceId
    match_id: MatchId
    moment_id: MomentId
    insight_id: InsightId
    insight_version: Annotated[int, Field(ge=1)]
    state_version: NonNegative
    as_of_session_ms: Milliseconds
    runner: RunnerKind
    outcome: RunOutcome
    fallback_reason: FallbackReason | None = None
    fixture: FixtureKind | None = None
    model_deployment: str | None = None
    trigger_receipt_ms: NonNegative
    deadline_ms: NonNegative
    started_ms: NonNegative
    finished_ms: NonNegative
    narrative_latency_ms: NonNegative | None = None
    steps: list[TraceStep]
    claims: list[ClaimTraceEntry]
    producer_output: ProducerOutput | None = None
    check_failures: list[TraceCheckFailure] | None = None
    released_claim_ids: list[ClaimId] | None = None
    usage: Usage

    @model_validator(mode="after")
    def _invariants(self) -> Self:
        if self.finished_ms < self.started_ms:
            raise ValueError("finished_ms must not be before started_ms")
        reason = self.fallback_reason
        if self.outcome == "fallback" and (reason is None or reason == "insufficient_tracking"):
            raise ValueError("a fallback outcome needs a fallback_reason other than insufficient_tracking")
        if self.outcome == "released" and reason not in (None, "expired"):
            raise ValueError("a released outcome allows only fallback_reason 'expired'")
        if self.outcome == "abstained" and reason != "insufficient_tracking":
            raise ValueError("an abstained outcome needs fallback_reason 'insufficient_tracking'")
        indices = [step.index for step in self.steps]
        if indices != list(range(len(indices))):
            raise ValueError(f"step index values must be contiguous from 0, got {indices}")
        approved = {entry.claim.claim_id for entry in self.claims if entry.status == "approved"}
        for claim_id in self.released_claim_ids or []:
            if claim_id not in approved:
                raise ValueError(f"released claim {claim_id} is not approved")
        return self
