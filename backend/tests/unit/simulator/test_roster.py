import json
from pathlib import Path

from tactistream.contracts import validate
from tactistream.simulator.config import SimulationConfig
from tactistream.simulator.roster import FORMATION_433, PERIOD_1, PERIOD_2, PLAYER_IDS, build_metadata, slots

EXAMPLE = Path(__file__).parents[4] / "contracts" / "examples" / "match_metadata.json"


def test_hero_metadata_equals_contract_example() -> None:
    metadata = build_metadata(SimulationConfig(42, "space_creation"), periods=[PERIOD_1])
    dumped = metadata.model_dump(mode="json", exclude_none=True)
    assert dumped == json.loads(EXAMPLE.read_text(encoding="utf-8"))
    validate("match_metadata.schema.json", dumped)


def test_metadata_uses_config_seed_match_id_and_periods() -> None:
    config = SimulationConfig(10000, "space_creation", "D", "eval")
    metadata = build_metadata(config, periods=[PERIOD_1, PERIOD_2])
    assert metadata.match_id == config.match_id
    assert metadata.source.seed == 10000
    assert [(p.period, p.attack_direction.blue, p.attack_direction.amber) for p in metadata.periods] == [
        (1, 1, -1),
        (2, -1, 1),
    ]


def test_slots_follow_attack_direction() -> None:
    assert slots("blue", "in_possession", 1)["blue-01"] == (6.0, 34.0)
    assert slots("blue", "in_possession", -1)["blue-01"] == (99.0, 34.0)
    amber = slots("amber", "out_of_possession", -1)
    assert amber["amber-01"] == (99.0, 34.0)
    assert amber["amber-04"][0] == 105.0 - (FORMATION_433["out_of_possession"][4][0])


def test_each_team_has_eleven_slots_per_phase() -> None:
    for phase in FORMATION_433:
        for team in ("blue", "amber"):
            team_slots = slots(team, phase, 1)
            assert len(team_slots) == 11
            assert set(team_slots) == {p for p in PLAYER_IDS if p.startswith(team)}


def test_formation_lines() -> None:
    in_pos = FORMATION_433["in_possession"]
    assert in_pos[1] == (6.0, 34.0)
    assert {in_pos[n][0] for n in (2, 3, 4, 5)} == {32.0}
    assert {in_pos[n][0] for n in (6, 8, 10)} == {50.0}
    assert {in_pos[n][0] for n in (7, 9, 11)} == {64.0}
    out = FORMATION_433["out_of_possession"]
    assert all(out[n][0] == in_pos[n][0] - 10.0 for n in range(2, 12))
    kickoff = FORMATION_433["kickoff"]
    assert all(x < 52.5 for x, _ in kickoff.values())
