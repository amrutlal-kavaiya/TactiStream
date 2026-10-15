"""`Recap` mirroring `contracts/schemas/recap.schema.json`."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from tactistream.contracts.common import (
    AnnotationId,
    ContractModel,
    EvidenceId,
    InsightId,
    Language,
    MatchId,
    Milliseconds,
    MomentId,
    PlayerId,
    SchemaVersion,
    TimeWindow,
    ViewerMode,
)

Involvement = Literal["direct", "off_ball", "none"]


class RecapItem(ContractModel):
    rank: Annotated[int, Field(ge=1)]
    moment_id: MomentId
    insight_id: InsightId
    replay_window: TimeWindow
    title: Annotated[str, StringConstraints(max_length=80)]
    pinned_player_involvement: Involvement | None = None
    evidence_ids: Annotated[list[EvidenceId], Field(min_length=1)]


class OverlayCue(ContractModel):
    """A timed overlay on the recap-relative clock (ms from recap start)."""

    start_ms: Milliseconds
    end_ms: Milliseconds
    insight_id: InsightId
    text: Annotated[str, StringConstraints(max_length=200)]
    annotations: list[AnnotationId]


class Recap(ContractModel):
    schema_version: SchemaVersion
    recap_id: Annotated[str, StringConstraints(pattern=r"^recap-[a-z0-9-]+$")]
    match_id: MatchId
    mode: ViewerMode
    language: Language
    pinned_player_id: PlayerId | None = None
    generated_at_state_version: Annotated[int, Field(ge=0)]
    summary: Annotated[str, StringConstraints(max_length=600)]
    items: Annotated[list[RecapItem], Field(min_length=1, max_length=8)]
    overlay_track: list[OverlayCue]
