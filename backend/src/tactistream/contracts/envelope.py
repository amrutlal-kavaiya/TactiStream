"""`FeedEnvelope` mirroring `contracts/schemas/feed_envelope.schema.json`."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, ValidationInfo, field_validator

from tactistream.contracts.common import ContractModel, MatchId, SchemaVersion
from tactistream.contracts.event import MatchEvent
from tactistream.contracts.insight import InsightPacket
from tactistream.contracts.match import MatchMetadata
from tactistream.contracts.payload import parse_payload
from tactistream.contracts.tracking import TrackingFrame

EnvelopeKind = Literal["metadata", "event", "frame", "insight", "agent_trace", "latency"]
EnvelopePayload = MatchMetadata | MatchEvent | TrackingFrame | InsightPacket | dict[str, Any]

_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "metadata": MatchMetadata,
    "event": MatchEvent,
    "frame": TrackingFrame,
    "insight": InsightPacket,
}


class FeedEnvelope(ContractModel):
    """Unit published on the FeedBus. `(kind, record_id)` is the dedupe key; payload is typed by `kind`."""

    schema_version: SchemaVersion
    kind: EnvelopeKind
    match_id: MatchId
    record_id: Annotated[str, StringConstraints(min_length=1)]
    published_ms: Annotated[int, Field(ge=0)]
    server_receipt_ms: Annotated[int, Field(ge=0)] | None = None
    payload: EnvelopePayload

    @field_validator("payload", mode="plain")
    @classmethod
    def _typed_payload(cls, value: object, info: ValidationInfo) -> BaseModel | dict[str, Any]:
        return parse_payload(_PAYLOAD_MODELS, info.data.get("kind"), value)
