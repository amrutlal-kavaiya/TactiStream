"""Ground-truth generation manifest: written to manifest.json only, never published or read by live code."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Literal

from tactistream.contracts import MomentPattern
from tactistream.simulator.config import SimulationConfig, Variant


@dataclass(frozen=True)
class SegmentLabel:
    index: int
    scenario: str
    variant: Variant
    start_ms: int
    end_ms: int
    positive: bool
    expected_pattern: MomentPattern | None
    negative_of: MomentPattern | None
    key_players: Mapping[str, str] = field(default_factory=dict)
    key_event_ids: Mapping[str, str] = field(default_factory=dict)
    intended_explanation: str = ""


@dataclass(frozen=True)
class TrackingGap:
    player_ids: tuple[str, ...]
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class GenerationManifest:
    manifest_version: Literal["1"]
    match_id: str
    config: SimulationConfig
    segments: tuple[SegmentLabel, ...]
    tracking_gaps: tuple[TrackingGap, ...]
    feed_sha256: str
    event_count: int
    frame_count: int
    duration_ms: int

    def to_canonical_json(self) -> str:
        data = asdict(self)
        data["segments"] = [
            {**s, "key_players": dict(s["key_players"]), "key_event_ids": dict(s["key_event_ids"])}
            for s in data["segments"]
        ]
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
