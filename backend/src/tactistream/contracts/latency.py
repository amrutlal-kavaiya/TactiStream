"""`LatencySample` mirroring `contracts/schemas/latency_sample.schema.json`."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from tactistream.contracts.common import ContractModel, MatchId, Milliseconds, SchemaVersion, TraceId
from tactistream.contracts.ws import FallbackReason

LatencyKind = Literal["fast_overlay", "narrative"]
LatencyOutcome = Literal["released", "fallback", "abstained"]


class LatencySample(ContractModel):
    schema_version: SchemaVersion = "1.0"
    sample_id: Annotated[str, Field(min_length=1)]
    match_id: MatchId
    kind: LatencyKind
    value_ms: Milliseconds
    outcome: LatencyOutcome
    fallback_reason: FallbackReason | None = None
    target_id: Annotated[str, Field(min_length=1)]
    viewer_id: Annotated[str, Field(min_length=1)]
    trace_id: TraceId | None = None
    config: Annotated[str, Field(min_length=1)] = "live"
    recorded_ms: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def _fallback_needs_reason(self) -> LatencySample:
        if self.kind == "narrative" and self.outcome == "fallback" and self.fallback_reason is None:
            raise ValueError("fallback_reason is required for a narrative fallback sample")
        return self
