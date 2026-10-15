"""Pieces shared by the B2 families: a keeper, a shot on the attacked goal and the dead-ball ending.

Coordinates are nominal (focus team attacks +x, goal at x = 105).
"""

from __future__ import annotations

from dataclasses import dataclass

from tactistream.contracts import Outcome
from tactistream.simulator.script import SegmentBuilder

FINISH_OUTCOMES: tuple[Outcome, ...] = ("on_target", "off_target")
SHOT_MS = 800
PERIOD_END_AFTER_MS = 1000
ON_TARGET_END = (104.6, 35.5)
OFF_TARGET_END = (105.0, 39.8)
PARRY_OUT = (105.8, 38.5)


@dataclass(frozen=True)
class Finish:
    shot: int
    """Beat index of the shot."""
    out_of_play_ms: int
    period_end_ms: int


def finish_outcome(b: SegmentBuilder) -> Outcome:
    return FINISH_OUTCOMES[int(b.rng.integers(len(FINISH_OUTCOMES)))]


def keeper(b: SegmentBuilder, t_shot: int, outcome: Outcome) -> str:
    """Opponent keeper keyframes; on target he parries the shot behind for a corner."""
    gk = b.op(1)
    b.keyframes(
        gk,
        [
            (0, (99.0, 34.0)),
            (t_shot - 2000, (99.5, 34.0)),
            (t_shot + SHOT_MS, (103.8, 35.2) if outcome == "on_target" else (101.0, 33.0)),
        ],
    )
    return gk


def shoot(b: SegmentBuilder, shooter: str, t_shot: int, outcome: Outcome) -> Finish:
    """Shot at `t_shot`, then `out_of_play` by the last touch and `period_end`."""
    gk = keeper(b, t_shot, outcome)
    out_ms = t_shot + SHOT_MS
    end_ms = out_ms + PERIOD_END_AFTER_MS
    if outcome == "on_target":
        beat = b.beat(t_shot, "shot", shooter, duration_ms=SHOT_MS, outcome=outcome, end=ON_TARGET_END)
        last = gk
        b.beat(out_ms, "out_of_play", last, ball_to=PARRY_OUT)
    else:
        beat = b.beat(t_shot, "shot", shooter, duration_ms=SHOT_MS, outcome=outcome, end=OFF_TARGET_END)
        last = shooter
        b.beat(out_ms, "out_of_play", last)
    b.beat(end_ms, "period_end", last)
    return Finish(beat, out_ms, end_ms)
