"""Live match state built from feed envelopes; deduplicated, order-independent and versioned."""

from __future__ import annotations

import bisect
import hashlib
import json
from dataclasses import dataclass, field

from tactistream.contracts import FeedEnvelope, MatchEvent, MatchMetadata, TrackingFrame


@dataclass(frozen=True)
class StateDelta:
    state_version: int
    new_events: list[MatchEvent] = field(default_factory=list)
    new_frame: TrackingFrame | None = None
    duplicate: bool = False
    new_metadata: MatchMetadata | None = None
    server_receipt_ms: int | None = None


class MatchState:
    """Metadata, events ordered by `sequence`, and the newest tracking frame.

    Every newly accepted metadata/event/frame record bumps `state_version`; a repeated
    (`kind`, `record_id`) is reported as a duplicate and changes nothing. Other kinds are ignored.
    """

    def __init__(self) -> None:
        self.metadata: MatchMetadata | None = None
        self.events: list[MatchEvent] = []
        self.latest_frame: TrackingFrame | None = None
        self.state_version = 0
        self._envelopes: dict[tuple[str, str], FeedEnvelope] = {}

    def apply(self, envelope: FeedEnvelope) -> StateDelta:
        key = (envelope.kind, envelope.record_id)
        if key in self._envelopes:
            return StateDelta(state_version=self.state_version, duplicate=True)
        payload = envelope.payload
        delta_events: list[MatchEvent] = []
        delta_frame: TrackingFrame | None = None
        delta_metadata: MatchMetadata | None = None
        if isinstance(payload, MatchMetadata):
            self.metadata = delta_metadata = payload
        elif isinstance(payload, MatchEvent):
            bisect.insort(self.events, payload, key=lambda e: e.sequence)
            delta_events = [payload]
        elif isinstance(payload, TrackingFrame):
            if self.latest_frame is None or payload.frame_index > self.latest_frame.frame_index:
                self.latest_frame = delta_frame = payload
        else:
            return StateDelta(state_version=self.state_version)
        self._envelopes[key] = envelope
        self.state_version += 1
        return StateDelta(
            state_version=self.state_version,
            new_events=delta_events,
            new_frame=delta_frame,
            new_metadata=delta_metadata,
            server_receipt_ms=envelope.server_receipt_ms,
        )

    def envelope(self, kind: str, record_id: str) -> FeedEnvelope | None:
        """The accepted envelope for a record, including its `server_receipt_ms` stamp."""
        return self._envelopes.get((kind, record_id))

    def state_hash(self) -> str:
        """sha256 of canonical JSON of metadata, ordered events and latest frame (version-independent)."""

        def dump(model: MatchMetadata | MatchEvent | TrackingFrame | None) -> object:
            return None if model is None else model.model_dump(mode="json", exclude_none=True)

        canonical = json.dumps(
            {
                "metadata": dump(self.metadata),
                "events": [dump(e) for e in self.events],
                "latest_frame": dump(self.latest_frame),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
