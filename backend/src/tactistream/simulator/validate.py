"""Plausibility validation of generated feeds (schema, kinematics, ball, events, possession, contiguity)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
from numpy.typing import NDArray
from pydantic import ValidationError as PydanticValidationError

from tactistream.contracts import (
    ContractError,
    FeedEnvelope,
    MatchEvent,
    MatchMetadata,
    TrackingFrame,
    validate,
)
from tactistream.simulator.issues import IssueCode, ValidationIssue
from tactistream.simulator.kinematics import (
    BALL_CARRY_MAX_DIST_M,
    FRAME_MS,
    MAX_PLAYER_ACCEL_MPS2,
    MAX_PLAYER_SPEED_MPS,
    PASS_SPEED_RANGE_MPS,
)
from tactistream.simulator.possession import IllegalTransition, Phase, PossessionState, transition

__all__ = ["IssueCode", "ValidationIssue", "ValidationReport", "validate_envelopes", "validate_output"]

SPEED_TOLERANCE_MPS = 0.15
ACCEL_TOLERANCE_MPS2 = 0.5
DISTANCE_TOLERANCE_M = 0.02
EVENT_COORD_MAX_M = 1.0
GOAL_LINE_MAX_M = 2.0
BOUNDS_MARGIN_M = 2.0
_UNCHECKED_COORD_EVENTS = ("out_of_play", "period_end")
_ARRIVING = ("kickoff", "pass")

Array = NDArray[np.float64]


class FeedRecords(Protocol):
    @property
    def metadata(self) -> MatchMetadata: ...
    @property
    def events(self) -> Sequence[MatchEvent]: ...
    @property
    def frames(self) -> Sequence[TrackingFrame]: ...


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]
    unchecked: int
    """Event-coordinate checks skipped because the actor was invisible at the event time."""

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass
class _Grid:
    """Positions on the 100 ms grid (NaN = invisible or frame missing)."""

    t0_ms: int
    frame_ids: list[str | None]
    players: dict[str, Array]
    ball: Array

    def index(self, t_ms: int) -> int | None:
        k = round((t_ms - self.t0_ms) / FRAME_MS)
        return k if 0 <= k < len(self.frame_ids) else None

    def frame_id(self, k: int) -> str:
        return self.frame_ids[k] or f"t={self.t0_ms + k * FRAME_MS}"

    def player_at(self, pid: str, t_ms: int) -> Array | None:
        k = self.index(t_ms)
        if k is None or pid not in self.players or math.isnan(self.players[pid][k, 0]):
            return None
        return np.asarray(self.players[pid][k], dtype=float)

    def ball_at(self, t_ms: int) -> Array | None:
        k = self.index(t_ms)
        if k is None or math.isnan(self.ball[k, 0]):
            return None
        return np.asarray(self.ball[k], dtype=float)


@dataclass
class _Collector:
    issues: list[ValidationIssue] = field(default_factory=list)
    seen: set[tuple[str, str]] = field(default_factory=set)
    unchecked: int = 0

    def add(self, code: IssueCode, record_id: str, detail: str, *, once_per: str | None = None) -> None:
        if once_per is not None:
            if (code, once_per) in self.seen:
                return
            self.seen.add((code, once_per))
        self.issues.append(ValidationIssue(code, record_id, detail))


def _dump(model: MatchMetadata | MatchEvent | TrackingFrame) -> object:
    return model.model_dump(mode="json", exclude_none=True)


def _check_schemas(
    out: _Collector, metadata: MatchMetadata, events: Sequence[MatchEvent], frames: Sequence[TrackingFrame]
) -> None:
    """JSON Schema for metadata, events and the boundary frames; every frame round-trips the contract model.

    The pydantic contract models mirror the schemas (including visible <=> pos_m) and are ~50x faster than
    jsonschema per frame, which keeps a 2,800-frame `demo_match` within its generation budget.
    """
    records: list[tuple[str, str, MatchMetadata | MatchEvent | TrackingFrame]] = [
        ("match_metadata.schema.json", metadata.match_id, metadata)
    ]
    records += [("event.schema.json", e.event_id, e) for e in events]
    records += [
        ("tracking_frame.schema.json", f.frame_id, f)
        for f in {id(f): f for f in [*frames[:1], *frames[-1:]]}.values()
    ]
    for schema, record_id, model in records:
        try:
            validate(schema, _dump(model))
        except ContractError as exc:
            out.add("schema_invalid", record_id, f"{exc.path}: {exc.message}")
    for frame in frames:
        try:
            TrackingFrame.model_validate(_dump(frame))
        except PydanticValidationError as exc:
            out.add("schema_invalid", frame.frame_id, str(exc.errors()[0]["msg"]), once_per=frame.frame_id)


def _check_structure(
    out: _Collector, metadata: MatchMetadata, events: Sequence[MatchEvent], frames: Sequence[TrackingFrame]
) -> None:
    periods = {p.period for p in metadata.periods}
    used = {e.period for e in events} | {f.period for f in frames}
    for period in sorted(used - periods):
        out.add("attack_direction_inconsistent", metadata.match_id, f"period {period} missing from metadata")
    previous_t = -1
    for expected, event in enumerate(events, start=1):
        if event.sequence != expected or event.event_id != f"evt-{expected:04d}":
            out.add("sequence_gap", event.event_id, f"sequence {event.sequence}, expected {expected}")
        if event.session_clock_ms < previous_t:
            out.add("sequence_gap", event.event_id, "session_clock_ms goes backwards")
        previous_t = event.session_clock_ms
    for expected, frame in enumerate(frames):
        t_expected = (frames[0].session_clock_ms if frames else 0) + expected * FRAME_MS
        if frame.frame_index != expected or frame.frame_id != f"frm-{frame.frame_index:06d}":
            out.add("frame_gap", frame.frame_id, f"frame_index {frame.frame_index}, expected {expected}")
            break
        if frame.session_clock_ms != t_expected:
            out.add("frame_gap", frame.frame_id, f"session_clock_ms {frame.session_clock_ms} != {t_expected}")
            break
    roster = [p.player_id for team in metadata.teams for p in team.players]
    for frame in frames:
        listed = [p.player_id for p in frame.players]
        if sorted(listed) != sorted(roster):
            missing = sorted(set(roster) - set(listed))
            extra = sorted(set(listed) - set(roster))
            out.add("roster_incomplete", frame.frame_id, f"missing {missing} extra {extra} or duplicates")


def _grid(metadata: MatchMetadata, frames: Sequence[TrackingFrame]) -> _Grid:
    t0 = frames[0].session_clock_ms if frames else 0
    n = (frames[-1].session_clock_ms - t0) // FRAME_MS + 1 if frames else 0
    ids = [p.player_id for team in metadata.teams for p in team.players]
    players = {pid: np.full((n, 2), np.nan) for pid in ids}
    ball = np.full((n, 2), np.nan)
    frame_ids: list[str | None] = [None] * n
    for frame in frames:
        k = (frame.session_clock_ms - t0) // FRAME_MS
        if not 0 <= k < n:
            continue
        frame_ids[k] = frame.frame_id
        for p in frame.players:
            if p.visible and p.pos_m is not None and p.player_id in players:
                players[p.player_id][k] = p.pos_m
        if frame.ball.visible and frame.ball.pos_m is not None:
            ball[k] = frame.ball.pos_m
    return _Grid(t0, frame_ids, players, ball)


def _check_kinematics(out: _Collector, grid: _Grid) -> None:
    dt = FRAME_MS / 1000.0
    max_speed = MAX_PLAYER_SPEED_MPS + SPEED_TOLERANCE_MPS
    max_accel = MAX_PLAYER_ACCEL_MPS2 + ACCEL_TOLERANCE_MPS2
    for pid, pos in grid.players.items():
        visible = np.flatnonzero(~np.isnan(pos[:, 0]))
        bad_step = np.zeros(len(pos), dtype=bool)
        steps = pos[visible[1:]] - pos[visible[:-1]]
        speeds = np.hypot(steps[:, 0], steps[:, 1]) / (np.diff(visible) * dt)
        for m in np.flatnonzero(speeds > max_speed):
            i, j = int(visible[m]), int(visible[m + 1])
            bad_step[i + 1 : j + 1] = True
            over = "one frame" if j == i + 1 else f"{(j - i) * FRAME_MS} ms gap (mean)"
            out.add(
                "speed_exceeded",
                grid.frame_id(j),
                f"{pid} {float(speeds[m]):.2f} m/s over {over} (max {max_speed:.2f})",
                once_per=pid,
            )
        if len(pos) < 5:
            continue
        second = pos[4:] - 2 * pos[2:-2] + pos[:-4]
        accel = np.hypot(second[:, 0], second[:, 1]) / (2 * dt) ** 2
        skipped = np.lib.stride_tricks.sliding_window_view(np.isnan(pos[:, 0]) | bad_step, 5).any(axis=1)
        hits = np.flatnonzero(~skipped & (np.nan_to_num(accel) > max_accel))
        if len(hits):
            k = int(hits[0]) + 2
            out.add(
                "accel_exceeded",
                grid.frame_id(k),
                f"{pid} {float(accel[k - 2]):.2f} m/s² over 200 ms (max {max_accel:.2f})",
            )
    entities = [*grid.players.items(), ("ball", grid.ball)]
    for name, pos in entities:
        with np.errstate(invalid="ignore"):
            outside = (
                (pos[:, 0] < -BOUNDS_MARGIN_M)
                | (pos[:, 0] > 105.0 + BOUNDS_MARGIN_M)
                | (pos[:, 1] < -BOUNDS_MARGIN_M)
                | (pos[:, 1] > 68.0 + BOUNDS_MARGIN_M)
            )
        hits = np.flatnonzero(outside)
        if len(hits):
            k = int(hits[0])
            out.add("out_of_bounds", grid.frame_id(k), f"{name} at {pos[k].round(2).tolist()}", once_per=name)


def _dist(a: Sequence[float] | Array, b: Sequence[float] | Array) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _check_event(out: _Collector, grid: _Grid, metadata: MatchMetadata, event: MatchEvent) -> None:
    t = event.session_clock_ms
    actor = grid.player_at(event.player_id, t)
    if event.event_type not in _UNCHECKED_COORD_EVENTS:
        if actor is None:
            out.unchecked += 1
        elif (d := _dist(event.start_m, actor)) > EVENT_COORD_MAX_M + DISTANCE_TOLERANCE_M:
            out.add("event_coord_mismatch", event.event_id, f"start_m {d:.2f} m from {event.player_id}")
    if event.event_type == "pass" and event.end_m is not None and event.duration_ms:
        speed = _dist(event.start_m, event.end_m) / (event.duration_ms / 1000.0)
        low, high = PASS_SPEED_RANGE_MPS
        if not low - 1e-6 <= speed <= high + 1e-6:
            out.add("pass_ball_speed", event.event_id, f"{speed:.2f} m/s outside {low}-{high}")
    if event.event_type == "pass":
        ball = grid.ball_at(t)
        if (
            actor is not None
            and ball is not None
            and _dist(ball, actor) > BALL_CARRY_MAX_DIST_M + DISTANCE_TOLERANCE_M
        ):
            out.add("pass_start_mismatch", event.event_id, f"ball {_dist(ball, actor):.2f} m from passer")
    if event.event_type in _ARRIVING and event.outcome in (None, "complete") and event.recipient_id:
        arrival = t + (event.duration_ms or 0)
        ball, recipient = grid.ball_at(arrival), grid.player_at(event.recipient_id, arrival)
        if ball is not None and recipient is not None:
            gap = _dist(ball, recipient)
            if gap > BALL_CARRY_MAX_DIST_M + DISTANCE_TOLERANCE_M:
                out.add("pass_end_mismatch", event.event_id, f"ball {gap:.2f} m from recipient at arrival")
    if event.event_type == "shot" and event.end_m is not None:
        spec = next((p for p in metadata.periods if p.period == event.period), None)
        if spec is not None:
            direction = spec.attack_direction.blue if event.team_id == "blue" else spec.attack_direction.amber
            goal_x = 105.0 if direction == 1 else 0.0
            if (event.end_m[0] - event.start_m[0]) * direction <= 0:
                out.add("attack_direction_inconsistent", event.event_id, f"shot away from goal x={goal_x:g}")
            elif (
                event.outcome in ("on_target", "off_target")
                and abs(event.end_m[0] - goal_x) > GOAL_LINE_MAX_M
            ):
                out.add(
                    "attack_direction_inconsistent", event.event_id, f"shot ends {event.end_m} off goal line"
                )


def _check_ball_control(out: _Collector, grid: _Grid, carrier: str, start_ms: int, end_ms: int) -> None:
    for t in range(start_ms + FRAME_MS, end_ms + 1, FRAME_MS):
        who = grid.player_at(carrier, t)
        if who is None:
            continue
        ball = grid.ball_at(t)
        k = grid.index(t)
        if k is None:
            continue
        if ball is None:
            out.add(
                "ball_detached",
                grid.frame_id(k),
                f"ball invisible while {carrier} controls it",
                once_per=carrier,
            )
        elif (d := _dist(ball, who)) > BALL_CARRY_MAX_DIST_M + DISTANCE_TOLERANCE_M:
            out.add(
                "ball_detached", grid.frame_id(k), f"ball {d:.2f} m from carrier {carrier}", once_per=carrier
            )


def _check_events(
    out: _Collector, grid: _Grid, metadata: MatchMetadata, events: Sequence[MatchEvent]
) -> None:
    state = PossessionState.start()
    carrier: str | None = None
    control_from = 0
    for event in events:
        try:
            nxt = transition(state, event)
        except IllegalTransition as exc:
            out.add("illegal_transition", event.event_id, exc.detail)
            continue
        _check_event(out, grid, metadata, event)
        t = event.session_clock_ms
        new_carrier = nxt.player_id if nxt.phase == Phase.CONTROLLED else None
        if carrier is not None and (new_carrier != carrier or event.event_type in _ARRIVING):
            _check_ball_control(out, grid, carrier, control_from, t)
            carrier = None
        if new_carrier is not None and carrier is None:
            carrier = new_carrier
            control_from = t + (event.duration_ms or 0) if event.event_type in _ARRIVING else t
        state = nxt
    if carrier is not None:
        _check_ball_control(
            out, grid, carrier, control_from, grid.t0_ms + (len(grid.frame_ids) - 1) * FRAME_MS
        )


def _validate(
    metadata: MatchMetadata,
    events: Sequence[MatchEvent],
    frames: Sequence[TrackingFrame],
    *,
    check_schemas: bool,
) -> ValidationReport:
    out = _Collector()
    if check_schemas:
        _check_schemas(out, metadata, events, frames)
    _check_structure(out, metadata, events, frames)
    grid = _grid(metadata, frames)
    _check_kinematics(out, grid)
    _check_events(out, grid, metadata, events)
    return ValidationReport(tuple(out.issues), out.unchecked)


def validate_output(output: FeedRecords) -> ValidationReport:
    return _validate(output.metadata, output.events, output.frames, check_schemas=True)


def validate_envelopes(envelopes: Sequence[FeedEnvelope]) -> ValidationReport:
    """The same checks, starting from a feed file's envelopes (metadata first)."""
    out = _Collector()
    for envelope in envelopes:
        try:
            validate("feed_envelope.schema.json", envelope.model_dump(mode="json", exclude_none=True))
        except ContractError as exc:
            out.add("schema_invalid", envelope.record_id, f"{exc.path}: {exc.message}")
    if not envelopes or not isinstance(envelopes[0].payload, MatchMetadata):
        out.add("schema_invalid", "feed", "first envelope must be match metadata")
        return ValidationReport(tuple(out.issues), 0)
    events = [e.payload for e in envelopes if isinstance(e.payload, MatchEvent)]
    frames = [e.payload for e in envelopes if isinstance(e.payload, TrackingFrame)]
    report = _validate(envelopes[0].payload, events, frames, check_schemas=False)
    return ValidationReport((*out.issues, *report.issues), report.unchecked)
