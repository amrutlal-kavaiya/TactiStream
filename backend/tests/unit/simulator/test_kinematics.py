import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tactistream.simulator.kinematics import (
    FRAME_MS,
    MAX_PLAYER_ACCEL_MPS2,
    MAX_PLAYER_SPEED_MPS,
    REPOSITION_ACCEL_MPS2,
    REPOSITION_MIN_MS,
    REPOSITION_SPEED_MPS,
    BallPhase,
    Keyframe,
    KinematicsError,
    ball_track,
    check_bounds,
    follow_track,
    plan_reposition,
    spline_track,
)


def grid(start_ms: int, end_ms: int) -> np.ndarray:
    return np.arange(start_ms, end_ms + 1, FRAME_MS, dtype=float)


def test_spline_passes_through_every_keyframe() -> None:
    keys = [
        Keyframe(0, (10.0, 10.0)),
        Keyframe(1000, (12.0, 11.0)),
        Keyframe(2500, (20.0, 15.0)),
        Keyframe(4000, (22.0, 14.0)),
    ]
    t = grid(0, 4000)
    track = spline_track(keys, t)
    assert track.shape == (41, 2)
    for key in keys:
        assert np.allclose(track[key.t_ms // FRAME_MS], key.pos, atol=1e-9)


def test_spline_holds_outside_keyframes_and_starts_at_rest() -> None:
    keys = [Keyframe(1000, (10.0, 10.0)), Keyframe(3000, (14.0, 10.0))]
    track = spline_track(keys, grid(0, 4000))
    assert np.allclose(track[:11], (10.0, 10.0))
    assert np.allclose(track[30:], (14.0, 10.0))
    assert np.allclose(track[11] - track[10], 0.0, atol=0.05)


def test_check_bounds_rejects_excess_speed() -> None:
    track = np.column_stack([np.linspace(0.0, 15.0, 11), np.zeros(11)])
    with pytest.raises(KinematicsError) as info:
        check_bounds("blue-09", track, t0_ms=2000)
    assert info.value.player_id == "blue-09"
    assert info.value.t_ms == 2100
    assert info.value.speed == pytest.approx(15.0)
    assert info.value.code == "speed_exceeded"


def test_check_bounds_rejects_excess_acceleration() -> None:
    x = [0.0, 0.0, 0.0, 0.3, 0.6, 0.9, 1.2]
    track = np.column_stack([x, np.zeros(len(x))])
    with pytest.raises(KinematicsError) as info:
        check_bounds("amber-04", track)
    assert info.value.player_id == "amber-04"
    assert info.value.t_ms == 200
    assert info.value.accel == pytest.approx(30.0)
    assert info.value.code == "accel_exceeded"


def test_check_bounds_accepts_limits() -> None:
    steady = np.column_stack([np.linspace(0.0, 9.5, 11), np.zeros(11)])
    check_bounds("blue-01", steady)


points = st.tuples(st.floats(0.0, 105.0), st.floats(0.0, 68.0))


@settings(derandomize=True, max_examples=200, deadline=None)
@given(
    targets=st.lists(st.tuples(points, st.integers(1, 15)), min_size=1, max_size=12),
    start=points,
    start_vel=st.tuples(st.floats(-6.0, 6.0), st.floats(-6.0, 6.0)),
)
def test_follow_track_never_exceeds_bounds(
    targets: list[tuple[tuple[float, float], int]],
    start: tuple[float, float],
    start_vel: tuple[float, float],
) -> None:
    sequence = np.array([pos for pos, repeat in targets for _ in range(repeat)], dtype=float)
    track = follow_track(sequence, start, start_vel, MAX_PLAYER_SPEED_MPS, MAX_PLAYER_ACCEL_MPS2)
    assert track.shape == sequence.shape
    assert tuple(track[0]) == start
    check_bounds("blue-02", track)


def test_follow_track_reaches_a_still_target() -> None:
    targets = np.tile((30.0, 20.0), (80, 1))
    track = follow_track(targets, (20.0, 20.0), (0.0, 0.0), 7.0, 3.0)
    assert math.dist(track[-1], (30.0, 20.0)) < 0.2


def test_ball_track_controlled_pass_and_dead_ball() -> None:
    carrier = np.column_stack([np.linspace(40.0, 46.0, 21), np.linspace(30.0, 32.0, 21)])
    receiver = np.tile((60.0, 40.0), (61, 1))
    tracks = {"blue-08": np.vstack([carrier, np.tile(carrier[-1], (40, 1))]), "blue-11": receiver}
    pass_start = (46.3, 32.1)
    phases = [
        BallPhase("controlled", 0, 2000, player_id="blue-08"),
        BallPhase("flight", 2000, 3000, start_pos=pass_start, end_pos=(60.0, 40.0)),
        BallPhase("dead", 3000, 6000, end_pos=(70.0, 0.0)),
    ]
    ball = ball_track(phases, tracks)
    assert ball.shape == (61, 3)
    for k in range(20):
        assert math.dist(ball[k, :2], tracks["blue-08"][k]) == pytest.approx(0.30, abs=0.01)
    midpoint = ((pass_start[0] + 60.0) / 2, (pass_start[1] + 40.0) / 2)
    assert math.dist(ball[25, :2], midpoint) <= 0.01
    assert np.allclose(ball[30, :2], (60.0, 40.0))
    assert np.isnan(ball[31:50]).all()
    assert np.allclose(ball[50:, :2], (70.0, 0.0))


def test_ball_track_lofted_pass_height() -> None:
    phases = [BallPhase("flight", 0, 2000, start_pos=(30.0, 10.0), end_pos=(40.0, 50.0), peak_height_m=6.0)]
    ball = ball_track(phases, {})
    assert ball[10, 2] == pytest.approx(6.0)
    assert ball[0, 2] == pytest.approx(0.0)
    assert ball[20, 2] == pytest.approx(0.0)


def test_ball_invisible_through_end_without_restart() -> None:
    phases = [
        BallPhase("placed", 0, 500, start_pos=(52.5, 34.0)),
        BallPhase("dead", 500, 2000),
    ]
    ball = ball_track(phases, {})
    assert np.allclose(ball[:5, :2], (52.5, 34.0))
    assert np.isnan(ball[6:]).all()


def test_plan_reposition_is_bounded() -> None:
    start = {"blue-02": (30.0, 10.0), "blue-09": (80.0, 40.0), "amber-01": (99.0, 34.0)}
    end = {"blue-02": (28.0, 12.0), "blue-09": (45.0, 30.0), "amber-01": (99.0, 34.0)}
    duration, tracks = plan_reposition(start, end)
    assert duration >= REPOSITION_MIN_MS
    assert duration % FRAME_MS == 0
    for pid, track in tracks.items():
        assert track.shape == (duration // FRAME_MS + 1, 2)
        assert np.allclose(track[0], start[pid])
        assert np.allclose(track[-1], end[pid])
        check_bounds(pid, track, max_speed=REPOSITION_SPEED_MPS, max_accel=REPOSITION_ACCEL_MPS2)


def test_plan_reposition_short_moves_take_minimum_time() -> None:
    duration, _ = plan_reposition({"blue-02": (30.0, 10.0)}, {"blue-02": (31.0, 10.0)})
    assert duration == REPOSITION_MIN_MS
