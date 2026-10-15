import pytest
from simulator.intent import check_space_creation, relabel

from tactistream.simulator.config import SimulationConfig
from tactistream.simulator.engine import simulate
from tactistream.simulator.validate import validate_output

HERO_TYPES = ["kickoff", "carry", "pass", "pass", "pass", "carry", "shot", "out_of_play", "period_end"]


def _window(output):  # type: ignore[no-untyped-def]
    segment = output.manifest.segments[0]
    return (segment.start_ms, segment.end_ms)


def test_hero_events_and_frames() -> None:
    out = simulate(SimulationConfig(42, "space_creation"))
    assert [e.event_type for e in out.events] == HERO_TYPES
    forward = out.events[4]
    assert forward.event_id == "evt-0005"
    assert (forward.outcome, forward.player_id, forward.recipient_id) == ("complete", "blue-08", "blue-11")
    shot = out.events[6]
    assert (shot.event_id, shot.player_id) == ("evt-0007", "blue-11")
    assert shot.outcome in ("on_target", "off_target", "blocked")
    assert len(out.frames) == out.manifest.duration_ms // 100 + 1
    ids = {f"{team}-{n:02d}" for team in ("blue", "amber") for n in range(1, 12)}
    assert all({p.player_id for p in frame.players} == ids for frame in out.frames)
    report = validate_output(out)
    assert report.ok, [i.line() for i in report.issues]
    assert check_space_creation(out, _window(out)) == []


@pytest.mark.parametrize("role", ["runner", "follower", "passer", "receiver"])
def test_intent_check_confirms_manifest_key_players(role: str) -> None:
    out = simulate(SimulationConfig(42, "space_creation"))
    wrong = relabel(out, **{role: "blue-07" if role != "follower" else "amber-02"})
    failures = check_space_creation(wrong, _window(out))
    assert any(role in f for f in failures), failures


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_dev_seeds_are_valid_and_intended(variant: str) -> None:
    failures = []
    for seed in range(1, 21):
        out = simulate(SimulationConfig(seed, "space_creation", variant))  # type: ignore[arg-type]
        report = validate_output(out)
        problems = [i.line() for i in report.issues] + check_space_creation(out, _window(out))
        if problems:
            failures.append((seed, problems[:3]))
    assert failures == []
