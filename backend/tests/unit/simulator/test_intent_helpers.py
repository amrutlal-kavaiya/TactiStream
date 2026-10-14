import pytest
from simulator.intent import (
    Tracks,
    angle_to_axis_deg,
    best_run,
    lane_clearance,
    nearest_opponent_distance,
    normalize,
    pressure_proxy,
)

from tactistream.contracts import TrackingFrame


def test_pressure_proxy() -> None:
    assert round(pressure_proxy([1.0, 2.0, 3.0]), 1) == 47.4
    assert round(pressure_proxy([5.0, 7.5, 10.0]), 1) == 6.8
    assert pressure_proxy([10.0, 1.0, 2.0, 3.0]) == pressure_proxy([1.0, 2.0, 3.0])


def test_lane_clearance() -> None:
    # Point-to-segment distance for the literal task inputs is 1.75 m (the "≈ 2.4 m" design value needs the
    # hero's t-4000 geometry below).
    assert lane_clearance((58.0, 32.0), (69.0, 27.5), [(67.5, 30.0)]) == pytest.approx(1.75, abs=0.1)
    assert lane_clearance((57.0, 31.5), (70.0, 26.5), [(67.5, 30.0)]) == pytest.approx(2.4, abs=0.1)
    assert lane_clearance((0.0, 0.0), (10.0, 0.0), [(15.0, 0.0), (5.0, 3.0)]) == pytest.approx(3.0)
    assert lane_clearance((0.0, 0.0), (10.0, 0.0), []) == float("inf")


def test_angle_and_normalize() -> None:
    assert angle_to_axis_deg((9.0, 10.0), attack_dir=1) == pytest.approx(48.0, abs=0.1)
    assert angle_to_axis_deg((-9.0, 10.0), attack_dir=-1) == pytest.approx(48.0, abs=0.1)
    assert angle_to_axis_deg((9.0, -10.0), attack_dir=1) == pytest.approx(48.0, abs=0.1)
    assert normalize((10.0, 20.0), -1) == (95.0, 48.0)
    assert normalize((10.0, 20.0), 1) == (10.0, 20.0)


def _frames(paths: dict[str, list[tuple[float, float] | None]]) -> list[TrackingFrame]:
    n = len(next(iter(paths.values())))
    return [
        TrackingFrame.model_validate(
            {
                "schema_version": "1.0",
                "match_id": "sim-0123456789",
                "frame_id": f"frm-{k:06d}",
                "frame_index": k,
                "period": 1,
                "period_clock_ms": 840000 + k * 100,
                "session_clock_ms": k * 100,
                "players": [
                    {"player_id": pid, "visible": False}
                    if path[k] is None
                    else {"player_id": pid, "visible": True, "pos_m": path[k]}
                    for pid, path in paths.items()
                ],
                "ball": {"visible": False},
                "source": {"kind": "synthetic", "generator_version": "0.1.0", "seed": 1},
            }
        )
        for k in range(n)
    ]


def test_best_run_finds_the_diagonal_run() -> None:
    still: list[tuple[float, float] | None] = [(50.0, 30.0)] * 41
    run: list[tuple[float, float] | None] = [(60.0, 30.0)] * 10 + [
        (60.0 + 0.3 * k, 30.0 + 0.3333 * k) for k in range(31)
    ]
    frames = _frames({"blue-08": still, "blue-09": run, "amber-04": still})
    tracks = Tracks.from_frames(frames)
    found = best_run(tracks, ["blue-08", "blue-09"], (0, 4000), attack_dir=1)
    assert found is not None
    assert found.player_id == "blue-09"
    assert found.displacement_m >= 10.0
    assert 30.0 <= found.angle_deg <= 60.0
    assert found.end_ms - found.start_ms <= 3200
    assert best_run(tracks, ["blue-09"], (0, 4000), attack_dir=-1) is None
    assert best_run(tracks, ["blue-08"], (0, 4000), attack_dir=1) is None


def test_nearest_opponent_distance_ignores_invisible_players() -> None:
    frames = _frames(
        {"blue-09": [(60.0, 30.0)], "amber-04": [None], "amber-05": [(63.0, 34.0)], "blue-10": [(60.5, 30.0)]}
    )
    tracks = Tracks.from_frames(frames)
    assert nearest_opponent_distance(tracks, "blue-09", 0) == pytest.approx(5.0)
