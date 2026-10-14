"""`InsightPacket` (`insight_packet.schema.json`) and `InsightBundle` (`ws_message.schema.json`)."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from tactistream.contracts.common import (
    AnnotationId,
    ClaimId,
    ClaimStatus,
    ContractModel,
    EvidenceId,
    InsightId,
    Language,
    MatchId,
    Milliseconds,
    MomentId,
    Panel,
    Priority,
    SchemaVersion,
    SourceKind,
    TimeWindow,
    TraceId,
    ViewerMode,
)

InsightLabel = Literal["synthetic", "interpretation", "partial_tracking", "fallback"]


class RenderSpec(ContractModel):
    clock: Literal["session_clock_ms"]
    show_from_ms: Milliseconds
    show_until_ms: Milliseconds
    priority: Priority
    panel: Panel
    annotations: list[AnnotationId]
    replay_window: TimeWindow | None = None


class InsightPacket(ContractModel):
    """Render instruction for one (mode, language) variant of one insight version."""

    schema_version: SchemaVersion
    insight_id: InsightId
    insight_version: Annotated[int, Field(ge=1)]
    match_id: MatchId
    moment_id: MomentId
    state_version: Annotated[int, Field(ge=0)]
    as_of_session_ms: Milliseconds
    mode: ViewerMode
    language: Language
    source_kind: SourceKind
    claim_status: ClaimStatus
    title: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    body: Annotated[str, StringConstraints(min_length=1, max_length=400)]
    labels: list[InsightLabel] | None = None
    evidence_ids: Annotated[list[EvidenceId], Field(min_length=1)]
    claim_ids: list[ClaimId]
    render: RenderSpec
    expires_at_session_ms: Milliseconds
    trace_id: TraceId

    @model_validator(mode="after")
    def _check_timing(self) -> Self:
        if self.render.show_until_ms <= self.render.show_from_ms:
            raise ValueError("render.show_until_ms must be greater than render.show_from_ms")
        if self.expires_at_session_ms < self.render.show_until_ms:
            raise ValueError("expires_at_session_ms must not be before render.show_until_ms")
        return self


class InsightBundle(ContractModel):
    """All (mode x language) variants of one insight version so switching is instant and consistent."""

    insight_id: InsightId
    insight_version: Annotated[int, Field(ge=1)]
    variants: Annotated[list[InsightPacket], Field(min_length=1, max_length=4)]
