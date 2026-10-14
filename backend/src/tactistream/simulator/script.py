"""Segment builder: beats -> legal events, keyframes -> bounded tracks, scene transform and seed jitter.

Families write nominal coordinates in the frame "focus team attacks +x, not mirrored" and nominal times
relative to the segment start. The builder scales times by the variant's tempo, applies the scene transform,
jitters keyframes (±0.5 m per axis) and beats (±200 ms on the 100 ms grid, order and >= 300 ms gaps kept, each
interval stretched by at most 15 %), runs every beat through the possession state machine, and turns keyframes
into spline tracks. Everyone without keyframes follows formation slots shifted with the ball.

Zero-tangent splines turn a keyframe offset d over an interval T into ~6 d / T² of acceleration, so jittered
keyframes need intervals of roughly 2 s or more to stay under 6 m/s².
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from tactistream.contracts import EventType, MatchEvent, Outcome, TeamId
from tactistream.simulator.config import GENERATOR_VERSION, VariantSpec
from tactistream.simulator.kinematics import (
    FRAME_MS,
    LOFT_MIN_DY_M,
    LOFT_PEAK_HEIGHT_M,
    BallPhase,
    Keyframe,
    ball_track,
    carry_offsets,
    check_bounds,
    follow_track,
    spline_track,
)
from tactistream.simulator.manifest import TrackingGap
from tactistream.simulator.possession import Phase, PossessionState, transition
from tactistream.simulator.roster import (
    CENTRE_SPOT,
    FORMATION_433,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    PLAYER_IDS,
    attack_dir,
    opponent,
    player_id,
    shirt_of,
    slots,
    team_of,
    to_actual,
)

Point = tuple[float, float]
Track = NDArray[np.float64]
PositionAt = Callable[[str, int], Point]

KEYFRAME_JITTER_M = 0.5
BEAT_JITTER_STEPS_MS = (-200, -100, 0, 100, 200)
BEAT_MIN_GAP_MS = 300
BEAT_MAX_STRETCH = 0.15
FOLLOWER_MAX_SPEED_MPS = 7.0
FOLLOWER_MAX_ACCEL_MPS2 = 3.0
FOLLOWER_RESPONSE_S = 1.0
BLOCK_SHIFT = (0.35, 0.25)
GK_SHIFT = (0.08, 0.1)
BALL_REFERENCE_SMOOTHING_S = 1.5
OU_SIGMA_M = 0.3
OU_THETA_PER_S = 0.5
TARGET_MARGIN_M = 2.0
SHOT_END_OFFSET_M = 0.4
_PLACEHOLDER_MATCH_ID = "sim-0000000000"
_ON_BALL_ACTORS = ("kickoff", "pass", "carry", "shot", "clearance", "interception", "ball_recovery", "tackle")


@dataclass(frozen=True, slots=True)
class Kickoff:
    """Segment starts with a kickoff by `team` at the segment start time."""

    team: TeamId


@dataclass(frozen=True, slots=True)
class Restart:
    """Segment starts with a restart pass by `team`; the ball is placed at `spot` (stadium coordinates)."""

    team: TeamId
    spot: Point


@dataclass(frozen=True, slots=True)
class SceneTransform:
    rotate: bool
    mirror_y: bool

    @classmethod
    def for_variant(cls, spec: VariantSpec) -> SceneTransform:
        return cls(rotate=spec.focus_attack_dir == -1, mirror_y=spec.y_mirror)

    def point(self, p: Point) -> Point:
        x, y = p
        if self.rotate:
            x, y = PITCH_LENGTH_M - x, PITCH_WIDTH_M - y
        if self.mirror_y:
            y = PITCH_WIDTH_M - y
        return (x, y)


@dataclass(frozen=True, slots=True)
class EventDraft:
    """An event with stadium coordinates and absolute session time, before match id and sequence numbers."""

    t_ms: int
    event_type: EventType
    team_id: TeamId
    player_id: str
    start_m: Point
    end_m: Point | None = None
    recipient_id: str | None = None
    duration_ms: int | None = None
    outcome: Outcome = None


@dataclass(frozen=True)
class LabelDraft:
    scenario: str
    positive: bool
    expected_pattern: str | None
    negative_of: str | None
    key_players: Mapping[str, str]
    key_beats: Mapping[str, int]
    intended_explanation: str


@dataclass(frozen=True)
class SegmentResult:
    t0_ms: int
    end_ms: int
    period: int
    events: tuple[EventDraft, ...]
    tracks: Mapping[str, Track]
    """Every roster player, (n, 2) on the 100 ms grid from `t0_ms` to `end_ms`."""
    visible: Mapping[str, NDArray[np.bool_]]
    ball: Track
    """(n, 3) x, y, height; NaN rows while the ball is invisible."""
    ball_phases: tuple[BallPhase, ...]
    gaps: tuple[TrackingGap, ...]
    label: LabelDraft | None
    end_positions: Mapping[str, Point]
    end_state: PossessionState
    keyframes: Mapping[str, tuple[Keyframe, ...]]


@dataclass
class _Beat:
    t_nominal: int
    t_final: int
    event_type: EventType
    actor: str
    recipient: str | None
    arrival_nominal: int | None
    outcome: Outcome
    end: Point | None
    end_player: str | None
    ball_to: Point | None
    state_before: PossessionState
    state_after: PossessionState


@dataclass
class _Keys:
    times: list[int] = field(default_factory=list)
    nominal: list[Point] = field(default_factory=list)
    final: list[Point] = field(default_factory=list)


def _round_ms(t: float) -> int:
    return math.floor(t / FRAME_MS + 0.5) * FRAME_MS


class SegmentBuilder:
    def __init__(
        self,
        rng: np.random.Generator,
        spec: VariantSpec,
        start: Kickoff | Restart,
        t0_ms: int = 0,
        *,
        jitter: bool = True,
        start_positions: Mapping[str, Point] | None = None,
    ) -> None:
        self.rng = rng
        self.spec = spec
        self.start = start
        self.t0_ms = t0_ms
        self.jitter = jitter
        self.focus: TeamId = spec.focus_team
        self.opp: TeamId = opponent(spec.focus_team)
        self.period = spec.period
        self.transform = SceneTransform.for_variant(spec)
        self.start_positions = dict(start_positions or {})
        self._keys: dict[str, _Keys] = {}
        self._targets: dict[str, list[tuple[int, Point]]] = {}
        self._beats: list[_Beat] = []
        self._gaps: list[TrackingGap] = []
        self._label: LabelDraft | None = None
        initial = PossessionState.start()
        if isinstance(start, Restart):
            initial = PossessionState(Phase.DEAD, opponent(start.team), None, start.team)
        self._state = initial

    # ----- naming and time helpers -------------------------------------------------------------

    def fp(self, shirt: int) -> str:
        """Focus-team player id."""
        return player_id(self.focus, shirt)

    def op(self, shirt: int) -> str:
        """Opponent player id."""
        return player_id(self.opp, shirt)

    def scaled(self, t_ms: int) -> int:
        """Nominal segment time scaled by the variant's tempo, on the 100 ms grid."""
        return _round_ms(t_ms * self.spec.time_scale)

    def nominal_keyframes(self, pid: str) -> list[tuple[int, Point]]:
        keys = self._keys[pid]
        return list(zip(keys.times, keys.nominal, strict=True))

    # ----- script ---------------------------------------------------------------------------------

    def keyframes(self, pid: str, keys: Sequence[tuple[int, Point]], *, jitter: bool = True) -> None:
        """Scripted actor: the spline passes through every (jittered) keyframe."""
        store = self._keys.setdefault(pid, _Keys())
        for t, pos in keys:
            nominal = self.transform.point(pos)
            final = nominal
            if self.jitter and jitter:
                dx, dy = self.rng.uniform(-KEYFRAME_JITTER_M, KEYFRAME_JITTER_M, size=2)
                final = (nominal[0] + float(dx), nominal[1] + float(dy))
            store.times.append(round(t * self.spec.time_scale))
            store.nominal.append(nominal)
            store.final.append(final)

    def targets(self, pid: str, keys: Sequence[tuple[int, Point]]) -> None:
        """Follower override: chase these (interpolated) points instead of the formation slot."""
        self._targets[pid] = [(round(t * self.spec.time_scale), self.transform.point(p)) for t, p in keys]

    def beat(
        self,
        t_ms: int,
        event_type: EventType,
        actor: str,
        *,
        recipient: str | None = None,
        duration_ms: int | None = None,
        outcome: Outcome = None,
        end: Point | None = None,
        end_player: str | None = None,
        ball_to: Point | None = None,
    ) -> int:
        """Append an event; raises `IllegalTransition` at once if the state machine forbids it."""
        ts = self.scaled(t_ms)
        arrival = self.scaled(t_ms + duration_ms) if duration_ms is not None else None
        final = self.t0_ms + ts + self._beat_offset(ts)
        provisional = self._provisional(ts, event_type, actor, recipient, outcome, duration_ms)
        before = self._state
        after = transition(before, provisional)
        self._state = after
        self._beats.append(
            _Beat(
                ts,
                final,
                event_type,
                actor,
                recipient,
                arrival,
                outcome,
                self.transform.point(end) if end is not None else None,
                end_player,
                self.transform.point(ball_to) if ball_to is not None else None,
                before,
                after,
            )
        )
        return len(self._beats) - 1

    def gap(self, player_ids: Sequence[str], start_ms: int, end_ms: int) -> None:
        """Hide players (no position) for frames in [start_ms, end_ms] (absolute session times)."""
        self._gaps.append(TrackingGap(tuple(sorted(player_ids)), start_ms, end_ms))

    def label(
        self,
        *,
        scenario: str,
        positive: bool,
        expected_pattern: str | None,
        negative_of: str | None = None,
        key_players: Mapping[str, str] | None = None,
        key_beats: Mapping[str, int] | None = None,
        intended_explanation: str = "",
    ) -> None:
        self._label = LabelDraft(
            scenario,
            positive,
            expected_pattern,
            negative_of,
            dict(key_players or {}),
            dict(key_beats or {}),
            intended_explanation,
        )

    def time_of(self, beat_index: int) -> int:
        """Final (jittered) session time of a beat."""
        return self._beats[beat_index].t_final

    # ----- internals ---------------------------------------------------------------------------

    def _beat_offset(self, ts: int) -> int:
        if not self._beats or not self.jitter:
            return 0
        prev = self._beats[-1]
        prev_offset = prev.t_final - self.t0_ms - prev.t_nominal
        interval = ts - prev.t_nominal
        if interval < BEAT_MIN_GAP_MS:
            return prev_offset
        max_change = math.floor(BEAT_MAX_STRETCH * interval / FRAME_MS) * FRAME_MS
        candidates = [
            d
            for d in BEAT_JITTER_STEPS_MS
            if abs(d - prev_offset) <= max_change and ts + d >= prev.t_nominal + prev_offset + BEAT_MIN_GAP_MS
        ]
        return candidates[int(self.rng.integers(len(candidates)))]

    def _nominal_position(self, pid: str, ts: int) -> Point:
        keys = self._keys.get(pid)
        if keys is None or not keys.times:
            return CENTRE_SPOT
        xs = np.interp(ts, keys.times, [p[0] for p in keys.nominal])
        ys = np.interp(ts, keys.times, [p[1] for p in keys.nominal])
        return (float(xs), float(ys))

    def _provisional(
        self,
        ts: int,
        event_type: EventType,
        actor: str,
        recipient: str | None,
        outcome: Outcome,
        duration_ms: int | None,
    ) -> MatchEvent:
        start = self._nominal_position(actor, ts)
        end: Point | None = start
        if event_type == "kickoff":
            start = CENTRE_SPOT
        elif event_type in ("pressure", "tackle") and self._state.player_id is not None:
            end = self._nominal_position(self._state.player_id, ts)
        return MatchEvent.model_validate(
            {
                "schema_version": "1.0",
                "match_id": _PLACEHOLDER_MATCH_ID,
                "event_id": f"evt-{len(self._beats) + 1:04d}",
                "sequence": len(self._beats) + 1,
                "period": self.period,
                "period_clock_ms": 0,
                "session_clock_ms": 0,
                "event_type": event_type,
                "team_id": team_of(actor),
                "player_id": actor,
                "recipient_id": recipient,
                "start_m": start,
                "end_m": end,
                "duration_ms": duration_ms if duration_ms is not None else 0,
                "outcome": outcome,
                "source": {"kind": "synthetic", "generator_version": GENERATOR_VERSION, "seed": 0},
            }
        )

    def _warp(self, t_nominal: float) -> int:
        anchors = [(b.t_nominal, b.t_final - self.t0_ms) for b in self._beats]
        if not anchors:
            return round(t_nominal)
        xs = [a for a, _ in anchors]
        ys = [b for _, b in anchors]
        if t_nominal <= xs[0]:
            return round(t_nominal + ys[0] - xs[0])
        if t_nominal >= xs[-1]:
            return round(t_nominal + ys[-1] - xs[-1])
        return round(float(np.interp(t_nominal, xs, ys)))

    def _facing(self, pid: str) -> Point:
        return (float(attack_dir(team_of(pid), self.period)), 0.0)

    # ----- build ------------------------------------------------------------------------------

    def build(self) -> SegmentResult:
        if not self._beats:
            raise ValueError("a segment needs at least one beat")
        t0 = self.t0_ms
        end_ms = self._beats[-1].t_final
        n = (end_ms - t0) // FRAME_MS + 1
        grid = np.arange(t0, end_ms + 1, FRAME_MS, dtype=float)

        final_keys: dict[str, tuple[Keyframe, ...]] = {}
        tracks: dict[str, Track] = {}
        for pid, keys in self._keys.items():
            frames = tuple(
                Keyframe(t0 + self._warp(t), pos) for t, pos in zip(keys.times, keys.final, strict=True)
            )
            final_keys[pid] = frames
            tracks[pid] = spline_track(frames, grid)
            check_bounds(pid, tracks[pid], t0_ms=t0)

        for beat in self._beats:
            if beat.event_type in _ON_BALL_ACTORS and beat.actor not in tracks:
                raise ValueError(f"{beat.event_type} actor {beat.actor} needs keyframes")

        offsets = {pid: carry_offsets(track, self._facing(pid)) for pid, track in tracks.items()}

        def index(t: int) -> int:
            return (t - t0) // FRAME_MS

        def ball_with(pid: str, t: int) -> Point:
            k = index(t)
            x, y = tracks[pid][k] + offsets[pid][k]
            return (float(x), float(y))

        def position(pid: str, t: int) -> Point:
            x, y = tracks[pid][index(t)]
            return (float(x), float(y))

        events, phases = self._resolve(ball_with, position)
        ball_reference = ball_track(phases, tracks, t0_ms=t0)
        everyone = self._followers(tracks, ball_reference, n)
        ball = ball_track(phases, everyone, t0_ms=t0)

        visible = {pid: np.ones(n, dtype=bool) for pid in PLAYER_IDS}
        for gap in self._gaps:
            lo = max(0, math.ceil((gap.start_ms - t0) / FRAME_MS))
            hi = min(n - 1, (gap.end_ms - t0) // FRAME_MS)
            for pid in gap.player_ids:
                visible[pid][lo : hi + 1] = False

        return SegmentResult(
            t0_ms=t0,
            end_ms=end_ms,
            period=self.period,
            events=tuple(events),
            tracks=everyone,
            visible=visible,
            ball=ball,
            ball_phases=tuple(phases),
            gaps=tuple(self._gaps),
            label=self._label,
            end_positions={pid: (float(t[-1, 0]), float(t[-1, 1])) for pid, t in everyone.items()},
            end_state=self._state,
            keyframes=final_keys,
        )

    def _resolve(
        self, ball_with: PositionAt, position: PositionAt
    ) -> tuple[list[EventDraft], list[BallPhase]]:
        """Event coordinates from the tracks and the ball phases between events."""
        t0 = self.t0_ms
        phases: list[BallPhase] = []
        # Open phase: ("placed" | "dead" | "controlled" | "loose", start time, player or position).
        open_kind: Literal["placed", "dead", "controlled", "loose"]
        open_from = t0
        open_player: str | None = None
        open_pos: Point | None = None
        if isinstance(self.start, Restart):
            open_kind, open_pos = "dead", self.start.spot
        else:
            open_kind, open_pos = "placed", CENTRE_SPOT

        def close(t: int, ball_at_t: Point | None) -> None:
            if open_kind == "controlled":
                assert open_player is not None
                phases.append(
                    BallPhase(
                        "controlled", open_from, t, player_id=open_player, facing=self._facing(open_player)
                    )
                )
            elif open_kind == "loose":
                assert open_pos is not None
                phases.append(
                    BallPhase("flight", open_from, t, start_pos=open_pos, end_pos=ball_at_t or open_pos)
                )
            elif open_kind == "placed":
                phases.append(BallPhase("placed", open_from, t, start_pos=open_pos))
            else:
                phases.append(BallPhase("dead", open_from, t, end_pos=open_pos))

        events: list[EventDraft] = []
        for i, beat in enumerate(self._beats):
            t = beat.t_final
            kind = beat.event_type
            actor = beat.actor
            before = beat.state_before
            arrival = t0 + self._warp(beat.arrival_nominal) if beat.arrival_nominal is not None else None
            if arrival is not None:
                arrival = _round_ms(arrival - t0) + t0
            start: Point
            end: Point | None = None
            if kind == "kickoff":
                start = CENTRE_SPOT
            elif kind == "pass" and before.phase == Phase.DEAD:
                assert isinstance(self.start, Restart)
                start = self.start.spot
            elif kind in ("pressure", "tackle"):
                start = position(actor, t)
                assert before.player_id is not None
                end = position(before.player_id, t)
            elif kind == "out_of_play" and before.phase == Phase.LOOSE:
                assert open_pos is not None
                start = beat.ball_to or open_pos
            elif kind == "period_end":
                start = position(actor, t)
            else:
                start = ball_with(actor, t)

            if kind in ("kickoff", "pass"):
                assert arrival is not None
                if beat.outcome in (None, "complete"):
                    assert beat.recipient is not None
                    end = ball_with(beat.recipient, arrival)
                elif beat.end_player is not None:
                    end = ball_with(beat.end_player, arrival)
                else:
                    assert beat.end is not None
                    end = beat.end
            elif kind in ("shot", "clearance"):
                assert arrival is not None
                if beat.end_player is not None:
                    px, py = position(beat.end_player, arrival)
                    dx, dy = start[0] - px, start[1] - py
                    norm = math.hypot(dx, dy) or 1.0
                    end = (px + SHOT_END_OFFSET_M * dx / norm, py + SHOT_END_OFFSET_M * dy / norm)
                else:
                    assert beat.end is not None
                    end = beat.end
            elif kind == "carry":
                next_t = self._beats[i + 1].t_final if i + 1 < len(self._beats) else t
                arrival = next_t
                end = ball_with(actor, next_t)

            duration = arrival - t if arrival is not None else None
            events.append(
                EventDraft(
                    t_ms=t,
                    event_type=kind,
                    team_id=team_of(actor),
                    player_id=actor,
                    start_m=start,
                    end_m=end,
                    recipient_id=beat.recipient,
                    duration_ms=duration,
                    outcome=beat.outcome,
                )
            )

            # Ball phases.
            after = beat.state_after
            if kind in ("kickoff", "pass", "shot", "clearance"):
                assert arrival is not None and end is not None
                close(t, start)
                peak = (
                    LOFT_PEAK_HEIGHT_M if kind == "pass" and abs(end[1] - start[1]) >= LOFT_MIN_DY_M else 0.0
                )
                phases.append(
                    BallPhase("flight", t, arrival, start_pos=start, end_pos=end, peak_height_m=peak)
                )
                open_from = arrival
                if after.phase == Phase.CONTROLLED:
                    open_kind, open_player, open_pos = "controlled", after.player_id, None
                else:
                    open_kind, open_player, open_pos = "loose", None, end
            elif kind in ("interception", "ball_recovery") or (kind == "tackle" and beat.outcome == "won"):
                close(t, start)
                open_kind, open_from, open_player, open_pos = "controlled", t, actor, None
            elif kind == "out_of_play":
                close(t, start)
                open_kind, open_from, open_player, open_pos = "dead", t, None, None
            elif kind == "period_end":
                close(t, None)
                open_kind, open_from, open_player, open_pos = "dead", t, None, None
        if open_from < self._beats[-1].t_final or not phases:
            close(self._beats[-1].t_final, None)
        return events, phases

    def _possession_team(self, n: int) -> list[TeamId]:
        teams: list[TeamId] = []
        b = 0
        current: TeamId = self.start.team
        for k in range(n):
            t = self.t0_ms + k * FRAME_MS
            while b < len(self._beats) and self._beats[b].t_final <= t:
                team = self._beats[b].state_after.team_id
                if team is not None:
                    current = team
                b += 1
            teams.append(current)
        return teams

    def _followers(self, scripted: Mapping[str, Track], ball_reference: Track, n: int) -> dict[str, Track]:
        dt = FRAME_MS / 1000.0
        ref = np.empty((n, 2))
        last = np.array(CENTRE_SPOT)
        smooth = np.array(CENTRE_SPOT)
        alpha = dt / BALL_REFERENCE_SMOOTHING_S
        for k in range(n):
            if not math.isnan(ball_reference[k, 0]):
                last = ball_reference[k, :2]
            smooth = smooth + alpha * (last - smooth)
            ref[k] = smooth
        shift = np.column_stack(
            [BLOCK_SHIFT[0] * (ref[:, 0] - CENTRE_SPOT[0]), BLOCK_SHIFT[1] * (ref[:, 1] - CENTRE_SPOT[1])]
        )
        gk_shift = np.column_stack(
            [GK_SHIFT[0] * (ref[:, 0] - CENTRE_SPOT[0]), GK_SHIFT[1] * (ref[:, 1] - CENTRE_SPOT[1])]
        )
        possession = self._possession_team(n)
        times = np.arange(n) * FRAME_MS
        phi = math.exp(-OU_THETA_PER_S * dt)
        noise_scale = OU_SIGMA_M * math.sqrt(1.0 - phi * phi)

        everyone: dict[str, Track] = {}
        for pid in PLAYER_IDS:
            if pid in scripted:
                everyone[pid] = scripted[pid]
                continue
            team = team_of(pid)
            direction = attack_dir(team, self.period)
            if pid in self._targets:
                keys = self._targets[pid]
                ktimes = [self._warp(t) for t, _ in keys]
                targets = np.column_stack(
                    [
                        np.interp(times, ktimes, [p[0] for _, p in keys]),
                        np.interp(times, ktimes, [p[1] for _, p in keys]),
                    ]
                )
            else:
                shirt = shirt_of(pid)
                in_pos = np.array(to_actual(FORMATION_433["in_possession"][shirt], direction))
                out_pos = np.array(to_actual(FORMATION_433["out_of_possession"][shirt], direction))
                base = np.array([in_pos if possession[k] == team else out_pos for k in range(n)])
                targets = base + (gk_shift if shirt == 1 else shift)
            noise = self.rng.standard_normal((n, 2)) * noise_scale
            ou = np.zeros((n, 2))
            for k in range(1, n):
                ou[k] = phi * ou[k - 1] + noise[k]
            targets = targets + ou
            targets[:, 0] = np.clip(targets[:, 0], TARGET_MARGIN_M, PITCH_LENGTH_M - TARGET_MARGIN_M)
            targets[:, 1] = np.clip(targets[:, 1], TARGET_MARGIN_M, PITCH_WIDTH_M - TARGET_MARGIN_M)
            start = self.start_positions.get(pid)
            if start is None:
                start = slots(team, "kickoff", direction)[pid]
            everyone[pid] = follow_track(
                targets,
                start,
                (0.0, 0.0),
                FOLLOWER_MAX_SPEED_MPS,
                FOLLOWER_MAX_ACCEL_MPS2,
                response_s=FOLLOWER_RESPONSE_S,
            )
        return everyone
