"""`MetricResult` mirroring `contracts/schemas/metric_result.schema.json`."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from tactistream.contracts.common import (
    ContractModel,
    EventId,
    FrameId,
    MatchId,
    MetricId,
    MetricKind,
    PlayerId,
    SchemaVersion,
    TimeWindow,
)

MetricStatus = Literal["ok", "unavailable"]
UnavailableReason = Literal["insufficient_tracking", "missing_events", "not_applicable"]
MetricUnit = Literal["m", "ratio", "per_min", "score_0_100", "count", "cosine"]

MetricWindow = TimeWindow


class MetricInputs(ContractModel):
    event_ids: list[EventId]
    frame_ids: list[FrameId]
    excluded_count: Annotated[int, Field(ge=0)] | None = None


class MetricResult(ContractModel):
    schema_version: SchemaVersion
    match_id: MatchId
    metric_id: MetricId
    kind: MetricKind
    definition_version: Annotated[str, StringConstraints(pattern=r"^[a-z_]+\.v[0-9]+$")]
    status: MetricStatus
    unavailable_reason: UnavailableReason | None = None
    value: float | None = None
    unit: MetricUnit | None = None
    components: dict[str, float] | None = None
    subject_ids: list[PlayerId] | None = None
    window: MetricWindow
    inputs: MetricInputs
    params: dict[str, float] | None = None
    limitation_key: str | None = None
    state_version: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def _check_status(self) -> Self:
        if self.status == "ok":
            if self.value is None or self.unit is None:
                raise ValueError("status 'ok' requires value and unit")
        else:
            if self.unavailable_reason is None:
                raise ValueError("status 'unavailable' requires unavailable_reason")
            if self.value is not None:
                raise ValueError("status 'unavailable' must not carry a value")
        return self
