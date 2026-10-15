"""simulate(config) -> SimulationOutput: family dispatch, contract records and manifest. No I/O."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from tactistream.contracts import MatchEvent, MatchMetadata, TrackingFrame
from tactistream.simulator.config import ConfigError, SimulationConfig
from tactistream.simulator.io import envelopes_for, feed_bytes
from tactistream.simulator.kinematics import FRAME_MS
from tactistream.simulator.manifest import GenerationManifest, SegmentLabel, TrackingGap
from tactistream.simulator.roster import PERIOD_1, PERIOD_2, PLAYER_IDS, build_metadata
from tactistream.simulator.script import SegmentResult

PERIOD_CLOCK_OFFSET_MS = 840_000
SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class SimulationOutput:
    config: SimulationConfig
    metadata: MatchMetadata
    events: tuple[MatchEvent, ...]
    frames: tuple[TrackingFrame, ...]
    manifest: GenerationManifest


def segment_rng(seed: int, index: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, index])))


def simulate(config: SimulationConfig) -> SimulationOutput:
    from tactistream.simulator.scenarios import FAMILIES

    family = FAMILIES.get(config.scenario)
    if family is None:
        raise ConfigError("invalid_scenario", f"scenario '{config.scenario}' is not implemented yet")
    result = family(segment_rng(config.seed, 0), config.spec)
    return assemble(config, [(config.scenario, config.variant, result)])


def _r(v: float) -> float:
    return round(float(v), 2) + 0.0


def _pt(p: Sequence[float]) -> tuple[float, float]:
    return (_r(p[0]), _r(p[1]))


def assemble(
    config: SimulationConfig, segments: Sequence[tuple[str, str, SegmentResult]]
) -> SimulationOutput:
    """Turn consecutive segment results into contract records and the ground-truth manifest."""
    match_id = config.match_id
    source = {"kind": "synthetic", "generator_version": config.generator_version, "seed": config.seed}
    periods = [PERIOD_1] if config.spec.period == 1 else [PERIOD_1, PERIOD_2]
    metadata = build_metadata(config, periods)

    events: list[MatchEvent] = []
    frames: list[TrackingFrame] = []
    labels: list[SegmentLabel] = []
    gaps: list[TrackingGap] = []
    for index, (scenario, variant, seg) in enumerate(segments):
        first_event = len(events)
        for draft in seg.events:
            seq = len(events) + 1
            record: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "match_id": match_id,
                "event_id": f"evt-{seq:04d}",
                "sequence": seq,
                "period": seg.period,
                "period_clock_ms": PERIOD_CLOCK_OFFSET_MS + draft.t_ms,
                "session_clock_ms": draft.t_ms,
                "event_type": draft.event_type,
                "team_id": draft.team_id,
                "player_id": draft.player_id,
                "start_m": _pt(draft.start_m),
                "outcome": draft.outcome,
                "source": source,
            }
            if draft.recipient_id is not None:
                record["recipient_id"] = draft.recipient_id
            if draft.end_m is not None:
                record["end_m"] = _pt(draft.end_m)
            if draft.duration_ms is not None:
                record["duration_ms"] = draft.duration_ms
            events.append(MatchEvent.model_validate(record))
        skip_first = bool(frames) and frames[-1].session_clock_ms == seg.t0_ms
        for k in range(1 if skip_first else 0, len(seg.ball)):
            t = seg.t0_ms + k * FRAME_MS
            frame_index = len(frames)
            players = []
            for pid in PLAYER_IDS:
                if seg.visible[pid][k]:
                    players.append({"player_id": pid, "visible": True, "pos_m": _pt(seg.tracks[pid][k])})
                else:
                    players.append({"player_id": pid, "visible": False})
            bx, by, bh = seg.ball[k]
            ball: dict[str, Any] = (
                {"visible": False}
                if math.isnan(bx)
                else {"visible": True, "pos_m": _pt((bx, by)), "height_m": _r(max(0.0, bh))}
            )
            frames.append(
                TrackingFrame.model_validate(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "match_id": match_id,
                        "frame_id": f"frm-{frame_index:06d}",
                        "frame_index": frame_index,
                        "period": seg.period,
                        "period_clock_ms": PERIOD_CLOCK_OFFSET_MS + t,
                        "session_clock_ms": t,
                        "players": players,
                        "ball": ball,
                        "source": source,
                    }
                )
            )
        gaps.extend(seg.gaps)
        if seg.label is not None:
            lab = seg.label
            labels.append(
                SegmentLabel(
                    index=index,
                    scenario=scenario,
                    variant=variant,  # type: ignore[arg-type]
                    start_ms=seg.t0_ms,
                    end_ms=seg.end_ms,
                    positive=lab.positive,
                    expected_pattern=lab.expected_pattern,  # type: ignore[arg-type]
                    negative_of=lab.negative_of,  # type: ignore[arg-type]
                    key_players=dict(lab.key_players),
                    key_event_ids={
                        name: events[first_event + beat].event_id for name, beat in lab.key_beats.items()
                    },
                    intended_explanation=lab.intended_explanation,
                )
            )

    feed = feed_bytes(envelopes_for(metadata, events, frames))
    manifest = GenerationManifest(
        manifest_version="1",
        match_id=match_id,
        config=config,
        segments=tuple(labels),
        tracking_gaps=tuple(gaps),
        feed_sha256=hashlib.sha256(feed).hexdigest(),
        event_count=len(events),
        frame_count=len(frames),
        duration_ms=frames[-1].session_clock_ms if frames else 0,
    )
    return SimulationOutput(config, metadata, tuple(events), tuple(frames), manifest)
