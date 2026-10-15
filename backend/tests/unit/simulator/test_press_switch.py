import pytest
from simulator.intent import check_press_turnover, check_switch_escape, relabel

from tactistream.simulator.config import SimulationConfig
from tactistream.simulator.engine import SimulationOutput, simulate
from tactistream.simulator.validate import validate_output

CHECKS = {"press_turnover": check_press_turnover, "switch_escape": check_switch_escape}


def _window(output: SimulationOutput) -> tuple[int, int]:
    segment = output.manifest.segments[0]
    return (segment.start_ms, segment.end_ms)


@pytest.mark.parametrize("variant", ["A", "B", "C"])
@pytest.mark.parametrize("scenario", sorted(CHECKS))
def test_dev_seeds_are_valid_and_intended(scenario: str, variant: str) -> None:
    failures = []
    for seed in range(1, 21):
        out = simulate(SimulationConfig(seed, scenario, variant))  # type: ignore[arg-type]
        problems = [i.line() for i in validate_output(out).issues] + CHECKS[scenario](out, _window(out))
        if problems:
            failures.append((seed, problems[:3]))
    assert failures == []


def test_press_turnover_hero_seed() -> None:
    out = simulate(SimulationConfig(42, "press_turnover"))
    interception = next(e for e in out.events if e.event_type == "interception")
    assert (interception.player_id, interception.outcome) == ("blue-10", "won")
    pressures = [
        e
        for e in out.events
        if e.event_type == "pressure"
        and e.team_id == "blue"
        and e.session_clock_ms < interception.session_clock_ms
    ]
    assert [e.player_id for e in pressures] == ["blue-09", "blue-11"]
    (label,) = out.manifest.segments
    assert (label.positive, label.expected_pattern, label.negative_of) == (True, "press_turnover", None)
    assert label.key_players["victim"] == "amber-05"
    assert label.key_players["interceptor"] == "blue-10"
    assert label.key_event_ids["turnover"] == interception.event_id


def test_switch_escape_hero_seed() -> None:
    out = simulate(SimulationConfig(42, "switch_escape"))
    switches = [
        e
        for e in out.events
        if e.event_type == "pass"
        and e.outcome == "complete"
        and e.end_m is not None
        and abs(e.end_m[1] - e.start_m[1]) >= 34.0
    ]
    assert len(switches) == 1
    switch = switches[0]
    assert (switch.player_id, switch.recipient_id) == ("blue-08", "blue-07")
    t0, t1 = switch.session_clock_ms, switch.session_clock_ms + (switch.duration_ms or 0)
    heights = [f.ball.height_m or 0.0 for f in out.frames if t0 <= f.session_clock_ms <= t1]
    assert 5.5 <= max(heights) <= 6.5
    (label,) = out.manifest.segments
    assert (label.positive, label.expected_pattern, label.negative_of) == (True, "switch_escape", None)
    assert label.key_event_ids["switch"] == switch.event_id


@pytest.mark.parametrize(
    ("scenario", "role", "wrong"),
    [
        ("press_turnover", "victim", "amber-02"),
        ("press_turnover", "interceptor", "blue-06"),
        ("switch_escape", "switcher", "blue-06"),
        ("switch_escape", "receiver", "blue-02"),
    ],
)
def test_intent_check_confirms_manifest_key_players(scenario: str, role: str, wrong: str) -> None:
    out = simulate(SimulationConfig(42, scenario))  # type: ignore[arg-type]
    failures = CHECKS[scenario](relabel(out, **{role: wrong}), _window(out))
    assert any(role in f for f in failures), failures
