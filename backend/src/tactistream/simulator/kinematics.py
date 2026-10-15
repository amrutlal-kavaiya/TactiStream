"""Bounded player and ball trajectories: splines for scripted actors, clamped followers, ball phases."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

MAX_PLAYER_SPEED_MPS = 9.5
MAX_PLAYER_ACCEL_MPS2 = 6.0
PASS_SPEED_RANGE_MPS = (8.0, 25.0)
SHOT_SPEED_MAX_MPS = 35.0
BALL_CARRY_MAX_DIST_M = 0.5
BALL_CARRY_OFFSET_M = 0.3
REPOSITION_SPEED_MPS = 7.0
REPOSITION_ACCEL_MPS2 = 4.0
REPOSITION_MIN_MS = 3000
FRAME_MS = 100
DEAD_BALL_VISIBLE_BEFORE_RESTART_MS = 1000
LOFT_MIN_DY_M = 30.0
LOFT_PEAK_HEIGHT_M = 6.0
_BOUNDS_EPS = 1e-6
_FACING_WEIGHT_MPS = 0.5

Point = tuple[float, float]
Track = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Keyframe:
    t_ms: int
    pos: Point


KinematicsCode = Literal["speed_exceeded", "accel_exceeded"]


class KinematicsError(ValueError):
    """A trajectory breaks the speed or acceleration bound; generation fails instead of clamping."""

    def __init__(
        self, player_id: str, t_ms: int, speed: float, accel: float, code: KinematicsCode, limit: str
    ) -> None:
        super().__init__(f"{player_id} at {t_ms} ms: {limit} (speed {speed:.2f} m/s, accel {accel:.2f} m/s²)")
        self.player_id = player_id
        self.t_ms = t_ms
        self.speed = speed
        self.accel = accel
        self.code: KinematicsCode = code
        self.limit = limit


def spline_track(keys: Sequence[Keyframe], t_grid: NDArray[np.float64]) -> Track:
    """C1 cubic Hermite through `keys` (Catmull-Rom tangents); at rest at the end keys, held outside."""
    if not keys:
        raise ValueError("spline_track needs at least one keyframe")
    times = np.array([k.t_ms for k in keys], dtype=float)
    if np.any(np.diff(times) <= 0):
        raise ValueError("keyframe times must strictly increase")
    pos = np.array([k.pos for k in keys], dtype=float)
    out = np.empty((len(t_grid), 2), dtype=float)
    if len(keys) == 1:
        out[:] = pos[0]
        return out
    tangents = np.zeros_like(pos)
    tangents[1:-1] = (pos[2:] - pos[:-2]) / (times[2:] - times[:-2])[:, None]
    t = np.clip(np.asarray(t_grid, dtype=float), times[0], times[-1])
    seg = np.clip(np.searchsorted(times, t, side="right") - 1, 0, len(keys) - 2)
    span = times[seg + 1] - times[seg]
    s = ((t - times[seg]) / span)[:, None]
    h00 = 2 * s**3 - 3 * s**2 + 1
    h10 = s**3 - 2 * s**2 + s
    h01 = -2 * s**3 + 3 * s**2
    h11 = s**3 - s**2
    out[:] = (
        h00 * pos[seg]
        + h10 * span[:, None] * tangents[seg]
        + h01 * pos[seg + 1]
        + h11 * span[:, None] * tangents[seg + 1]
    )
    return out


def follow_track(
    targets: NDArray[np.float64],
    start: Point,
    start_vel: Point,
    max_speed: float,
    max_accel: float,
    *,
    response_s: float = 1.0,
    frame_ms: int = FRAME_MS,
) -> Track:
    """Chase per-frame `targets` with speed and acceleration clamped, so the bounds hold by construction."""
    dt = frame_ms / 1000.0
    n = len(targets)
    track = np.empty((n, 2), dtype=float)
    if n == 0:
        return track
    p = np.array(start, dtype=float)
    v = np.array(start_vel, dtype=float)
    track[0] = p
    for k in range(1, n):
        offset = targets[k] - p
        dist = float(np.hypot(*offset))
        if dist > 1e-9:
            desired_speed = min(max_speed, dist / response_s, math.sqrt(2.0 * max_accel * 0.8 * dist))
            v_des = offset / dist * desired_speed
        else:
            v_des = np.zeros(2)
        dv = v_des - v
        dv_norm = float(np.hypot(*dv))
        if dv_norm > max_accel * dt:
            dv *= max_accel * dt / dv_norm
        v = v + dv
        speed = float(np.hypot(*v))
        if speed > max_speed:
            v *= max_speed / speed
        p = p + v * dt
        track[k] = p
    return track


def check_bounds(
    player_id: str,
    track: Track,
    frame_ms: int = FRAME_MS,
    *,
    t0_ms: int = 0,
    max_speed: float = MAX_PLAYER_SPEED_MPS,
    max_accel: float = MAX_PLAYER_ACCEL_MPS2,
) -> None:
    """Raise `KinematicsError` at the first 1-step speed or 1-step second-difference acceleration breach."""
    dt = frame_ms / 1000.0
    speeds = np.hypot(*np.diff(track, axis=0).T) / dt if len(track) > 1 else np.zeros(0)
    accels = np.hypot(*np.diff(track, n=2, axis=0).T) / dt**2 if len(track) > 2 else np.zeros(0)
    bad_speed = np.flatnonzero(speeds > max_speed + _BOUNDS_EPS)
    bad_accel = np.flatnonzero(accels > max_accel + _BOUNDS_EPS)
    first_speed = int(bad_speed[0]) + 1 if len(bad_speed) else None
    first_accel = int(bad_accel[0]) + 1 if len(bad_accel) else None
    if first_speed is None and first_accel is None:
        return
    code: KinematicsCode
    if first_accel is None or (first_speed is not None and first_speed <= first_accel):
        assert first_speed is not None
        k, code, limit = first_speed, "speed_exceeded", f"speed exceeds {max_speed} m/s"
    else:
        k, code, limit = first_accel, "accel_exceeded", f"acceleration exceeds {max_accel} m/s²"
    speed = float(speeds[k - 1])
    accel = float(accels[k - 1]) if 0 < k <= len(accels) else 0.0
    raise KinematicsError(player_id, t0_ms + k * frame_ms, speed, accel, code, limit)


BallPhaseKind = Literal["controlled", "flight", "placed", "dead"]


@dataclass(frozen=True, slots=True)
class BallPhase:
    """Ball state over (start_ms, end_ms]; the first phase also covers its start.

    controlled: carrier position + 0.3 m along the carrier's velocity (`facing` when standing).
    flight: linear `start_pos` -> `end_pos`, height `4·peak·u(1-u)`.
    placed: still and visible at `start_pos`.
    dead: invisible until 1000 ms before `end_ms`, then at the restart spot `end_pos` (invisible if none).
    """

    kind: BallPhaseKind
    start_ms: int
    end_ms: int
    player_id: str | None = None
    start_pos: Point | None = None
    end_pos: Point | None = None
    peak_height_m: float = 0.0
    facing: Point = (1.0, 0.0)


def carry_offsets(track: Track, facing: Point) -> Track:
    """Ball offset from a carrier: 0.3 m along the velocity, blended toward `facing` when slow."""
    vel = np.gradient(track, FRAME_MS / 1000.0, axis=0) if len(track) > 1 else np.zeros_like(track)
    direction = vel + _FACING_WEIGHT_MPS * np.asarray(facing, dtype=float)
    norm = np.hypot(*direction.T)[:, None]
    fallback = np.broadcast_to(np.asarray(facing, dtype=float), direction.shape)
    unit = np.where(norm > 1e-9, direction / np.where(norm > 1e-9, norm, 1.0), fallback)
    return np.asarray(unit * BALL_CARRY_OFFSET_M, dtype=float)


def _phase_index(phases: Sequence[BallPhase], t: float) -> int:
    for i, phase in enumerate(phases):
        if t <= phase.end_ms:
            return i
    return len(phases) - 1


def ball_track(
    possession_timeline: Sequence[BallPhase],
    player_tracks: Mapping[str, Track],
    *,
    t0_ms: int | None = None,
) -> Track:
    """Ball (x, y, height) per frame from `t0_ms` to the last phase end; NaN rows while invisible."""
    if not possession_timeline:
        raise ValueError("ball_track needs at least one phase")
    t0 = possession_timeline[0].start_ms if t0_ms is None else t0_ms
    end = possession_timeline[-1].end_ms
    times = np.arange(t0, end + 1, FRAME_MS, dtype=float)
    ball = np.full((len(times), 3), np.nan)
    offsets: dict[tuple[str, Point], Track] = {}
    for k, t in enumerate(times):
        phase = possession_timeline[_phase_index(possession_timeline, t)]
        if phase.kind == "controlled":
            assert phase.player_id is not None
            key = (phase.player_id, phase.facing)
            if key not in offsets:
                offsets[key] = carry_offsets(player_tracks[phase.player_id], phase.facing)
            carrier = player_tracks[phase.player_id][k]
            ball[k] = (*(carrier + offsets[key][k]), 0.0)
        elif phase.kind == "flight":
            assert phase.start_pos is not None and phase.end_pos is not None
            span = phase.end_ms - phase.start_ms
            u = 1.0 if span <= 0 else min(max((t - phase.start_ms) / span, 0.0), 1.0)
            a, b = np.asarray(phase.start_pos), np.asarray(phase.end_pos)
            ball[k] = (*(a + (b - a) * u), 4.0 * phase.peak_height_m * u * (1.0 - u))
        elif phase.kind == "placed":
            assert phase.start_pos is not None
            ball[k] = (*phase.start_pos, 0.0)
        elif phase.end_pos is not None and t >= phase.end_ms - DEAD_BALL_VISIBLE_BEFORE_RESTART_MS:
            ball[k] = (*phase.end_pos, 0.0)
    return ball


def reposition_duration_ms(max_distance_m: float) -> int:
    """Shortest 100 ms multiple (>= 3000) fitting a rest-to-rest move of `max_distance_m` at 7 m/s, 4 m/s²."""
    needed_s = max_distance_m / REPOSITION_SPEED_MPS + REPOSITION_SPEED_MPS / REPOSITION_ACCEL_MPS2
    return max(REPOSITION_MIN_MS, math.ceil(round(needed_s * 1000.0, 6) / FRAME_MS) * FRAME_MS)


def _trapezoid(distance: float, duration_s: float, t: NDArray[np.float64]) -> NDArray[np.float64]:
    a = REPOSITION_ACCEL_MPS2
    disc = max(a * a * duration_s * duration_s - 4.0 * a * distance, 0.0)
    cruise = (a * duration_s - math.sqrt(disc)) / 2.0
    if cruise <= 0.0:
        return np.zeros_like(t)
    ta = cruise / a
    s = np.where(
        t < ta,
        0.5 * a * t**2,
        np.where(
            t <= duration_s - ta,
            0.5 * a * ta**2 + cruise * (t - ta),
            distance - 0.5 * a * (duration_s - t) ** 2,
        ),
    )
    return np.asarray(s, dtype=float)


def plan_reposition(start: Mapping[str, Point], end: Mapping[str, Point]) -> tuple[int, dict[str, Track]]:
    """Rest-to-rest straight moves for every player over one shared duration (<= 7 m/s, <= 4 m/s²)."""
    distances = {pid: math.dist(start[pid], end[pid]) for pid in start}
    duration = reposition_duration_ms(max(distances.values(), default=0.0))
    t = np.arange(0, duration + 1, FRAME_MS, dtype=float) / 1000.0
    tracks: dict[str, Track] = {}
    for pid, distance in distances.items():
        a, b = np.asarray(start[pid], dtype=float), np.asarray(end[pid], dtype=float)
        if distance <= 1e-9:
            tracks[pid] = np.tile(a, (len(t), 1))
            continue
        s = _trapezoid(distance, duration / 1000.0, t)
        track = a + np.outer(s / distance, b - a)
        track[-1] = b
        tracks[pid] = track
    return duration, tracks
