"""Possession state machine: the legal-transition table every generated event sequence must follow."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from tactistream.contracts import EventType, MatchEvent, TeamId
from tactistream.simulator.issues import ValidationIssue
from tactistream.simulator.roster import CENTRE_SPOT, opponent, team_of

KICKOFF_SPOT_TOLERANCE_M = 0.5
PRESSURE_MAX_DIST_M = 3.0
TACKLE_MAX_DIST_M = 1.5


class Phase(StrEnum):
    DEAD = "dead"
    CONTROLLED = "controlled"
    IN_FLIGHT = "in_flight"
    LOOSE = "loose"
    ENDED = "ended"


@dataclass(frozen=True, slots=True)
class PossessionState:
    phase: Phase
    team_id: TeamId | None
    """Possessing team (CONTROLLED) or last-touch team (LOOSE, DEAD, ENDED)."""
    player_id: str | None
    restart_team: TeamId | None
    """Set in DEAD after `out_of_play`; `None` in DEAD means start of period (kickoff)."""
    deflected_by: TeamId | None = None
    """Set in LOOSE after a `blocked` or `on_target` shot: the defending team made the last touch (block,
    parry or save). Events never name that player, so last-touch is enforced at team level."""

    @classmethod
    def start(cls) -> PossessionState:
        return cls(Phase.DEAD, None, None, None)


ActorRule = Literal[
    "kickoff_team", "restart_team", "any", "controller", "opponent", "opponent_of_last_touch", "last_touch"
]


@dataclass(frozen=True, slots=True)
class TransitionRule:
    actor: ActorRule
    outcomes: frozenset[str | None]
    max_distance_m: float | None = None
    """Upper bound on |start_m - end_m| (actor to player in control) for pressure and tackle."""


def _rule(actor: ActorRule, *outcomes: str | None, max_distance_m: float | None = None) -> TransitionRule:
    return TransitionRule(actor, frozenset(outcomes), max_distance_m)


LEGAL_TRANSITIONS: Mapping[tuple[Phase, EventType], TransitionRule] = {
    (Phase.DEAD, "kickoff"): _rule("kickoff_team", None),
    (Phase.DEAD, "pass"): _rule("restart_team", "complete", "incomplete"),
    (Phase.DEAD, "period_end"): _rule("any", None),
    (Phase.CONTROLLED, "carry"): _rule("controller", None),
    (Phase.CONTROLLED, "pass"): _rule("controller", "complete", "incomplete"),
    (Phase.CONTROLLED, "shot"): _rule("controller", "on_target", "off_target", "blocked"),
    (Phase.CONTROLLED, "clearance"): _rule("controller", None),
    (Phase.CONTROLLED, "pressure"): _rule("opponent", None, max_distance_m=PRESSURE_MAX_DIST_M),
    (Phase.CONTROLLED, "tackle"): _rule("opponent", "won", "lost", max_distance_m=TACKLE_MAX_DIST_M),
    (Phase.CONTROLLED, "out_of_play"): _rule("controller", None),
    (Phase.CONTROLLED, "period_end"): _rule("controller", None),
    (Phase.LOOSE, "interception"): _rule("opponent_of_last_touch", "won"),
    (Phase.LOOSE, "ball_recovery"): _rule("any", None),
    (Phase.LOOSE, "out_of_play"): _rule("last_touch", None),
}


class IllegalTransition(ValueError):  # noqa: N818 - name fixed by the data model
    def __init__(self, event_id: str, detail: str) -> None:
        super().__init__(f"{event_id}: {detail}")
        self.event_id = event_id
        self.detail = detail


def _check_actor(rule: TransitionRule, state: PossessionState, event: MatchEvent) -> str | None:
    team, actor = event.team_id, event.player_id
    if team_of(actor) != team:
        return f"team_id {team} does not match player {actor}"
    if rule.actor == "kickoff_team":
        if state.restart_team is not None:
            return f"kickoff is not a restart after out_of_play (restart team {state.restart_team})"
        if math.dist(event.start_m, CENTRE_SPOT) > KICKOFF_SPOT_TOLERANCE_M:
            return f"kickoff at {list(event.start_m)} is not on the centre spot"
    elif rule.actor == "restart_team":
        if state.restart_team is None:
            return "a restart pass needs a preceding out_of_play"
        if team != state.restart_team:
            return f"restart belongs to {state.restart_team}, not {team}"
    elif rule.actor == "controller":
        if actor != state.player_id:
            return f"{actor} is not in control (controller {state.player_id})"
    elif rule.actor == "opponent":
        if team == state.team_id:
            return f"{actor} belongs to the possessing team"
    elif rule.actor == "opponent_of_last_touch" and team == state.team_id:
        return f"{actor} belongs to the last-touch team"
    elif rule.actor == "last_touch":
        if state.deflected_by is not None and team != state.deflected_by:
            return f"{actor} did not touch last ({state.deflected_by} deflected the shot)"
        if state.deflected_by is None and actor != state.player_id:
            return f"{actor} did not touch last (last touch {state.player_id})"
    if rule.max_distance_m is not None:
        if event.end_m is None:
            return f"{event.event_type} needs end_m (position of the player in control)"
        distance = math.dist(event.start_m, event.end_m)
        if distance > rule.max_distance_m:
            return f"{event.event_type} from {distance:.2f} m (max {rule.max_distance_m} m)"
    return None


def transition(state: PossessionState, event: MatchEvent) -> PossessionState:
    """Return the state after `event`, or raise `IllegalTransition` if the table does not allow it."""
    rule = LEGAL_TRANSITIONS.get((state.phase, event.event_type))
    if rule is None:
        raise IllegalTransition(event.event_id, f"{event.event_type} is not legal in phase {state.phase}")
    problem = _check_actor(rule, state, event)
    if problem is None and event.outcome not in rule.outcomes:
        problem = f"outcome {event.outcome!r} is not allowed for {event.event_type}"
    recipient = event.recipient_id
    needs_teammate = event.event_type in ("kickoff", "pass") and event.outcome in (None, "complete")
    if (
        problem is None
        and needs_teammate
        and (recipient is None or team_of(recipient) != event.team_id or recipient == event.player_id)
    ):
        problem = f"recipient {recipient} is not a teammate of {event.player_id}"
    if problem is not None:
        raise IllegalTransition(event.event_id, problem)

    team, actor = event.team_id, event.player_id
    kind = event.event_type
    if kind == "period_end":
        return PossessionState(Phase.ENDED, team, actor, None)
    if kind in ("kickoff", "pass"):
        if event.outcome == "incomplete":
            return PossessionState(Phase.LOOSE, team, actor, None)
        return PossessionState(Phase.CONTROLLED, team, recipient, None)
    if kind == "shot" and event.outcome in ("blocked", "on_target"):
        return PossessionState(Phase.LOOSE, team, actor, None, deflected_by=opponent(team))
    if kind in ("shot", "clearance"):
        return PossessionState(Phase.LOOSE, team, actor, None)
    if kind == "out_of_play":
        return PossessionState(Phase.DEAD, team, actor, opponent(team))
    if kind in ("interception", "ball_recovery") or (kind == "tackle" and event.outcome == "won"):
        return PossessionState(Phase.CONTROLLED, team, actor, None)
    return state


def is_turnover(prev_state: PossessionState, event: MatchEvent) -> bool:
    """Interception, won tackle, or ball recovery by the team that did not last possess."""
    if event.event_type == "interception" or (event.event_type == "tackle" and event.outcome == "won"):
        return True
    return event.event_type == "ball_recovery" and event.team_id != prev_state.team_id


def check_sequence(events: Sequence[MatchEvent]) -> list[ValidationIssue]:
    """Run the state machine over `events`; an illegal event is reported and skipped."""
    issues: list[ValidationIssue] = []
    state = PossessionState.start()
    for event in events:
        try:
            state = transition(state, event)
        except IllegalTransition as exc:
            issues.append(ValidationIssue("illegal_transition", event.event_id, exc.detail))
    return issues
