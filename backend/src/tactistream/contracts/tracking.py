"""`TrackingFrame` mirroring `contracts/schemas/tracking_frame.schema.json`.

Unavailable entities carry `visible=False` and no position; positions are never fabricated.
"""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import Field, model_validator

from tactistream.contracts.common import (
    ContractModel,
    FrameId,
    MatchId,
    Milliseconds,
    PlayerId,
    PointM,
    Provenance,
    SchemaVersion,
)


def _check_visibility(visible: bool, pos_m: PointM | None) -> None:
    if visible and pos_m is None:
        raise ValueError("visible entities require pos_m")
    if not visible and pos_m is not None:
        raise ValueError("invisible entities must not carry pos_m")


class PlayerPosition(ContractModel):
    player_id: PlayerId
    visible: bool
    pos_m: PointM | None = None

    @model_validator(mode="after")
    def _visible_iff_position(self) -> Self:
        _check_visibility(self.visible, self.pos_m)
        return self


class BallPosition(ContractModel):
    visible: bool
    pos_m: PointM | None = None
    height_m: Annotated[float, Field(ge=0, le=30)] | None = None

    @model_validator(mode="after")
    def _visible_iff_position(self) -> Self:
        _check_visibility(self.visible, self.pos_m)
        return self


class TrackingFrame(ContractModel):
    schema_version: SchemaVersion
    match_id: MatchId
    frame_id: FrameId
    frame_index: Annotated[int, Field(ge=0)]
    period: Annotated[int, Field(ge=1, le=2)]
    period_clock_ms: Milliseconds
    session_clock_ms: Milliseconds
    players: list[PlayerPosition]
    ball: BallPosition
    source: Provenance
