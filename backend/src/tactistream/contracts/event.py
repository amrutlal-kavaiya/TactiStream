"""`MatchEvent` mirroring `contracts/schemas/event.schema.json`."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, model_validator

from tactistream.contracts.common import (
    ContractModel,
    EventId,
    MatchId,
    Milliseconds,
    PlayerId,
    PointM,
    Provenance,
    SchemaVersion,
    TeamId,
)

EventType = Literal[
    "kickoff",
    "pass",
    "carry",
    "pressure",
    "tackle",
    "interception",
    "ball_recovery",
    "shot",
    "clearance",
    "out_of_play",
    "period_end",
]
Outcome = (
    Literal["complete", "incomplete", "on_target", "off_target", "blocked", "goal", "won", "lost"] | None
)


class MatchEvent(ContractModel):
    _required_nullable: ClassVar[tuple[str, ...]] = ("outcome",)

    schema_version: SchemaVersion
    match_id: MatchId
    event_id: EventId
    sequence: Annotated[int, Field(ge=0)]
    period: Annotated[int, Field(ge=1, le=2)]
    period_clock_ms: Milliseconds
    session_clock_ms: Milliseconds
    event_type: EventType
    team_id: TeamId
    player_id: PlayerId
    recipient_id: PlayerId | None = None
    start_m: PointM
    end_m: PointM | None = None
    duration_ms: Milliseconds | None = None
    outcome: Outcome
    related_event_ids: list[EventId] | None = None
    source: Provenance

    @model_validator(mode="after")
    def _check_type_rules(self) -> Self:
        if self.event_type == "pass":
            if self.end_m is None or self.duration_ms is None:
                raise ValueError("pass events require end_m and duration_ms")
            if self.outcome == "complete" and self.recipient_id is None:
                raise ValueError("completed passes require recipient_id")
        if self.event_type in ("carry", "shot") and self.end_m is None:
            raise ValueError(f"{self.event_type} events require end_m")
        return self
