from typing import Any

import pytest

from tactistream.contracts import MatchEvent
from tactistream.simulator.possession import (
    LEGAL_TRANSITIONS,
    IllegalTransition,
    Phase,
    PossessionState,
    check_sequence,
    is_turnover,
    transition,
)

START = PossessionState(Phase.DEAD, None, None, None)
BLUE_08 = PossessionState(Phase.CONTROLLED, "blue", "blue-08", None)
BLUE_LOOSE = PossessionState(Phase.LOOSE, "blue", "blue-08", None)
RESTART_BLUE = PossessionState(Phase.DEAD, "amber", "amber-04", "blue")
ENDED = PossessionState(Phase.ENDED, "blue", "blue-08", None)
_seq = iter(range(1, 10_000))


def ev(event_type: str, player: str, **fields: Any) -> MatchEvent:
    sequence = fields.pop("sequence", None) or next(_seq)
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "match_id": "demo-blue-amber-001",
        "event_id": f"evt-{sequence:04d}",
        "sequence": sequence,
        "period": 1,
        "period_clock_ms": 840000,
        "session_clock_ms": 0,
        "event_type": event_type,
        "team_id": player.split("-")[0],
        "player_id": player,
        "start_m": (60.0, 30.0),
        "outcome": None,
        "source": {"kind": "synthetic", "generator_version": "0.1.0", "seed": 42},
    }
    if event_type in ("pass", "kickoff", "carry", "shot"):
        data["end_m"] = (70.0, 30.0)
        data["duration_ms"] = 800
    data.update(fields)
    return MatchEvent.model_validate(data)


LEGAL_CASES = [
    (
        "dead_kickoff",
        START,
        ev("kickoff", "blue-10", start_m=(52.5, 34.0), recipient_id="blue-08"),
        PossessionState(Phase.CONTROLLED, "blue", "blue-08", None),
    ),
    (
        "dead_restart_pass_complete",
        RESTART_BLUE,
        ev("pass", "blue-04", recipient_id="blue-05", outcome="complete"),
        PossessionState(Phase.CONTROLLED, "blue", "blue-05", None),
    ),
    (
        "dead_restart_pass_incomplete",
        RESTART_BLUE,
        ev("pass", "blue-04", outcome="incomplete"),
        PossessionState(Phase.LOOSE, "blue", "blue-04", None),
    ),
    (
        "dead_period_end",
        RESTART_BLUE,
        ev("period_end", "amber-04"),
        PossessionState(Phase.ENDED, "amber", "amber-04", None),
    ),
    ("controlled_carry", BLUE_08, ev("carry", "blue-08"), BLUE_08),
    (
        "controlled_pass_complete",
        BLUE_08,
        ev("pass", "blue-08", recipient_id="blue-11", outcome="complete"),
        PossessionState(Phase.CONTROLLED, "blue", "blue-11", None),
    ),
    ("controlled_pass_incomplete", BLUE_08, ev("pass", "blue-08", outcome="incomplete"), BLUE_LOOSE),
    ("controlled_shot_on_target", BLUE_08, ev("shot", "blue-08", outcome="on_target"), BLUE_LOOSE),
    ("controlled_shot_off_target", BLUE_08, ev("shot", "blue-08", outcome="off_target"), BLUE_LOOSE),
    ("controlled_shot_blocked", BLUE_08, ev("shot", "blue-08", outcome="blocked"), BLUE_LOOSE),
    ("controlled_clearance", BLUE_08, ev("clearance", "blue-08"), BLUE_LOOSE),
    (
        "controlled_pressure",
        BLUE_08,
        ev("pressure", "amber-06", start_m=(62.0, 30.0), end_m=(60.0, 30.0)),
        BLUE_08,
    ),
    (
        "controlled_tackle_won",
        BLUE_08,
        ev("tackle", "amber-06", start_m=(61.0, 30.0), end_m=(60.0, 30.0), outcome="won"),
        PossessionState(Phase.CONTROLLED, "amber", "amber-06", None),
    ),
    (
        "controlled_tackle_lost",
        BLUE_08,
        ev("tackle", "amber-06", start_m=(61.0, 30.0), end_m=(60.0, 30.0), outcome="lost"),
        BLUE_08,
    ),
    (
        "controlled_out_of_play",
        BLUE_08,
        ev("out_of_play", "blue-08"),
        PossessionState(Phase.DEAD, "blue", "blue-08", "amber"),
    ),
    (
        "controlled_period_end",
        BLUE_08,
        ev("period_end", "blue-08"),
        PossessionState(Phase.ENDED, "blue", "blue-08", None),
    ),
    (
        "loose_interception",
        BLUE_LOOSE,
        ev("interception", "amber-05", outcome="won"),
        PossessionState(Phase.CONTROLLED, "amber", "amber-05", None),
    ),
    (
        "loose_recovery_same_team",
        BLUE_LOOSE,
        ev("ball_recovery", "blue-09"),
        PossessionState(Phase.CONTROLLED, "blue", "blue-09", None),
    ),
    (
        "loose_recovery_opponent",
        BLUE_LOOSE,
        ev("ball_recovery", "amber-03"),
        PossessionState(Phase.CONTROLLED, "amber", "amber-03", None),
    ),
    (
        "loose_out_of_play",
        BLUE_LOOSE,
        ev("out_of_play", "amber-01"),
        PossessionState(Phase.DEAD, "amber", "amber-01", "blue"),
    ),
]


@pytest.mark.parametrize(
    ("state", "event", "expected"), [c[1:] for c in LEGAL_CASES], ids=[c[0] for c in LEGAL_CASES]
)
def test_legal_transitions(state: PossessionState, event: MatchEvent, expected: PossessionState) -> None:
    assert transition(state, event) == expected


def test_every_table_row_is_covered() -> None:
    covered = {(case[1].phase, case[2].event_type) for case in LEGAL_CASES}
    assert covered == set(LEGAL_TRANSITIONS)


ILLEGAL_CASES = [
    ("carry_not_in_control", BLUE_08, ev("carry", "blue-11")),
    ("interception_by_last_touch_team", BLUE_LOOSE, ev("interception", "blue-09", outcome="won")),
    (
        "pressure_by_possessing_team",
        BLUE_08,
        ev("pressure", "blue-06", start_m=(61.0, 30.0), end_m=(60.0, 30.0)),
    ),
    ("pressure_from_4m", BLUE_08, ev("pressure", "amber-06", start_m=(64.0, 30.0), end_m=(60.0, 30.0))),
    (
        "tackle_from_2m",
        BLUE_08,
        ev("tackle", "amber-06", start_m=(62.0, 30.0), end_m=(60.0, 30.0), outcome="won"),
    ),
    ("after_period_end", ENDED, ev("kickoff", "blue-10", start_m=(52.5, 34.0), recipient_id="blue-08")),
    ("period_end_after_period_end", ENDED, ev("period_end", "blue-08")),
    ("kickoff_off_centre", START, ev("kickoff", "blue-10", start_m=(50.0, 34.0), recipient_id="blue-08")),
    ("kickoff_to_opponent", START, ev("kickoff", "blue-10", start_m=(52.5, 34.0), recipient_id="amber-08")),
    (
        "restart_by_team_that_put_ball_out",
        RESTART_BLUE,
        ev("pass", "amber-04", recipient_id="amber-05", outcome="complete"),
    ),
    (
        "kickoff_on_restart",
        RESTART_BLUE,
        ev("kickoff", "blue-10", start_m=(52.5, 34.0), recipient_id="blue-08"),
    ),
    ("pass_to_opponent", BLUE_08, ev("pass", "blue-08", recipient_id="amber-04", outcome="complete")),
    ("shot_bad_outcome", BLUE_08, ev("shot", "blue-08", outcome="won")),
    ("interception_while_controlled", BLUE_08, ev("interception", "amber-05", outcome="won")),
]


@pytest.mark.parametrize(
    ("state", "event"), [c[1:] for c in ILLEGAL_CASES], ids=[c[0] for c in ILLEGAL_CASES]
)
def test_illegal_transitions(state: PossessionState, event: MatchEvent) -> None:
    with pytest.raises(IllegalTransition) as info:
        transition(state, event)
    assert info.value.event_id == event.event_id


def test_check_sequence_reports_first_illegal_event() -> None:
    kickoff = ev("kickoff", "blue-10", sequence=1, start_m=(52.5, 34.0), recipient_id="blue-08")
    shot = ev("shot", "blue-10", sequence=2, outcome="off_target")
    issues = check_sequence([kickoff, shot])
    assert len(issues) == 1
    assert (issues[0].code, issues[0].record_id) == ("illegal_transition", "evt-0002")


def test_check_sequence_skips_illegal_event_and_continues() -> None:
    kickoff = ev("kickoff", "blue-10", sequence=1, start_m=(52.5, 34.0), recipient_id="blue-08")
    bad = ev("carry", "amber-08", sequence=2)
    good = ev("carry", "blue-08", sequence=3)
    assert [i.record_id for i in check_sequence([kickoff, bad, good])] == ["evt-0002"]


def test_is_turnover() -> None:
    assert is_turnover(BLUE_LOOSE, ev("interception", "amber-05", outcome="won"))
    assert is_turnover(
        BLUE_08, ev("tackle", "amber-06", start_m=(61.0, 30.0), end_m=(60.0, 30.0), outcome="won")
    )
    assert not is_turnover(
        BLUE_08, ev("tackle", "amber-06", start_m=(61.0, 30.0), end_m=(60.0, 30.0), outcome="lost")
    )
    assert is_turnover(BLUE_LOOSE, ev("ball_recovery", "amber-03"))
    assert not is_turnover(BLUE_LOOSE, ev("ball_recovery", "blue-03"))
    assert not is_turnover(BLUE_08, ev("pass", "blue-08", recipient_id="blue-11", outcome="complete"))
