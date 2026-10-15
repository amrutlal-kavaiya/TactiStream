"""space_creation: build-up, a diagonal off-ball run drags the follower out of the passer -> receiver lane,
then a forward pass into the widened lane, a carry and a shot.

Coordinates are nominal (focus team attacks +x, no mirror); times are nominal ms from the segment start. With
<= 2 build-up passes the forward pass stays at 8800 ms (data-model hero table); each extra pass adds 1800 ms.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from tactistream.contracts import Outcome
from tactistream.simulator.config import KeyActorSet, VariantSpec
from tactistream.simulator.script import Kickoff, Point, Restart, SegmentBuilder, SegmentResult

SCENARIO = "space_creation"
SHOT_OUTCOMES: tuple[Outcome, ...] = ("on_target", "off_target", "blocked")
SHOT_PROBABILITIES = (0.4, 0.4, 0.2)

KICKOFF_MS = 600
FIRST_PASS_MS = 2600
PASS_SPACING_MS = 1800
PASS_MS = 800
RUN_DELAY_MS = 600
RUN_TO_PASS_MS = 3000
FORWARD_PASS_MS = 900
SHOT_AFTER_PASS_MS = 3500
SHOT_MS = 800
BLOCK_MS = 400
PERIOD_END_AFTER_MS = 1000


@dataclass(frozen=True)
class Actors:
    """Shirt numbers: focus team except `follower`, `blocker` (opponent)."""

    passer: int
    receiver: int
    runner: int
    follower: int
    kicker: int
    partner_a: int
    partner_b: int
    blocker: int


ACTORS: Mapping[KeyActorSet, Actors] = {
    "primary": Actors(
        passer=8, receiver=11, runner=9, follower=4, kicker=10, partner_a=6, partner_b=4, blocker=5
    ),
    "alternate": Actors(
        passer=10, receiver=9, runner=7, follower=3, kicker=8, partner_a=6, partner_b=4, blocker=5
    ),
    "second_alternate": Actors(
        passer=6, receiver=7, runner=10, follower=5, kicker=9, partner_a=8, partner_b=4, blocker=4
    ),
}

# Ball-holder chains by build-up pass count: P = passer, M = partner a, N = partner b.
CHAINS: Mapping[int, str] = {0: "P", 1: "MP", 2: "PMP", 3: "PMNP", 4: "PMPNP"}

KICKOFF_START = (48.6, 31.8)
STATIONS: Mapping[str, Point] = {"M": (50.0, 24.0), "N": (46.0, 37.0), "P": (57.0, 31.5)}


@dataclass(frozen=True)
class Timeline:
    passes: tuple[int, ...]
    last_arrival: int
    run_start: int
    forward_pass: int
    reception: int
    shot: int
    out_of_play: int
    period_end: int

    @classmethod
    def for_passes(cls, n: int) -> Timeline:
        last = FIRST_PASS_MS + PASS_SPACING_MS * (max(n, 2) - 1)
        passes = tuple(last - PASS_SPACING_MS * (n - k) for k in range(1, n + 1))
        arrival = last + PASS_MS
        run_start = arrival + RUN_DELAY_MS
        forward = run_start + RUN_TO_PASS_MS
        shot = forward + SHOT_AFTER_PASS_MS
        return cls(
            passes,
            arrival,
            run_start,
            forward,
            forward + FORWARD_PASS_MS,
            shot,
            shot + SHOT_MS,
            shot + SHOT_MS + PERIOD_END_AFTER_MS,
        )


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


def script(b: SegmentBuilder) -> None:
    a = ACTORS[b.spec.key_actor_set]
    n = b.spec.build_up_passes
    tl = Timeline.for_passes(n)
    chain = CHAINS[n]
    outcome = SHOT_OUTCOMES[int(b.rng.choice(len(SHOT_OUTCOMES), p=SHOT_PROBABILITIES))]
    ids = {"P": b.fp(a.passer), "M": b.fp(a.partner_a), "N": b.fp(a.partner_b)}
    passer, receiver, runner = ids["P"], b.fp(a.receiver), b.fp(a.runner)
    follower, blocker, keeper, kicker = b.op(a.follower), b.op(a.blocker), b.op(1), b.fp(a.kicker)
    fp, rec, sh, end = tl.forward_pass, tl.reception, tl.shot, tl.period_end

    _holders(b, chain, ids, tl)
    b.keyframes(kicker, [(0, (52.2, 34.0)), (2500, (51.0, 38.5)), (5000, (49.5, 42.0)), (end, (50.5, 43.0))])
    b.keyframes(
        runner,
        [
            (0, (51.0, 30.0)),
            (tl.run_start - 2000, (63.3, 28.5)),
            (tl.run_start, (66.0, 31.5)),
            (tl.run_start + 2800, (75.5, 42.0)),
            (fp + 1800, (78.5, 45.0)),
            (end, (79.5, 46.0)),
        ],
    )
    b.keyframes(
        follower,
        [
            (0, (71.0, 31.0)),
            (fp - 4000, (67.5, 30.0)),
            (fp, (73.5, 37.5)),
            (fp + 1800, (75.5, 40.0)),
            (end, (76.0, 40.5)),
        ],
    )
    b.keyframes(
        receiver,
        [
            (0, (53.5, 22.5)),
            (fp - 4000, (69.0, 26.4)),
            (fp - 1000, (69.6, 26.8)),
            (sh, (86.0, 30.0)),
            (end, (89.0, 30.6)),
        ],
    )
    blocked = outcome == "blocked"
    b.keyframes(
        blocker,
        [
            (0, (77.0, 38.0)),
            (fp, (86.0, 33.5)),
            (sh + BLOCK_MS, (97.5, 31.5) if blocked else (93.0, 26.0)),
        ],
    )
    b.keyframes(
        keeper,
        [
            (0, (99.0, 34.0)),
            (fp, (99.5, 33.5)),
            (tl.out_of_play, (103.8, 35.2) if outcome == "on_target" else (101.0, 33.0)),
        ],
    )
    b.targets(b.op(6), [(0, (64.0, 40.0)), (end, (70.0, 40.0))])
    b.targets(b.op(9), [(0, (52.0, 38.0)), (end, (55.0, 38.0))])

    b.beat(0, "kickoff", kicker, recipient=ids[chain[0]], duration_ms=KICKOFF_MS)
    b.beat(KICKOFF_MS, "carry", ids[chain[0]])
    for k, t in enumerate(tl.passes):
        b.beat(t, "pass", ids[chain[k]], recipient=ids[chain[k + 1]], duration_ms=PASS_MS, outcome="complete")
    pass_beat = b.beat(
        fp, "pass", passer, recipient=receiver, duration_ms=FORWARD_PASS_MS, outcome="complete"
    )
    b.beat(rec, "carry", receiver)
    if outcome == "blocked":
        shot_beat = b.beat(sh, "shot", receiver, duration_ms=BLOCK_MS, outcome=outcome, end_player=blocker)
        last = blocker
        b.beat(tl.out_of_play, "out_of_play", last, ball_to=(105.3, 27.5))
    elif outcome == "on_target":
        shot_beat = b.beat(sh, "shot", receiver, duration_ms=SHOT_MS, outcome=outcome, end=(104.6, 35.5))
        last = keeper
        b.beat(tl.out_of_play, "out_of_play", last, ball_to=(105.8, 38.5))
    else:
        shot_beat = b.beat(sh, "shot", receiver, duration_ms=SHOT_MS, outcome=outcome, end=(105.0, 39.8))
        last = receiver
        b.beat(tl.out_of_play, "out_of_play", last)
    b.beat(end, "period_end", last)

    focus, opp = b.focus.capitalize(), b.opp.capitalize()
    b.label(
        scenario=SCENARIO,
        positive=True,
        expected_pattern="space_creation",
        key_players={"runner": runner, "follower": follower, "passer": passer, "receiver": receiver},
        key_beats={"forward_pass": pass_beat, "shot": shot_beat},
        intended_explanation=(
            f"{focus} {a.runner}'s diagonal run draws {opp} {a.follower}; the {focus} {a.passer} → {focus} "
            f"{a.receiver} lane widens; forward pass, then shot."
        ),
    )


def _holders(b: SegmentBuilder, chain: str, ids: Mapping[str, str], tl: Timeline) -> None:
    """Keyframes for P, M, N: receive at their station, hold near it, P ends ready for the forward pass."""
    fp, end = tl.forward_pass, tl.period_end
    first = chain[0]
    starts: dict[str, list[tuple[int, Point]]] = {
        "P": [(0, (51.0, 37.0))],
        "M": [(0, (46.0, 27.0))],
        "N": [(0, (40.0, 35.0))],
    }
    starts[first] = [(0, KICKOFF_START)]
    keys = starts
    if first == "P":
        keys["P"].append((FIRST_PASS_MS, (54.5, 32.4)))
    elif first == "M":
        keys["M"].append((tl.passes[0], (49.5, 25.5)))
        keys["P"].append((FIRST_PASS_MS, (55.0, 34.0)))
    for k, t in enumerate(tl.passes):
        holder = chain[k + 1]
        arrival = t + PASS_MS
        if holder == "P" and keys["P"][-1][0] >= arrival - 1500:
            keys["P"].pop()
        keys[holder].append((arrival, STATIONS[holder]))
    keys["P"].append((fp, (58.0, 32.0)))
    keys["P"].append((end, (60.0, 32.5)))
    if "M" in chain:
        keys["M"].append((end, (51.5, 26.0)))
    else:
        keys["M"].append((end, (49.0, 27.0)))
    keys["N"].append((end, (47.5, 36.0)))
    for role in ("P", "M", "N"):
        b.keyframes(ids[role], _thin(keys[role]))


def _thin(keys: list[tuple[int, Point]]) -> list[tuple[int, Point]]:
    """Drop keys closer than 1500 ms to the previous kept key (jittered short spans break the accel bound)."""
    out: list[tuple[int, Point]] = []
    for t, p in sorted(keys, key=lambda k: k[0]):
        if out and t - out[-1][0] < 1500:
            continue
        out.append((t, p))
    return out
