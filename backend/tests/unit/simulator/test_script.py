import itertools

import numpy as np
import pytest

from tactistream.simulator.config import VARIANTS
from tactistream.simulator.possession import IllegalTransition, Phase
from tactistream.simulator.script import Kickoff, SceneTransform, SegmentBuilder

CARRY_TIMES = [600, 1000, 1500, 2300, 2700, 3600, 4000, 4500]


def builder(seed: int = 7, variant: str = "A", *, jitter: bool = True) -> SegmentBuilder:
    spec = VARIANTS[variant]  # type: ignore[index]
    return SegmentBuilder(np.random.default_rng(seed), spec, Kickoff(spec.focus_team), jitter=jitter)


def scripted(b: SegmentBuilder) -> SegmentBuilder:
    """Blue 10 kicks off to Blue 8, who jogs forward with a series of carries, then the ball goes out."""
    b.keyframes(b.fp(10), [(0, (52.2, 34.0)), (3000, (54.0, 37.0)), (6000, (55.0, 39.0))], jitter=False)
    b.keyframes(b.fp(8), [(0, (48.0, 32.0)), (2500, (52.0, 32.5)), (5000, (58.0, 31.0))])
    b.beat(0, "kickoff", b.fp(10), recipient=b.fp(8), duration_ms=600)
    for t in CARRY_TIMES:
        b.beat(t, "carry", b.fp(8))
    b.beat(5000, "out_of_play", b.fp(8))
    b.beat(6000, "period_end", b.fp(8))
    return b


def test_illegal_beat_raises_immediately() -> None:
    b = builder()
    with pytest.raises(IllegalTransition):
        b.beat(0, "carry", b.fp(8))


def test_scene_transform() -> None:
    assert SceneTransform(rotate=True, mirror_y=False).point((60.0, 40.0)) == (45.0, 28.0)
    assert SceneTransform(rotate=True, mirror_y=True).point((60.0, 40.0)) == (45.0, 40.0)
    assert SceneTransform(rotate=False, mirror_y=False).point((60.0, 40.0)) == (60.0, 40.0)
    assert builder(variant="E").transform.point((60.0, 40.0)) == (45.0, 28.0)
    assert builder(variant="D").transform.point((60.0, 40.0)) == (45.0, 40.0)
    assert builder(variant="B").transform.point((60.0, 40.0)) == (60.0, 28.0)


def test_jitter_is_bounded_ordered_and_quantized() -> None:
    nominal = [0, *CARRY_TIMES, 5000, 6000]
    moved = 0
    for seed in range(20):
        b = scripted(builder(seed))
        result = b.build()
        times = [e.t_ms for e in result.events]
        assert all(t % 100 == 0 for t in times)
        assert times[0] == 0
        assert all(abs(t - n) <= 200 for t, n in zip(times, nominal, strict=True))
        assert all(later - earlier >= 300 for earlier, later in itertools.pairwise(times))
        moved += sum(t != n for t, n in zip(times, nominal, strict=True))
        for key, (_, nominal_pos) in zip(
            result.keyframes[b.fp(8)], b.nominal_keyframes(b.fp(8)), strict=True
        ):
            assert abs(key.pos[0] - nominal_pos[0]) <= 0.5
            assert abs(key.pos[1] - nominal_pos[1]) <= 0.5
        assert result.keyframes[b.fp(10)][0].pos == (52.2, 34.0)
    assert moved > 0


def test_without_jitter_times_are_nominal() -> None:
    result = scripted(builder(jitter=False)).build()
    assert [e.t_ms for e in result.events] == [0, *CARRY_TIMES, 5000, 6000]


def test_time_scale_stretches_beats() -> None:
    result = scripted(builder(variant="C", jitter=False)).build()
    assert [e.t_ms for e in result.events][:3] == [0, 700, 1100]


def test_gap_hides_one_player_for_the_window() -> None:
    b = scripted(builder(jitter=False))
    b.gap(["blue-09"], 1000, 2000)
    result = b.build()
    hidden = ~result.visible["blue-09"]
    assert hidden[10:21].all()
    assert not hidden[:10].any()
    assert not hidden[21:].any()
    assert all(mask.all() for pid, mask in result.visible.items() if pid != "blue-09")
    assert len(result.tracks) == 22
    assert result.ball.shape == (61, 3)


def test_build_ends_dead_after_out_of_play() -> None:
    b = builder(jitter=False)
    b.keyframes(b.fp(10), [(0, (52.2, 34.0)), (3000, (54.0, 36.0))], jitter=False)
    b.keyframes(b.fp(8), [(0, (48.0, 32.0)), (3000, (52.0, 32.0))])
    b.beat(0, "kickoff", b.fp(10), recipient=b.fp(8), duration_ms=600)
    b.beat(600, "carry", b.fp(8))
    b.beat(3000, "out_of_play", b.fp(8))
    result = b.build()
    assert result.end_state.phase == Phase.DEAD
    assert result.end_state.restart_team == "amber"
    assert result.end_ms == 3000


def test_event_coordinates_come_from_tracks() -> None:
    result = scripted(builder(3)).build()
    kickoff, carry = result.events[0], result.events[1]
    assert kickoff.start_m == (52.5, 34.0)
    assert kickoff.end_m == carry.start_m
    k = carry.t_ms // 100
    assert np.allclose(result.ball[k, :2], carry.start_m)
    assert np.hypot(*(result.tracks["blue-08"][k] - np.array(carry.start_m))) == pytest.approx(0.3)
