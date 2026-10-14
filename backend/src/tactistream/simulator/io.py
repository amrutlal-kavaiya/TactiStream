"""Canonical feed/manifest files: envelopes in replay order, canonical JSON lines, atomic writes."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tactistream.contracts import FeedEnvelope, MatchEvent, MatchMetadata, TrackingFrame

if TYPE_CHECKING:
    from tactistream.simulator.engine import SimulationOutput

BASE_PUBLISHED_EPOCH_MS = 1_792_000_000_000
FEED_FILE = "feed.jsonl"
MANIFEST_FILE = "manifest.json"


@dataclass(frozen=True)
class WrittenFiles:
    feed_path: Path
    manifest_path: Path
    feed_sha256: str


def canonical_line(obj: Mapping[str, object]) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def envelopes_for(
    metadata: MatchMetadata, events: Sequence[MatchEvent], frames: Sequence[TrackingFrame]
) -> list[FeedEnvelope]:
    """Metadata first, then by session time with events before frames at equal time."""
    match_id = metadata.match_id
    timed: list[tuple[int, int, FeedEnvelope]] = []
    for event in events:
        envelope = FeedEnvelope(
            schema_version="1.0",
            kind="event",
            match_id=match_id,
            record_id=event.event_id,
            published_ms=BASE_PUBLISHED_EPOCH_MS + event.session_clock_ms,
            payload=event,
        )
        timed.append((event.session_clock_ms, 0, envelope))
    for frame in frames:
        envelope = FeedEnvelope(
            schema_version="1.0",
            kind="frame",
            match_id=match_id,
            record_id=frame.frame_id,
            published_ms=BASE_PUBLISHED_EPOCH_MS + frame.session_clock_ms,
            payload=frame,
        )
        timed.append((frame.session_clock_ms, 1, envelope))
    timed.sort(key=lambda item: (item[0], item[1]))
    head = FeedEnvelope(
        schema_version="1.0",
        kind="metadata",
        match_id=match_id,
        record_id=match_id,
        published_ms=BASE_PUBLISHED_EPOCH_MS,
        payload=metadata,
    )
    return [head, *(envelope for _, _, envelope in timed)]


def to_envelopes(output: SimulationOutput) -> list[FeedEnvelope]:
    return envelopes_for(output.metadata, output.events, output.frames)


def feed_bytes(envelopes: Sequence[FeedEnvelope]) -> bytes:
    return b"".join(canonical_line(e.model_dump(mode="json", exclude_none=True)) for e in envelopes)


def write_output(output: SimulationOutput, out_dir: Path, *, force: bool = False) -> WrittenFiles:
    """Write `feed.jsonl` and `manifest.json` via a sibling temp dir; nothing lands in `out_dir` on error."""
    if out_dir.exists() and any(out_dir.iterdir()) and not force:
        raise FileExistsError(f"{out_dir} is not empty (use --force to overwrite)")
    feed = feed_bytes(to_envelopes(output))
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=out_dir.parent))
    try:
        (tmp / FEED_FILE).write_bytes(feed)
        (tmp / MANIFEST_FILE).write_text(output.manifest.to_canonical_json() + "\n", encoding="utf-8")
        if out_dir.exists():
            for name in (MANIFEST_FILE, FEED_FILE):
                os.replace(tmp / name, out_dir / name)
        else:
            os.replace(tmp, out_dir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return WrittenFiles(out_dir / FEED_FILE, out_dir / MANIFEST_FILE, hashlib.sha256(feed).hexdigest())
