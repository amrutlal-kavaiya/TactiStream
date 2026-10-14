"""`CandidateMoment` mirroring `contracts/schemas/candidate_moment.schema.json`."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from tactistream.contracts.common import (
    ContractModel,
    EventId,
    MatchId,
    MetricId,
    MomentId,
    MomentPattern,
    PlayerId,
    SchemaVersion,
    TimeWindow,
)


class CandidateMoment(ContractModel):
    """A deterministic, ranked window worth explaining. Never carries scenario labels."""

    schema_version: SchemaVersion
    match_id: MatchId
    moment_id: MomentId
    pattern: MomentPattern
    trigger_event_id: EventId
    window: TimeWindow
    involved_player_ids: list[PlayerId]
    metric_ids: list[MetricId]
    tracking_coverage: Annotated[float, Field(ge=0, le=1)] | None = None
    rank_score: float
    state_version: Annotated[int, Field(ge=0)]
