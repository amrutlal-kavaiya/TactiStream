"""press_turnover: the focus team presses the opponent's build-up in the opponent's defensive third.

The opponent kicks off and plays back to the victim; two pressers close him down (`pressure` by presser 1,
then presser 2), his pass is `incomplete` and the interceptor, standing in the passing lane, makes an
`interception` 700 ms later, carries, passes to presser 1, who shoots -> `out_of_play` -> `period_end`.

At the lost pass the victim and both pressers sit on unjittered keyframes (presser 1 at 1.04 m, presser 2 at
1.22 m), so the pressure proxy there is >= 43 for every seed.

Coordinates are nominal (focus team attacks +x, the opponent defends x = 105); times are nominal ms.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from tactistream.simulator.config import KeyActorSet, VariantSpec
from tactistream.simulator.roster import opponent
from tactistream.simulator.scenarios.common import finish_outcome, shoot
from tactistream.simulator.script import Kickoff, Point, Restart, SegmentBuilder, SegmentResult

SCENARIO = "press_turnover"

KICKOFF_MS = 600
BACK_PASS = 2400
BACK_PASS_MS = 1200
PRESSURE_1 = 5600
PRESSURE_2 = 6100
LOST_PASS = 6600
LOST_PASS_MS = 700
INTERCEPTION = LOST_PASS + LOST_PASS_MS
COUNTER_CARRY = INTERCEPTION + 300
COUNTER_PASS = 9400
COUNTER_PASS_MS = 800
SHOT = 11400

VICTIM_AT_PASS: Point = (81.0, 42.0)


@dataclass(frozen=True)
class Actors:
    """Shirt numbers: focus team pressers and interceptor; opponent victim, feeder and kicker."""

    presser_1: int
    presser_2: int
    interceptor: int
    victim: int
    feeder: int = 6
    kicker: int = 9


ACTORS: Mapping[KeyActorSet, Actors] = {
    "primary": Actors(presser_1=9, presser_2=11, interceptor=10, victim=5),
    "alternate": Actors(presser_1=7, presser_2=9, interceptor=8, victim=4),
    "second_alternate": Actors(presser_1=11, presser_2=10, interceptor=6, victim=2),
}


def build(
    rng: np.random.Generator,
    spec: VariantSpec,
    *,
    start: Kickoff | Restart | None = None,
    t0_ms: int = 0,
    start_positions: Mapping[str, Point] | None = None,
) -> SegmentResult:
    b = SegmentBuilder(
        rng, spec, start or Kickoff(opponent(spec.focus_team)), t0_ms, start_positions=start_positions
    )
    script(b)
    return b.build()


def script(b: SegmentBuilder) -> None:
    a = ACTORS[b.spec.key_actor_set]
    outcome = finish_outcome(b)
    p1, p2, interceptor = b.fp(a.presser_1), b.fp(a.presser_2), b.fp(a.interceptor)
    victim, feeder, kicker = b.op(a.victim), b.op(a.feeder), b.op(a.kicker)
    end = SHOT + 1800
    vx, vy = VICTIM_AT_PASS

    b.keyframes(kicker, [(0, (52.8, 34.0)), (2500, (56.0, 30.0)), (end, (62.0, 28.0))])
    b.keyframes(feeder, [(0, (57.0, 37.5)), (BACK_PASS, (60.0, 39.0)), (end, (66.0, 38.0))])
    b.keyframes(victim, [(0, (72.0, 37.0)), (3600, (78.5, 40.0))])
    b.keyframes(victim, [(LOST_PASS, VICTIM_AT_PASS)], jitter=False)
    b.keyframes(victim, [(end, (82.0, 43.0))])
    b.keyframes(p1, [(0, (66.0, 38.0)), (4400, (76.5, 40.0))])
    b.keyframes(p1, [(LOST_PASS, (vx - 1.0, vy - 0.3))], jitter=False)
    b.keyframes(p1, [(COUNTER_PASS + COUNTER_PASS_MS, (94.0, 36.0)), (end, (97.0, 35.0))])
    b.keyframes(p2, [(0, (60.0, 46.0)), (4400, (75.5, 45.5))])
    b.keyframes(p2, [(LOST_PASS, (vx - 0.2, vy + 1.2))], jitter=False)
    b.keyframes(p2, [(end, (88.0, 45.0))])
    b.keyframes(
        interceptor,
        [
            (0, (60.0, 42.0)),
            (3600, (67.0, 41.5)),
            (LOST_PASS, (70.0, 41.0)),
            (COUNTER_PASS, (83.0, 39.0)),
            (end, (92.0, 37.0)),
        ],
    )

    b.beat(0, "kickoff", kicker, recipient=feeder, duration_ms=KICKOFF_MS)
    b.beat(KICKOFF_MS, "carry", feeder)
    b.beat(BACK_PASS, "pass", feeder, recipient=victim, duration_ms=BACK_PASS_MS, outcome="complete")
    b.beat(BACK_PASS + BACK_PASS_MS, "carry", victim)
    b.beat(PRESSURE_1, "pressure", p1)
    b.beat(PRESSURE_2, "pressure", p2)
    b.beat(LOST_PASS, "pass", victim, duration_ms=LOST_PASS_MS, outcome="incomplete", end_player=interceptor)
    turnover = b.beat(INTERCEPTION, "interception", interceptor, outcome="won")
    b.beat(COUNTER_CARRY, "carry", interceptor)
    b.beat(COUNTER_PASS, "pass", interceptor, recipient=p1, duration_ms=COUNTER_PASS_MS, outcome="complete")
    b.beat(COUNTER_PASS + COUNTER_PASS_MS, "carry", p1)
    finish = shoot(b, p1, SHOT, outcome)

    focus, opp = b.focus.capitalize(), b.opp.capitalize()
    b.label(
        scenario=SCENARIO,
        positive=True,
        expected_pattern="press_turnover",
        key_players={"presser_1": p1, "presser_2": p2, "victim": victim, "interceptor": interceptor},
        key_beats={"turnover": turnover, "shot": finish.shot},
        intended_explanation=(
            f"{focus} {a.presser_1} and {focus} {a.presser_2} press {opp} {a.victim}; "
            f"{focus} {a.interceptor} intercepts the forced pass, then shot."
        ),
    )
