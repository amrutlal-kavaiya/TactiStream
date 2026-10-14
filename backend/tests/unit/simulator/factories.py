"""A hand-built, fully valid 2 s simulator output for validator tests.

Blue 10 kicks off to Blue 8, who jogs at 2 m/s along +x with the ball 0.3 m ahead, carries, then passes to a
still Blue 6. Everyone else stands at the kickoff slots. 21 frames (0..2000 ms), three events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tactistream.contracts import MatchEvent, MatchMetadata, TrackingFrame
from tactistream.simulator.config import SimulationConfig
from tactistream.simulator.roster import PERIOD_1, PLAYER_IDS, build_metadata, slots

SOURCE = {"kind": "synthetic", "generator_version": "0.1.0", "seed": 42}
MATCH_ID = "demo-blue-amber-001"
Point = tuple[float, float]


@dataclass
class Records:
    metadata: MatchMetadata
    events: list[MatchEvent]
    frames: list[TrackingFrame]
    positions: dict[str, list[Point | None]] = field(default_factory=dict)
    ball: list[Point | None] = field(default_factory=list)


def blue_08(t_ms: int) -> Point:
    return (47.0 + 2.0 * t_ms / 1000.0, 32.0)


def _event(sequence: int, t_ms: int, event_type: str, player: str, **fields: Any) -> MatchEvent:
    return MatchEvent.model_validate(
        {
            "schema_version": "1.0",
            "match_id": MATCH_ID,
            "event_id": f"evt-{sequence:04d}",
            "sequence": sequence,
            "period": 1,
            "period_clock_ms": 840000 + t_ms,
            "session_clock_ms": t_ms,
            "event_type": event_type,
            "team_id": player.split("-")[0],
            "player_id": player,
            "outcome": None,
            "source": SOURCE,
            **fields,
        }
    )


def frames_from(positions: dict[str, list[Point | None]], ball: list[Point | None]) -> list[TrackingFrame]:
    frames = []
    for k, ball_pos in enumerate(ball):
        players = []
        for pid in PLAYER_IDS:
            pos = positions[pid][k]
            players.append(
                {"player_id": pid, "visible": False}
                if pos is None
                else {"player_id": pid, "visible": True, "pos_m": (round(pos[0], 2), round(pos[1], 2))}
            )
        frames.append(
            TrackingFrame.model_validate(
                {
                    "schema_version": "1.0",
                    "match_id": MATCH_ID,
                    "frame_id": f"frm-{k:06d}",
                    "frame_index": k,
                    "period": 1,
                    "period_clock_ms": 840000 + k * 100,
                    "session_clock_ms": k * 100,
                    "players": players,
                    "ball": {"visible": False}
                    if ball_pos is None
                    else {
                        "visible": True,
                        "pos_m": (round(ball_pos[0], 2), round(ball_pos[1], 2)),
                        "height_m": 0.0,
                    },
                    "source": SOURCE,
                }
            )
        )
    return frames


def make_output(*, pass_speed_mps: float = 12.5) -> Records:
    times = range(0, 2001, 100)
    standing = {**slots("blue", "kickoff", 1), **slots("amber", "kickoff", -1)}
    standing["blue-10"] = (52.2, 34.0)
    pass_start = (blue_08(1200)[0] + 0.3, 32.0)
    standing["blue-06"] = (pass_start[0] - 0.3, 32.0 - 0.8 * pass_speed_mps)
    pass_end = (standing["blue-06"][0] + 0.3, standing["blue-06"][1])
    positions: dict[str, list[Point | None]] = {pid: [standing[pid] for _ in times] for pid in PLAYER_IDS}
    positions["blue-08"] = [blue_08(t) for t in times]
    kick_end = (blue_08(600)[0] + 0.3, 32.0)
    ball: list[Point | None] = []
    for t in times:
        if t <= 600:
            u = t / 600
            ball.append((52.5 + (kick_end[0] - 52.5) * u, 34.0 + (kick_end[1] - 34.0) * u))
        elif t <= 1200:
            ball.append((blue_08(t)[0] + 0.3, 32.0))
        else:
            u = (t - 1200) / 800
            ball.append(
                (
                    pass_start[0] + (pass_end[0] - pass_start[0]) * u,
                    pass_start[1] + (pass_end[1] - pass_start[1]) * u,
                )
            )
    events = [
        _event(
            1,
            0,
            "kickoff",
            "blue-10",
            recipient_id="blue-08",
            start_m=(52.5, 34.0),
            end_m=kick_end,
            duration_ms=600,
        ),
        _event(2, 600, "carry", "blue-08", start_m=kick_end, end_m=pass_start, duration_ms=600),
        _event(
            3,
            1200,
            "pass",
            "blue-08",
            recipient_id="blue-06",
            start_m=pass_start,
            end_m=(round(pass_end[0], 2), round(pass_end[1], 2)),
            duration_ms=800,
            outcome="complete",
        ),
    ]
    metadata = build_metadata(SimulationConfig(42, "space_creation"), periods=[PERIOD_1])
    return Records(metadata, events, frames_from(positions, ball), positions, ball)


def rebuild_frames(records: Records) -> Records:
    records.frames = frames_from(records.positions, records.ball)
    return records


def make_simulation_output(**options: Any) -> Any:
    """The factory records wrapped as a `SimulationOutput` with a one-segment manifest."""
    from tactistream.simulator.engine import SimulationOutput
    from tactistream.simulator.manifest import GenerationManifest, SegmentLabel

    r = make_output(**options)
    config = SimulationConfig(42, "space_creation")
    label = SegmentLabel(
        index=0,
        scenario="space_creation",
        variant="A",
        start_ms=0,
        end_ms=2000,
        positive=True,
        expected_pattern="space_creation",
        negative_of=None,
        key_players={"passer": "blue-08"},
        key_event_ids={"forward_pass": "evt-0003"},
        intended_explanation="factory",
    )
    manifest = GenerationManifest(
        manifest_version="1",
        match_id=MATCH_ID,
        config=config,
        segments=(label,),
        tracking_gaps=(),
        feed_sha256="0" * 64,
        event_count=len(r.events),
        frame_count=len(r.frames),
        duration_ms=2000,
    )
    return SimulationOutput(config, r.metadata, tuple(r.events), tuple(r.frames), manifest)
