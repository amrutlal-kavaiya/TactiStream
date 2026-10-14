"""Per-session evidence index: id -> (kind, record, availability time), resolved as of a session time."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tactistream.contracts import MatchEvent, MetricResult, TrackingFrame

EvidenceKind = Literal["event", "frame", "metric"]
EvidenceRecord = MatchEvent | TrackingFrame | MetricResult

_RECORD_TYPES: dict[EvidenceKind, type[EvidenceRecord]] = {
    "event": MatchEvent,
    "frame": TrackingFrame,
    "metric": MetricResult,
}


@dataclass(frozen=True)
class EvidenceEntry:
    evidence_id: str
    kind: EvidenceKind
    record: EvidenceRecord
    session_clock_ms: int


def evidence_id_of(record: EvidenceRecord) -> str:
    if isinstance(record, MatchEvent):
        return record.event_id
    if isinstance(record, TrackingFrame):
        return record.frame_id
    return record.metric_id


class EvidenceIndex:
    def __init__(self) -> None:
        self._entries: dict[str, EvidenceEntry] = {}

    def add(self, kind: EvidenceKind, record: EvidenceRecord, session_clock_ms: int) -> EvidenceEntry:
        if not isinstance(record, _RECORD_TYPES[kind]):
            raise TypeError(f"{kind} evidence must be {_RECORD_TYPES[kind].__name__}")
        entry = EvidenceEntry(evidence_id_of(record), kind, record, session_clock_ms)
        self._entries[entry.evidence_id] = entry
        return entry

    def resolve(self, evidence_id: str, as_of_ms: int) -> EvidenceEntry | None:
        """The entry, unless unknown or only available after `as_of_ms` (no future evidence)."""
        entry = self._entries.get(evidence_id)
        if entry is None or entry.session_clock_ms > as_of_ms:
            return None
        return entry

    def clear(self) -> None:
        self._entries.clear()

    def __contains__(self, evidence_id: object) -> bool:
        return evidence_id in self._entries
