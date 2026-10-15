"""Test-only helpers: attack-normalized geometry and one intent check per scenario family.

Checks use local geometry so 002 does not depend on 003; margins sit above 003's detection thresholds.
Each `check_<family>(output, label_window)` returns failure messages; an empty list means the intent holds.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
from numpy.typing import NDArray

from tactistream.contracts import MatchEvent, TrackingFrame
from tactistream.simulator.config import VARIANTS, SimulationConfig
from tactistream.simulator.engine import simulate
from tactistream.simulator.possession import IllegalTransition, PossessionState, is_turnover, transition

Point = tuple[float, float]
Window = tuple[int, int]
ON_BALL = ("kickoff", "pass", "carry", "shot", "clearance")


def normalize(p: Point, attack_dir: int) -> Point:
    """Rotate stadium coordinates so the team attacks +x."""
    return (p[0], p[1]) if attack_dir == 1 else (105.0 - p[0], 68.0 - p[1])


def angle_to_axis_deg(vec: Point, attack_dir: int) -> float:
    """Angle in degrees between a displacement and the attack axis (0 = straight at goal, 90 = square)."""
    dx, dy = vec[0] * attack_dir, abs(vec[1])
    return math.degrees(math.atan2(dy, dx))


def point_segment_distance(p: Point, a: Point, b: Point) -> float:
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    length2 = vx * vx + vy * vy
    u = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / length2))
    return math.dist(p, (ax + u * vx, ay + u * vy))


def lane_clearance(passer: Point, receiver: Point, defenders: Iterable[Point]) -> float:
    """Minimum distance from any defender to the passer -> receiver segment."""
    return min((point_segment_distance(d, passer, receiver) for d in defenders), default=float("inf"))


def pressure_proxy(distances: Iterable[float]) -> float:
    """(100/3) * sum(exp(-d/2.5)) over the three nearest distances."""
    nearest = sorted(distances)[:3]
    return (100.0 / 3.0) * sum(math.exp(-d / 2.5) for d in nearest)


class Tracks:
    """Per-player positions on the frame grid (NaN while invisible), indexed by session time."""

    def __init__(self, t0_ms: int, positions: dict[str, NDArray[np.float64]], periods: list[int]) -> None:
        self.t0_ms = t0_ms
        self.positions = positions
        self.periods = periods

    @classmethod
    def from_frames(cls, frames: Sequence[TrackingFrame]) -> Tracks:
        ids = [p.player_id for p in frames[0].players]
        positions = {pid: np.full((len(frames), 2), np.nan) for pid in ids}
        for k, frame in enumerate(frames):
            for p in frame.players:
                if p.visible and p.pos_m is not None:
                    positions.setdefault(p.player_id, np.full((len(frames), 2), np.nan))[k] = p.pos_m
        return cls(frames[0].session_clock_ms, positions, [f.period for f in frames])

    def index(self, t_ms: int) -> int:
        return max(0, min(len(self.periods) - 1, round((t_ms - self.t0_ms) / 100)))

    def at(self, player_id: str, t_ms: int) -> Point | None:
        x, y = self.positions[player_id][self.index(t_ms)]
        return None if math.isnan(x) else (float(x), float(y))

    def team_at(self, team: str, t_ms: int) -> dict[str, Point]:
        out: dict[str, Point] = {}
        for pid in self.positions:
            if pid.startswith(team + "-"):
                pos = self.at(pid, t_ms)
                if pos is not None:
                    out[pid] = pos
        return out


def relabel(output: Any, **key_players: str) -> Any:
    """A copy of `output` whose first manifest segment names different key players."""
    first, *rest = output.manifest.segments
    label = replace(first, key_players={**first.key_players, **key_players})
    return replace(output, manifest=replace(output.manifest, segments=(label, *rest)))


def _tracks(frames: Tracks | Sequence[TrackingFrame]) -> Tracks:
    return frames if isinstance(frames, Tracks) else Tracks.from_frames(frames)


def _opponent(team: str) -> str:
    return "amber" if team == "blue" else "blue"


def nearest_opponent_distance(frames: Tracks | Sequence[TrackingFrame], player_id: str, t_ms: int) -> float:
    tracks = _tracks(frames)
    me = tracks.at(player_id, t_ms)
    if me is None:
        return float("nan")
    others = tracks.team_at(_opponent(player_id.split("-")[0]), t_ms).values()
    return min((math.dist(me, o) for o in others), default=float("inf"))


def nearest_opponent(frames: Tracks | Sequence[TrackingFrame], player_id: str, t_ms: int) -> str | None:
    tracks = _tracks(frames)
    me = tracks.at(player_id, t_ms)
    if me is None:
        return None
    others = tracks.team_at(_opponent(player_id.split("-")[0]), t_ms)
    return min(others, key=lambda pid: math.dist(me, others[pid]), default=None)


def _pressure_on(tracks: Tracks, player_id: str, t_ms: int) -> float:
    me = tracks.at(player_id, t_ms)
    if me is None:
        return float("nan")
    others = tracks.team_at(_opponent(player_id.split("-")[0]), t_ms).values()
    return pressure_proxy(math.dist(me, o) for o in others)


@dataclass(frozen=True)
class Run:
    player_id: str
    start_ms: int
    end_ms: int
    vector: Point
    displacement_m: float
    mean_speed_mps: float
    angle_deg: float


def best_run(
    frames: Tracks | Sequence[TrackingFrame],
    player_ids: Iterable[str],
    window: Window,
    *,
    attack_dir: int,
    max_ms: int = 3200,
    min_displacement_m: float = 10.0,
    min_speed_mps: float = 4.3,
    angle_range: tuple[float, float] = (30.0, 60.0),
) -> Run | None:
    """Largest straight-line displacement over <= `max_ms` inside `window` that meets every threshold."""
    tracks = _tracks(frames)
    lo, hi = tracks.index(window[0]), tracks.index(window[1])
    best: Run | None = None
    for pid in player_ids:
        pos = tracks.positions[pid][lo : hi + 1]
        for lag in range(1, min(max_ms // 100, len(pos) - 1) + 1):
            disp = pos[lag:] - pos[:-lag]
            dist = np.hypot(disp[:, 0], disp[:, 1])
            for i in np.flatnonzero(np.nan_to_num(dist, nan=0.0) >= min_displacement_m):
                vec = (float(disp[i, 0]), float(disp[i, 1]))
                d = float(dist[i])
                speed = d / (lag / 10.0)
                angle = angle_to_axis_deg(vec, attack_dir)
                if speed < min_speed_mps or not angle_range[0] <= angle <= angle_range[1]:
                    continue
                if best is None or d > best.displacement_m:
                    start = tracks.t0_ms + (lo + int(i)) * 100
                    best = Run(pid, start, start + lag * 100, vec, d, speed, angle)
    return best


class _Context:
    """Events, tracks and focus team of one labelled window of a simulator output."""

    def __init__(self, output: Any, window: Window) -> None:
        self.output = output
        self.window = window
        self.tracks = Tracks.from_frames(output.frames)
        label = next(
            (s for s in output.manifest.segments if s.start_ms <= window[1] and s.end_ms >= window[0]), None
        )
        variant = label.variant if label is not None else output.config.variant
        self.label = label
        self.keys: Mapping[str, str] = label.key_players if label is not None else {}
        self.focus = VARIANTS[variant].focus_team
        self.opp = _opponent(self.focus)
        self.events: list[MatchEvent] = [
            e for e in output.events if window[0] <= e.session_clock_ms <= window[1]
        ]
        period = self.events[0].period if self.events else 1
        direction = next(p.attack_direction for p in output.metadata.periods if p.period == period)
        self.attack_dir = direction.blue if self.focus == "blue" else direction.amber

    def focus_turnovers(self) -> list[MatchEvent]:
        state = PossessionState.start()
        found: list[MatchEvent] = []
        for event in self.output.events:
            try:
                nxt = transition(state, event)
            except IllegalTransition:
                continue
            if (
                event in self.events
                and event.team_id == self.focus
                and state.team_id != self.focus
                and is_turnover(state, event)
            ):
                found.append(event)
            state = nxt
        return found

    def identity(self, role: str, actual: str | None) -> list[str]:
        """Failure if the manifest names a different player for `role`."""
        expected = self.keys.get(role)
        if expected is None or actual == expected:
            return []
        return [f"{role} is {actual}, manifest key_players says {expected}"]

    def lane(self, passer: str, receiver: str, t_ms: int) -> float:
        a, b = self.tracks.at(passer, t_ms), self.tracks.at(receiver, t_ms)
        if a is None or b is None:
            return float("nan")
        return lane_clearance(a, b, self.tracks.team_at(self.opp, t_ms).values())


def _arrival(event: MatchEvent) -> int:
    return event.session_clock_ms + (event.duration_ms or 0)


def _forward_pass(ctx: _Context) -> tuple[MatchEvent | None, MatchEvent | None]:
    shots = [e for e in ctx.events if e.event_type == "shot" and e.team_id == ctx.focus]
    if not shots:
        return None, None
    shot = shots[0]
    passes = [
        e
        for e in ctx.events
        if e.event_type == "pass"
        and e.team_id == ctx.focus
        and e.outcome == "complete"
        and e.session_clock_ms < shot.session_clock_ms
    ]
    return (passes[-1] if passes else None), shot


def _space_checks(output: Any, window: Window, *, negative: bool) -> list[str]:
    ctx = _Context(output, window)
    failures: list[str] = []
    fwd, shot = _forward_pass(ctx)
    if fwd is None or shot is None:
        return ["no completed focus-team pass followed by a focus-team shot"]
    t_pass = fwd.session_clock_ms
    if shot.session_clock_ms - t_pass > 6000:
        failures.append(f"shot {shot.session_clock_ms - t_pass} ms after the forward pass (> 6000)")
    assert fwd.recipient_id is not None
    failures += ctx.identity("passer", fwd.player_id) + ctx.identity("receiver", fwd.recipient_id)
    candidates = [
        pid
        for pid in ctx.tracks.positions
        if pid.startswith(ctx.focus + "-") and pid not in (fwd.player_id, fwd.recipient_id)
    ]
    run = best_run(ctx.tracks, candidates, (t_pass - 4000, t_pass), attack_dir=ctx.attack_dir)
    if run is None:
        failures.append("no off-ball run >= 10 m within 3.2 s at >= 4.3 m/s and 30-60 degrees")
    else:
        failures += ctx.identity("runner", run.player_id)
    if run is not None and not negative:
        runner_at = ctx.tracks.at(run.player_id, run.start_ms)
        opponents = ctx.tracks.team_at(ctx.opp, run.start_ms)
        assert runner_at is not None
        follower = min(opponents, key=lambda pid: math.dist(opponents[pid], runner_at))
        failures += ctx.identity("follower", follower)
        a, b = ctx.tracks.at(follower, run.start_ms), ctx.tracks.at(follower, run.end_ms)
        if a is None or b is None:
            failures.append(f"follower {follower} not visible over the run")
        else:
            fv = (b[0] - a[0], b[1] - a[1])
            norm = math.hypot(*fv) * run.displacement_m
            cos = (fv[0] * run.vector[0] + fv[1] * run.vector[1]) / norm if norm else 0.0
            if cos < 0.8:
                failures.append(f"follower {follower} cosine with run {cos:.2f} < 0.8")
    gain = ctx.lane(fwd.player_id, fwd.recipient_id, t_pass) - ctx.lane(
        fwd.player_id, fwd.recipient_id, t_pass - 4000
    )
    if math.isnan(gain):
        failures.append("lane clearance not measurable (passer or receiver invisible)")
    elif negative and gain > 1.0:
        failures.append(f"lane clearance gain {gain:.2f} m > 1.0")
    elif not negative and gain < 2.5:
        failures.append(f"lane clearance gain {gain:.2f} m < 2.5")
    return failures


def check_space_creation(output: Any, label_window: Window) -> list[str]:
    return _space_checks(output, label_window, negative=False)


def check_run_no_channel(output: Any, label_window: Window) -> list[str]:
    return _space_checks(output, label_window, negative=True)


def _victim_events(ctx: _Context) -> list[MatchEvent]:
    return [e for e in ctx.events if e.team_id == ctx.opp and e.event_type in ON_BALL]


def check_press_turnover(output: Any, label_window: Window) -> list[str]:
    ctx = _Context(output, label_window)
    turnovers = ctx.focus_turnovers()
    if not turnovers:
        return ["no focus-team turnover"]
    turnover = turnovers[0]
    before = [e for e in _victim_events(ctx) if e.session_clock_ms <= turnover.session_clock_ms]
    if not before:
        return ["no opponent on-ball event before the turnover"]
    last = before[-1]
    failures = ctx.identity("victim", last.player_id) + ctx.identity("interceptor", turnover.player_id)
    gap = turnover.session_clock_ms - last.session_clock_ms
    if gap > 3000:
        failures.append(f"turnover {gap} ms after the victim's last on-ball event (> 3000)")
    pressure = _pressure_on(ctx.tracks, last.player_id, last.session_clock_ms)
    if not pressure >= 40.0:
        failures.append(f"pressure on {last.player_id} {pressure:.1f} < 40")
    return failures


def check_press_no_turnover(output: Any, label_window: Window) -> list[str]:
    ctx = _Context(output, label_window)
    turnovers = [t.session_clock_ms for t in ctx.focus_turnovers()]
    pressed = [
        e for e in _victim_events(ctx) if _pressure_on(ctx.tracks, e.player_id, e.session_clock_ms) >= 40.0
    ]
    if not pressed:
        return ["no opponent on-ball event under pressure >= 40"]
    victim = ctx.keys.get("victim")
    if victim is not None and all(e.player_id != victim for e in pressed):
        return [f"victim {victim} (manifest key_players) never under pressure >= 40"]
    for e in pressed:
        if any(e.session_clock_ms < t <= e.session_clock_ms + 5000 for t in turnovers):
            return [f"focus-team turnover within 5000 ms of pressed event {e.event_id}"]
    return []


def _switches(ctx: _Context, min_dy: float) -> list[MatchEvent]:
    return [
        e
        for e in ctx.events
        if e.event_type == "pass"
        and e.team_id == ctx.focus
        and e.outcome == "complete"
        and e.end_m is not None
        and abs(e.end_m[1] - e.start_m[1]) >= min_dy
    ]


def check_switch_escape(output: Any, label_window: Window) -> list[str]:
    ctx = _Context(output, label_window)
    switches = _switches(ctx, 34.0)
    if not switches:
        return ["no completed focus-team pass with |dy| >= 34 m"]
    switch = switches[0]
    assert switch.recipient_id is not None
    failures = ctx.identity("switcher", switch.player_id) + ctx.identity("receiver", switch.recipient_id)
    distance = nearest_opponent_distance(ctx.tracks, switch.recipient_id, _arrival(switch))
    if not distance >= 7.0:
        failures.append(f"receiver's nearest opponent {distance:.2f} m < 7 at reception")
    return failures


def check_switch_closed(output: Any, label_window: Window) -> list[str]:
    ctx = _Context(output, label_window)
    switches = _switches(ctx, 30.0)
    if not switches:
        return ["no completed focus-team pass with |dy| >= 30 m"]
    switch = switches[0]
    assert switch.recipient_id is not None
    reception = _arrival(switch)
    failures = ctx.identity("switcher", switch.player_id) + ctx.identity("receiver", switch.recipient_id)
    failures += ctx.identity("closer", nearest_opponent(ctx.tracks, switch.recipient_id, reception))
    distance = nearest_opponent_distance(ctx.tracks, switch.recipient_id, reception)
    if not distance <= 3.5:
        failures.append(f"receiver's nearest opponent {distance:.2f} m > 3.5 at reception")
    tackles = [
        e
        for e in ctx.events
        if e.event_type == "tackle"
        and e.team_id == ctx.opp
        and e.outcome == "won"
        and 0 <= e.session_clock_ms - reception <= 2000
    ]
    if not tackles:
        failures.append("no opponent tackle won within 2000 ms of reception")
    else:
        failures += ctx.identity("closer", tackles[0].player_id)
    pressure = _pressure_on(ctx.tracks, switch.recipient_id, reception)
    if not pressure < 30.0:
        failures.append(f"pressure on receiver at reception {pressure:.1f} >= 30")
    return failures


IntentCheck = Callable[[Any, Window], list[str]]


def _strip(record: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k != "match_id"}


def check_tracking_gap(output: Any, label_window: Window) -> list[str]:
    failures: list[str] = []
    gaps = output.manifest.tracking_gaps
    if not gaps:
        return ["manifest lists no tracking gap"]
    hidden: dict[str, tuple[int, int]] = {pid: (g.start_ms, g.end_ms) for g in gaps for pid in g.player_ids}
    for frame in output.frames:
        for p in frame.players:
            window = hidden.get(p.player_id)
            if window and window[0] <= frame.session_clock_ms <= window[1] and (p.visible or p.pos_m):
                failures.append(f"{p.player_id} visible in {frame.frame_id} inside the gap")
        if any(not p.visible and p.pos_m is not None for p in frame.players):
            failures.append(f"fabricated position in {frame.frame_id}")
    cfg = output.config
    ref = simulate(SimulationConfig(cfg.seed, "space_creation", cfg.variant, cfg.split))
    if [_strip(e.model_dump(mode="json")) for e in output.events] != [
        _strip(e.model_dump(mode="json")) for e in ref.events
    ]:
        failures.append("events differ from space_creation")
    for got, want in zip(output.frames, ref.frames, strict=True):
        a, b = _strip(got.model_dump(mode="json")), _strip(want.model_dump(mode="json"))
        t = got.session_clock_ms
        for side in (a, b):
            side["players"] = [
                p
                for p in side["players"]
                if not (
                    p["player_id"] in hidden and hidden[p["player_id"]][0] <= t <= hidden[p["player_id"]][1]
                )
            ]
        if a != b:
            failures.append(f"{got.frame_id} differs from space_creation outside the gap")
            break
    return failures[:5]


LIBRARY: Mapping[str, IntentCheck] = {
    "space_creation": check_space_creation,
    "press_turnover": check_press_turnover,
    "switch_escape": check_switch_escape,
}
"""Every implemented scenario family and its intent check (the T047 library matrix)."""
