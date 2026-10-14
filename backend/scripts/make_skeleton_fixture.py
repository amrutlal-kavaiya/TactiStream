"""Generate `data/fixtures/skeleton.jsonl`: walking-skeleton feed (metadata, 4 events, 60 frames at 10 Hz).

Run from `backend/`: `uv run python scripts/make_skeleton_fixture.py`. Output is deterministic.
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
METADATA_EXAMPLE = REPO / "contracts" / "examples" / "match_metadata.json"
OUTPUT = REPO / "data" / "fixtures" / "skeleton.jsonl"

MATCH_ID = "demo-blue-amber-001"
EPOCH_MS = 1_792_000_000_000
SOURCE = {"kind": "synthetic", "generator_version": "0.1.0", "seed": 42}
FRAME_COUNT = 60
FRAME_INTERVAL_MS = 100

Point = tuple[float, float]

# 4-4-2 shapes; each team starts in its own half (Blue attacks +x).
BLUE_BASE: dict[str, Point] = {
    "blue-01": (5.0, 34.0),
    "blue-02": (25.0, 8.0),
    "blue-03": (22.0, 26.0),
    "blue-04": (22.0, 42.0),
    "blue-05": (25.0, 60.0),
    "blue-06": (40.0, 44.0),
    "blue-07": (42.0, 58.0),
    "blue-09": (51.0, 40.0),
    "blue-10": (52.3, 34.6),
}
AMBER_BASE: dict[str, Point] = {
    "amber-01": (100.0, 34.0),
    "amber-02": (80.0, 60.0),
    "amber-03": (83.0, 42.0),
    "amber-04": (83.0, 26.0),
    "amber-05": (80.0, 8.0),
    "amber-06": (65.0, 24.0),
    "amber-07": (63.0, 10.0),
    "amber-08": (64.0, 38.0),
    "amber-11": (63.0, 56.0),
    "amber-09": (56.0, 30.0),
    "amber-10": (56.0, 40.0),
}

# Piecewise-linear paths as (time_ms, point) keyframes; held constant outside the keyframes.
BLUE_08_PATH: list[tuple[int, Point]] = [(0, (52.0, 33.0)), (1500, (52.0, 33.0)), (3000, (58.1, 32.4))]
BLUE_11_PATH: list[tuple[int, Point]] = [(0, (50.0, 29.0)), (3900, (71.2, 28.0)), (5400, (75.0, 27.0))]
BALL_PATH: list[tuple[int, Point]] = [
    (0, (52.5, 34.0)),
    (1500, (52.0, 33.0)),
    (3000, (58.1, 32.4)),
    (3900, (71.2, 28.0)),
    (5400, (75.0, 27.0)),
]


def _interpolate(path: list[tuple[int, Point]], t: int) -> Point:
    if t <= path[0][0]:
        return path[0][1]
    for (t0, (x0, y0)), (t1, (x1, y1)) in itertools.pairwise(path):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)
    return path[-1][1]


def _carry(t: int, start: int, duration: int, path: list[tuple[int, Point]]) -> Point:
    return _interpolate(path, min(max(t, start), start + duration))


def _sway(base: Point, t: int, phase: int) -> Point:
    angle = 2 * math.pi * t / 3000 + phase
    return (base[0] + 0.4 * math.sin(angle), base[1] + 0.3 * math.cos(angle))


def _pos(point: Point) -> list[float]:
    return [round(point[0], 2), round(point[1], 2)]


def _player_position(player_id: str, t: int, phase: int) -> Point:
    if player_id == "blue-08":
        return _interpolate(BLUE_08_PATH, t)
    if player_id == "blue-11":
        return _interpolate(BLUE_11_PATH, t)
    base = BLUE_BASE.get(player_id) or AMBER_BASE[player_id]
    return _sway(base, t, phase)


def _event(sequence: int, t: int, **fields: Any) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "match_id": MATCH_ID,
        "event_id": f"evt-{sequence:04d}",
        "sequence": sequence,
        "period": 1,
        "period_clock_ms": t,
        "session_clock_ms": t,
        **fields,
        "source": SOURCE,
    }


def _events() -> list[dict[str, Any]]:
    return [
        _event(
            40,
            0,
            event_type="kickoff",
            team_id="blue",
            player_id="blue-10",
            start_m=[52.5, 34.0],
            outcome=None,
        ),
        _event(
            41,
            1500,
            event_type="carry",
            team_id="blue",
            player_id="blue-08",
            start_m=[52.0, 33.0],
            end_m=[58.1, 32.4],
            duration_ms=1500,
            outcome=None,
        ),
        _event(
            42,
            3000,
            event_type="pass",
            team_id="blue",
            player_id="blue-08",
            recipient_id="blue-11",
            start_m=[58.1, 32.4],
            end_m=[71.2, 28.0],
            duration_ms=900,
            outcome="complete",
        ),
        _event(
            43,
            3900,
            event_type="carry",
            team_id="blue",
            player_id="blue-11",
            start_m=[71.2, 28.0],
            end_m=[75.0, 27.0],
            duration_ms=1500,
            outcome=None,
        ),
    ]


def _frame(index: int, player_ids: list[str]) -> dict[str, Any]:
    t = index * FRAME_INTERVAL_MS
    return {
        "schema_version": "1.0",
        "match_id": MATCH_ID,
        "frame_id": f"frm-{index:06d}",
        "frame_index": index,
        "period": 1,
        "period_clock_ms": t,
        "session_clock_ms": t,
        "players": [
            {"player_id": pid, "visible": True, "pos_m": _pos(_player_position(pid, t, phase))}
            for phase, pid in enumerate(player_ids)
        ],
        "ball": {"visible": True, "pos_m": _pos(_interpolate(BALL_PATH, t)), "height_m": 0.1},
        "source": SOURCE,
    }


def _envelope(kind: str, record_id: str, t: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "kind": kind,
        "match_id": MATCH_ID,
        "record_id": record_id,
        "published_ms": EPOCH_MS + t,
        "payload": payload,
    }


def build_lines() -> list[str]:
    metadata = json.loads(METADATA_EXAMPLE.read_text(encoding="utf-8"))
    player_ids = [p["player_id"] for team in metadata["teams"] for p in team["players"]]
    timed: list[tuple[int, int, dict[str, Any]]] = []
    for event in _events():
        timed.append(
            (
                event["session_clock_ms"],
                0,
                _envelope("event", event["event_id"], event["session_clock_ms"], event),
            )
        )
    for index in range(FRAME_COUNT):
        frame = _frame(index, player_ids)
        timed.append(
            (
                frame["session_clock_ms"],
                1,
                _envelope("frame", frame["frame_id"], frame["session_clock_ms"], frame),
            )
        )
    timed.sort(key=lambda item: (item[0], item[1]))
    envelopes = [_envelope("metadata", MATCH_ID, 0, metadata), *(env for _, _, env in timed)]
    return [json.dumps(env, ensure_ascii=False, separators=(",", ":")) for env in envelopes]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(build_lines()) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
