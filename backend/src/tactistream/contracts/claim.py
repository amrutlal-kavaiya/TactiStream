"""Claim ledger types mirroring `contracts/schemas/claim.schema.json`."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from tactistream.contracts.common import (
    AnnotationId,
    ClaimId,
    ContractModel,
    EventId,
    EvidenceId,
    MetricId,
    MomentId,
    Panel,
    PlayerId,
    Priority,
    TeamId,
)
from tactistream.contracts.metric import MetricUnit

SlotKind = Literal["player", "team", "metric", "event_time"]
ClaimKind = Literal["fact", "interpretation"]
Uncertainty = Literal["low", "medium", "high"]
AbstainReason = Literal["insufficient_tracking", "no_supported_interpretation", "timeout"]
Decision = Literal["approve", "revise", "reject"]
ReasonCode = Literal[
    "ok",
    "missing_evidence_id",
    "future_evidence",
    "value_mismatch",
    "unit_mismatch",
    "unsupported_causality",
    "counterevidence",
    "insufficient_tracking",
    "template_kind_mismatch",
]


class SlotValue(ContractModel):
    kind: SlotKind
    player_id: PlayerId | None = None
    team_id: TeamId | None = None
    metric_id: MetricId | None = None
    event_id: EventId | None = None
    value: float | None = None
    unit: MetricUnit | None = None


class Claim(ContractModel):
    claim_id: ClaimId
    kind: ClaimKind
    template_id: Annotated[str, StringConstraints(pattern=r"^(fact|interp)\.[a-z_]+$")]
    slots: dict[str, SlotValue]
    evidence_ids: Annotated[list[EvidenceId], Field(min_length=1)]
    uncertainty: Uncertainty
    requested_annotations: list[AnnotationId] | None = None
    rationale: Annotated[str, StringConstraints(max_length=280)] | None = None


class AnalystOutput(ContractModel):
    moment_id: MomentId
    claims: Annotated[list[Claim], Field(max_length=2)]
    abstained: bool
    abstain_reason: AbstainReason | None = None


class Verdict(ContractModel):
    claim_id: ClaimId
    decision: Decision
    reason_codes: list[ReasonCode]
    note: Annotated[str, StringConstraints(max_length=200)] | None = None


class VerifierOutput(ContractModel):
    moment_id: MomentId
    verdicts: list[Verdict]


class ModePlan(ContractModel):
    title_template_id: Annotated[str, StringConstraints(pattern=r"^title\.[a-z_]+$")]
    claim_ids: Annotated[list[ClaimId], Field(min_length=1, max_length=2)]
    annotations: list[AnnotationId]
    priority: Priority
    panel: Panel


class ProducerOutput(ContractModel):
    moment_id: MomentId
    fan: ModePlan
    analyst: ModePlan
