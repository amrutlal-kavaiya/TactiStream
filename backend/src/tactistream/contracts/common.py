"""Shared definitions mirroring `contracts/schemas/common.schema.json`."""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    StringConstraints,
    model_serializer,
)


class ContractModel(BaseModel):
    """Base for every contract model: immutable, unknown fields rejected.

    Fields listed in `_required_nullable` are required-but-nullable in the schema, so they are kept as
    `null` even when dumping with `exclude_none=True`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    _required_nullable: ClassVar[tuple[str, ...]] = ()

    @model_serializer(mode="wrap")
    def _keep_required_nulls(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo) -> Any:
        data = handler(self)
        if info.exclude_none and self._required_nullable and isinstance(data, dict):
            for name in self._required_nullable:
                if getattr(self, name) is None:
                    data[name] = None
        return data


SchemaVersion = Annotated[str, StringConstraints(pattern=r"^1\.[0-9]+$")]
Milliseconds = Annotated[int, Field(ge=0)]
MatchId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")]
TeamId = Literal["blue", "amber"]
PlayerId = Annotated[str, StringConstraints(pattern=r"^(blue|amber)-[0-9]{2}$")]
EventId = Annotated[str, StringConstraints(pattern=r"^evt-[0-9]{4,}$")]
FrameId = Annotated[str, StringConstraints(pattern=r"^frm-[0-9]{6,}$")]
MetricId = Annotated[str, StringConstraints(pattern=r"^metric-[a-z_]+-[0-9]{4,}(-(blue|amber)-[0-9]{2})?$")]
MomentId = Annotated[str, StringConstraints(pattern=r"^mom-[0-9]{4,}$")]
InsightId = Annotated[str, StringConstraints(pattern=r"^ins-[0-9]{4,}$")]
ClaimId = Annotated[str, StringConstraints(pattern=r"^clm-[0-9]{4,}-[0-9]+$")]
EvidenceId = EventId | FrameId | MetricId
TraceId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
AnnotationId = Annotated[
    str,
    StringConstraints(
        pattern=r"^(highlight|path|pressure_ring)_(blue|amber)_[0-9]{2}$|^show_channel_[0-9]{4,}$"
    ),
]

PointX = Annotated[float, Field(ge=-5, le=110)]
PointY = Annotated[float, Field(ge=-5, le=73)]
PointM = tuple[PointX, PointY]
"""Stadium-fixed position in metres; pitch 105 x 68, origin bottom-left."""

SourceKind = Literal["synthetic", "event_feed_aligned_to_video", "video_derived"]
ViewerMode = Literal["fan", "analyst"]
Language = Literal["en", "hi"]
MetricKind = Literal[
    "pass_completion",
    "forward_progress",
    "rhythm",
    "pressure",
    "channel",
    "receiver_separation",
    "defender_follow",
    "off_ball_run",
    "contribution",
]
MomentPattern = Literal["space_creation", "press_turnover", "switch_escape", "shot", "generic"]
ClaimStatus = Literal["verified_fact", "interpretation_supported", "insufficient_data", "fallback_template"]
Panel = Literal["lower_third", "side_panel"]
Priority = Annotated[int, Field(ge=1, le=3)]


class Provenance(ContractModel):
    kind: SourceKind
    generator_version: str | None = None
    seed: int | None = None


class TimeWindow(ContractModel):
    start_ms: Milliseconds
    end_ms: Milliseconds
