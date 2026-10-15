"""switch_escape: the focus team circulates on its left flank (y >= 50) against an overload, then the switcher
plays a lofted pass (|dy| >= 34 m, ~2000 ms) to the far-side receiver, who is >= 7 m from the nearest opponent
at reception, carries and shoots -> `out_of_play` -> `period_end`.

Coordinates are nominal (focus team attacks +x, not mirrored); times are nominal ms.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from tactistream.simulator.config import KeyActorSet, VariantSpec
from tactistream.simulator.scenarios.common import finish_outcome, shoot
from tactistream.simulator.script import Kickoff, Point, Restart, SegmentBuilder, SegmentResult

SCENARIO = "switch_escape"

KICKOFF_MS = 600
PASS_1 = 2400
PASS_2 = 4800
PASS_3 = 7000
PASS_MS = 900
RETURN_MS = 800
SWITCH = 8800
SWITCH_MS = 2000
RECEPTION = SWITCH + SWITCH_MS
SHOT = RECEPTION + 3000


@dataclass(frozen=True)
class Actors:
    """Shirt numbers: focus team `switcher`, `receiver`, flank helpers `h1`, `h2`; opponent `closer`."""

    switcher: int
    receiver: int
    closer: int
    h1: int = 3
    h2: int = 11
    kicker: int = 9


ACTORS: Mapping[KeyActorSet, Actors] = {
    "primary": Actors(switcher=8, receiver=7, closer=3),
    "alternate": Actors(switcher=10, receiver=2, closer=2),
    "second_alternate": Actors(switcher=6, receiver=11, closer=5, h2=10),
}


def build(
    rng: np.random.Generator,
    spec: VariantSpec,
    *,
    start: Kickoff | Restart | None = None,
    t0_ms: int = 0,
    start_positions: Mapping[str, Point] | None = None,
) -> SegmentResult:
    b = SegmentBuilder(rng, spec, start or Kickoff(spec.focus_team), t0_ms, start_positions=start_positions)
    script(b)
    return b.build()


def circulation(b: SegmentBuilder, a: Actors, end: int) -> None:
    """Kickoff to the switcher, two passes along the left flank and back to the switcher, who carries."""
    switcher, h1, h2, kicker = b.fp(a.switcher), b.fp(a.h1), b.fp(a.h2), b.fp(a.kicker)
    b.keyframes(kicker, [(0, (52.2, 34.0)), (3000, (58.0, 38.0)), (8000, (70.0, 36.0)), (end, (84.0, 34.0))])
    b.keyframes(
        switcher,
        [
            (0, (48.6, 35.5)),
            (PASS_1, (50.5, 39.5)),
            (PASS_2, (55.0, 48.0)),
            (PASS_3 + RETURN_MS, (60.0, 52.0)),
            (RECEPTION, (66.0, 48.0)),
            (end, (70.0, 45.0)),
        ],
    )
    b.keyframes(
        h1, [(0, (40.0, 52.0)), (PASS_1 + PASS_MS, (50.0, 56.0)), (6000, (53.0, 57.0)), (end, (58.0, 56.0))]
    )
    b.keyframes(
        h2, [(0, (50.0, 58.0)), (PASS_2 + PASS_MS, (62.0, 60.0)), (8000, (65.0, 59.0)), (end, (75.0, 55.0))]
    )
    b.targets(b.op(2), [(0, (70.0, 52.0)), (SWITCH, (63.0, 55.0)), (end, (72.0, 50.0))])
    b.targets(b.op(8), [(0, (63.0, 46.0)), (SWITCH, (65.0, 50.0)), (end, (72.0, 44.0))])
    b.targets(b.op(7), [(0, (55.0, 58.0)), (SWITCH, (59.0, 56.0)), (end, (64.0, 52.0))])

    b.beat(0, "kickoff", kicker, recipient=switcher, duration_ms=KICKOFF_MS)
    b.beat(KICKOFF_MS, "carry", switcher)
    b.beat(PASS_1, "pass", switcher, recipient=h1, duration_ms=PASS_MS, outcome="complete")
    b.beat(PASS_1 + PASS_MS, "carry", h1)
    b.beat(PASS_2, "pass", h1, recipient=h2, duration_ms=PASS_MS, outcome="complete")
    b.beat(PASS_2 + PASS_MS, "carry", h2)
    b.beat(PASS_3, "pass", h2, recipient=switcher, duration_ms=RETURN_MS, outcome="complete")
    b.beat(PASS_3 + RETURN_MS, "carry", switcher)


def script(b: SegmentBuilder) -> None:
    a = ACTORS[b.spec.key_actor_set]
    outcome = finish_outcome(b)
    switcher, receiver, closer = b.fp(a.switcher), b.fp(a.receiver), b.op(a.closer)
    end = SHOT + 1800
    circulation(b, a, end)
    b.keyframes(
        receiver,
        [
            (0, (52.0, 12.0)),
            (SWITCH, (70.0, 13.0)),
            (RECEPTION, (74.0, 15.0)),
            (SHOT, (88.0, 24.0)),
            (end, (90.0, 25.0)),
        ],
    )
    b.keyframes(
        closer, [(0, (80.0, 14.0)), (SWITCH, (79.0, 21.0)), (RECEPTION, (80.5, 22.0)), (end, (90.0, 28.0))]
    )

    switch = b.beat(SWITCH, "pass", switcher, recipient=receiver, duration_ms=SWITCH_MS, outcome="complete")
    b.beat(RECEPTION, "carry", receiver)
    finish = shoot(b, receiver, SHOT, outcome)

    focus, opp = b.focus.capitalize(), b.opp.capitalize()
    b.label(
        scenario=SCENARIO,
        positive=True,
        expected_pattern="switch_escape",
        key_players={"switcher": switcher, "receiver": receiver, "closer": closer},
        key_beats={"switch": switch, "shot": finish.shot},
        intended_explanation=(
            f"{focus} {a.switcher} switches play from the crowded left flank to {focus} {a.receiver}, "
            f"who has space away from {opp} {a.closer}; carry, then shot."
        ),
    )
