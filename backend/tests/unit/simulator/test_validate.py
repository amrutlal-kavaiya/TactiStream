from collections.abc import Callable

import pytest

from tactistream.contracts import FeedEnvelope, PlayerPosition
from tactistream.simulator.validate import ValidationReport, validate_envelopes, validate_output
from unit.simulator.factories import Records, make_output, rebuild_frames


def codes(report: ValidationReport) -> list[str]:
    return [issue.code for issue in report.issues]


def test_factory_output_is_valid() -> None:
    report = validate_output(make_output())
    assert report.issues == ()
    assert report.ok
    assert report.unchecked == 0


def _jump(r: Records) -> Records:
    for k in range(10, 21):
        x, y = r.positions["blue-02"][k]  # type: ignore[misc]
        r.positions["blue-02"][k] = (x + 1.2, y)
    return rebuild_frames(r)


def _accelerate(r: Records) -> Records:
    x0, y0 = r.positions["blue-03"][0]  # type: ignore[misc]
    for k in range(9, 21):
        r.positions["blue-03"][k] = (x0 + 0.35 + 0.7 * (k - 9), y0)
    return rebuild_frames(r)


def _detach_ball(r: Records) -> Records:
    x, y = r.ball[9]  # type: ignore[misc]
    r.ball[9] = (x + 0.5, y)
    return rebuild_frames(r)


def _carry_start_off(r: Records) -> Records:
    carry = r.events[1]
    r.events[1] = carry.model_copy(update={"start_m": (carry.start_m[0], carry.start_m[1] + 1.5)})
    return r


def _carry_by_opponent(r: Records) -> Records:
    r.events[1] = r.events[1].model_copy(update={"player_id": "amber-08", "team_id": "amber"})
    return r


def _drop_frame(r: Records) -> Records:
    del r.frames[7]
    return r


def _drop_player(r: Records) -> Records:
    frame = r.frames[5]
    r.frames[5] = frame.model_copy(
        update={"players": [p for p in frame.players if p.player_id != "amber-06"]}
    )
    return r


def _backward_shot(r: Records) -> Records:
    passed = r.events[2]
    r.events[2] = passed.model_copy(
        update={"event_type": "shot", "recipient_id": None, "end_m": (30.0, 32.0), "outcome": "blocked"}
    )
    return r


def _reappear_far(r: Records) -> Records:
    x, y = r.positions["blue-02"][0]  # type: ignore[misc]
    for k in range(6, 15):
        r.positions["blue-02"][k] = None
    for k in range(15, 21):
        r.positions["blue-02"][k] = (x + 12.0, y)
    return rebuild_frames(r)


def _fabricated_position(r: Records) -> Records:
    frame = r.frames[3]
    bad = PlayerPosition.model_construct(player_id="blue-02", visible=False, pos_m=(28.0, 10.0))
    players = [bad if p.player_id == "blue-02" else p for p in frame.players]
    r.frames[3] = frame.model_copy(update={"players": players})
    return r


MUTATIONS: list[tuple[str, Callable[[Records], Records], str]] = [
    ("jump", _jump, "speed_exceeded"),
    ("accelerate", _accelerate, "accel_exceeded"),
    ("detach_ball", _detach_ball, "ball_detached"),
    ("carry_start_off", _carry_start_off, "event_coord_mismatch"),
    ("carry_by_opponent", _carry_by_opponent, "illegal_transition"),
    ("drop_frame", _drop_frame, "frame_gap"),
    ("drop_player", _drop_player, "roster_incomplete"),
    ("backward_shot", _backward_shot, "attack_direction_inconsistent"),
    ("reappear_far", _reappear_far, "speed_exceeded"),
    ("fabricated_position", _fabricated_position, "schema_invalid"),
]


@pytest.mark.parametrize(("mutate", "code"), [m[1:] for m in MUTATIONS], ids=[m[0] for m in MUTATIONS])
def test_single_mutation_yields_one_issue(mutate: Callable[[Records], Records], code: str) -> None:
    report = validate_output(mutate(make_output()))
    assert codes(report) == [code], report.issues
    assert not report.ok


def test_fast_pass_is_flagged() -> None:
    report = validate_output(make_output(pass_speed_mps=30.0))
    assert codes(report) == ["pass_ball_speed"]
    assert report.issues[0].record_id == "evt-0003"


def test_invisible_actor_at_event_is_unchecked() -> None:
    r = make_output()
    r.positions["blue-08"][12] = None
    report = validate_output(rebuild_frames(r))
    assert report.issues == ()
    assert report.unchecked == 1


def test_issue_lines_name_the_record() -> None:
    report = validate_output(_carry_start_off(make_output()))
    assert report.issues[0].record_id == "evt-0002"
    assert report.issues[0].line().startswith("event_coord_mismatch evt-0002 ")


def _envelopes(r: Records) -> list[FeedEnvelope]:
    base = 1_792_000_000_000
    out = [
        FeedEnvelope(
            schema_version="1.0",
            kind="metadata",
            match_id=r.metadata.match_id,
            record_id=r.metadata.match_id,
            published_ms=base,
            payload=r.metadata,
        )
    ]
    for e in r.events:
        out.append(
            FeedEnvelope(
                schema_version="1.0",
                kind="event",
                match_id=e.match_id,
                record_id=e.event_id,
                published_ms=base + e.session_clock_ms,
                payload=e,
            )
        )
    for f in r.frames:
        out.append(
            FeedEnvelope(
                schema_version="1.0",
                kind="frame",
                match_id=f.match_id,
                record_id=f.frame_id,
                published_ms=base + f.session_clock_ms,
                payload=f,
            )
        )
    return out


def test_validate_envelopes_runs_the_same_checks() -> None:
    assert validate_envelopes(_envelopes(make_output())).ok
    assert codes(validate_envelopes(_envelopes(_detach_ball(make_output())))) == ["ball_detached"]


def test_validate_envelopes_requires_metadata_first() -> None:
    envelopes = _envelopes(make_output())
    report = validate_envelopes(envelopes[1:])
    assert codes(report) == ["schema_invalid"]
