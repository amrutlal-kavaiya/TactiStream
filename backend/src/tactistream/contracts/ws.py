"""WebSocket messages on `/ws/matches/{match_id}` mirroring `contracts/schemas/ws_message.schema.json`."""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationInfo, field_validator

from tactistream.contracts.common import (
    ContractModel,
    InsightId,
    Language,
    MatchId,
    Milliseconds,
    MomentId,
    PlayerId,
    TraceId,
    ViewerMode,
)
from tactistream.contracts.event import MatchEvent
from tactistream.contracts.insight import InsightBundle
from tactistream.contracts.match import MatchMetadata
from tactistream.contracts.metric import MetricResult
from tactistream.contracts.moment import CandidateMoment
from tactistream.contracts.payload import parse_payload
from tactistream.contracts.tracking import TrackingFrame

ServerMessageType = Literal[
    "snapshot",
    "event",
    "frame",
    "metric",
    "moment",
    "insight",
    "insight_revoked",
    "narrative_status",
    "heartbeat",
    "error",
]
RevokeReason = Literal["late_event_revision", "expired", "superseded"]
NarrativeStage = Literal[
    "analysing", "verifying", "producing", "checking", "released", "fallback", "abstained"
]
FallbackReason = Literal[
    "timeout", "verifier_rejected", "output_check_failed", "model_error", "expired", "insufficient_tracking"
]
PlaybackStateName = Literal["playing", "paused", "ended"]


class InsightRevoked(ContractModel):
    insight_id: InsightId
    insight_version: Annotated[int, Field(ge=1)]
    reason: RevokeReason


class NarrativeStatus(ContractModel):
    moment_id: MomentId
    stage: NarrativeStage
    fallback_reason: FallbackReason | None = None
    trace_id: TraceId | None = None


class SnapshotPlayback(ContractModel):
    state: PlaybackStateName
    speed: Annotated[float, Field(gt=0, le=4)]
    seed: int


class Snapshot(ContractModel):
    _required_nullable: ClassVar[tuple[str, ...]] = ("latest_frame",)

    metadata: MatchMetadata
    state_version: Annotated[int, Field(ge=0)]
    session_clock_ms: Milliseconds
    events: list[MatchEvent]
    latest_frame: TrackingFrame | None
    moments: list[CandidateMoment]
    insights: list[InsightBundle]
    playback: SnapshotPlayback


ServerPayload = (
    Snapshot
    | MatchEvent
    | TrackingFrame
    | MetricResult
    | CandidateMoment
    | InsightBundle
    | InsightRevoked
    | NarrativeStatus
    | dict[str, Any]
)

_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "snapshot": Snapshot,
    "event": MatchEvent,
    "frame": TrackingFrame,
    "metric": MetricResult,
    "moment": CandidateMoment,
    "insight": InsightBundle,
    "insight_revoked": InsightRevoked,
    "narrative_status": NarrativeStatus,
}


class ServerMessage(ContractModel):
    """Server → client frame. `seq` is monotonic per match stream; payload is typed by `type`."""

    type: ServerMessageType
    seq: Annotated[int, Field(ge=0)]
    match_id: MatchId
    server_receipt_ms: Annotated[int, Field(ge=0)] | None = None
    payload: ServerPayload

    @field_validator("payload", mode="plain")
    @classmethod
    def _typed_payload(cls, value: object, info: ValidationInfo) -> BaseModel | dict[str, Any]:
        return parse_payload(_PAYLOAD_MODELS, info.data.get("type"), value)


class ResumeMsg(ContractModel):
    type: Literal["resume"]
    last_seq: Annotated[int, Field(ge=-1)]


class PrefsMsg(ContractModel):
    type: Literal["prefs"]
    mode: ViewerMode
    language: Language
    pinned_player_id: PlayerId | None = None


class DisplayAckMsg(ContractModel):
    type: Literal["display_ack"]
    target_kind: Literal["event", "insight"]
    target_id: str
    server_seq: Annotated[int, Field(ge=0)]


ClientMessage = Annotated[ResumeMsg | PrefsMsg | DisplayAckMsg, Field(discriminator="type")]

client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def parse_client_message(data: str | bytes) -> ResumeMsg | PrefsMsg | DisplayAckMsg:
    """Parse one client JSON text frame; raises `pydantic.ValidationError` on unknown or malformed input."""
    return client_message_adapter.validate_json(data)
