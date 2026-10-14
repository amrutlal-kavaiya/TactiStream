"""Load recorded feeds (JSON Lines of `FeedEnvelope`) in replay order."""

from __future__ import annotations

import json
from pathlib import Path

from tactistream.contracts import ContractError, FeedEnvelope, validate

_KIND_ORDER = {"metadata": 0, "event": 1}


def fixtures_dir() -> Path:
    return Path(__file__).parents[4] / "data" / "fixtures"


def skeleton_fixture_path() -> Path:
    return fixtures_dir() / "skeleton.jsonl"


def envelope_time_ms(envelope: FeedEnvelope) -> int:
    """Session time at which a record is due; metadata (no clock) is due at 0."""
    return int(getattr(envelope.payload, "session_clock_ms", 0))


def _replay_key(envelope: FeedEnvelope) -> tuple[int, int, int]:
    is_metadata = envelope.kind == "metadata"
    return (0 if is_metadata else 1, envelope_time_ms(envelope), _KIND_ORDER.get(envelope.kind, 2))


def load_fixture(path: Path) -> list[FeedEnvelope]:
    """Schema-validate every line, then sort metadata first, then by session time, events before frames."""
    records: list[FeedEnvelope] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        obj = json.loads(line)
        try:
            validate("feed_envelope.schema.json", obj)
        except ContractError as exc:
            raise ValueError(f"{path.name}:{number}: {exc}") from exc
        records.append(FeedEnvelope.model_validate(obj))
    return sorted(records, key=_replay_key)
