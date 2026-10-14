"""Deterministic output checks run on every insight packet before release (constitution I, FR-007)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from tactistream.api.evidence import EvidenceEntry, EvidenceIndex
from tactistream.contracts import InsightPacket, MatchEvent, MatchMetadata, MetricResult

CheckCode = Literal[
    "unsupported_number", "unsupported_player", "unknown_evidence", "invalid_timing", "expired"
]

_EVIDENCE_TOKEN = re.compile(r"\b(?:evt-\d{4,}|frm-\d{6,}|metric-[a-z_]+-\d{4,}(?:-(?:blue|amber)-\d{2})?)\b")
_NUMBER = re.compile(r"(?:(?<![\w.])-)?(?<![\w.])\d+(?:\.\d+)?(?!\d)")


@dataclass(frozen=True)
class CheckFailure:
    code: CheckCode
    detail: str


def check_packet(
    packet: InsightPacket, evidence: EvidenceIndex, metadata: MatchMetadata, now_ms: int
) -> list[CheckFailure]:
    """Every number, player name and evidence ID in title/body must be backed by resolvable evidence."""
    failures: list[CheckFailure] = []
    render = packet.render
    if render.show_until_ms <= render.show_from_ms:
        failures.append(
            CheckFailure(
                "invalid_timing",
                f"show_until_ms {render.show_until_ms} <= show_from_ms {render.show_from_ms}",
            )
        )
    if now_ms > packet.expires_at_session_ms:
        failures.append(CheckFailure("expired", f"expired at {packet.expires_at_session_ms}, now {now_ms}"))

    resolved: list[EvidenceEntry] = []
    for evidence_id in packet.evidence_ids:
        entry = evidence.resolve(evidence_id, as_of_ms=now_ms)
        if entry is None:
            failures.append(
                CheckFailure("unknown_evidence", f"{evidence_id} is not available as of {now_ms}")
            )
        else:
            resolved.append(entry)

    text = f"{packet.title}\n{packet.body}"
    for token in _EVIDENCE_TOKEN.findall(text):
        if token not in packet.evidence_ids:
            failures.append(CheckFailure("unknown_evidence", f"{token} appears in text but is not cited"))
    text = _EVIDENCE_TOKEN.sub(" ", text)

    subjects = _subjects(resolved)
    for player_id, name in _player_names(metadata, packet.language):
        pattern = re.compile(re.escape(name) + r"(?!\d)")
        if pattern.search(text):
            if player_id not in subjects:
                failures.append(
                    CheckFailure(
                        "unsupported_player", f"{name} ({player_id}) is not a subject of the evidence"
                    )
                )
            text = pattern.sub(" ", text)

    allowed = _numbers(resolved)
    for number in _NUMBER.findall(text):
        if not _supported(number, allowed):
            failures.append(CheckFailure("unsupported_number", f"{number} does not match any evidence value"))
    return failures


def _player_names(metadata: MatchMetadata, language: str) -> list[tuple[str, str]]:
    names = [
        (player.player_id, player.display_name.en if language == "en" else player.display_name.hi)
        for team in metadata.teams
        for player in team.players
    ]
    return sorted(names, key=lambda item: -len(item[1]))


def _subjects(entries: Iterable[EvidenceEntry]) -> set[str]:
    subjects: set[str] = set()
    for entry in entries:
        record = entry.record
        if isinstance(record, MatchEvent):
            subjects.add(record.player_id)
            if record.recipient_id:
                subjects.add(record.recipient_id)
        elif isinstance(record, MetricResult):
            subjects.update(record.subject_ids or [])
    return subjects


def _numbers(entries: Iterable[EvidenceEntry]) -> list[float]:
    numbers: list[float] = []
    for entry in entries:
        record = entry.record
        if isinstance(record, MetricResult):
            if record.value is not None:
                numbers.append(record.value)
            numbers.extend((record.components or {}).values())
        elif isinstance(record, MatchEvent):
            numbers.extend(record.start_m)
            numbers.extend(record.end_m or ())
            if record.duration_ms is not None:
                numbers.append(record.duration_ms)
    return numbers


def _supported(number: str, allowed: Iterable[float]) -> bool:
    decimals = len(number.split(".", 1)[1]) if "." in number else 0
    return any(f"{value:.{decimals}f}" == number for value in allowed)
