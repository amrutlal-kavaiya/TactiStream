import re

import pytest

from tactistream.simulator.config import (
    DEV_VARIANTS,
    EVAL_VARIANTS,
    HERO_MATCH_IDS,
    SEED_MAX,
    VARIANTS,
    ConfigError,
    SimulationConfig,
)


@pytest.mark.parametrize(
    ("kwargs", "code", "message"),
    [
        ({"seed": 10000}, "eval_seed_requires_eval_split", "seed 10000 is reserved for split=eval"),
        (
            {"seed": 42, "variant": "D"},
            "eval_variant_requires_eval_split",
            "variant D is reserved for split=eval",
        ),
        (
            {"seed": 42, "split": "eval", "variant": "D"},
            "dev_seed_in_eval_split",
            "split=eval requires seed >= 10000",
        ),
        (
            {"seed": 10000, "split": "eval", "variant": "A"},
            "invalid_variant",
            "split=eval requires variant D, E or F",
        ),
        ({"seed": 0}, "invalid_seed", "seed must be in 1..2147483647"),
        ({"seed": 2**31}, "invalid_seed", "seed must be in 1..2147483647"),
    ],
)
def test_configuration_rules(kwargs: dict[str, object], code: str, message: str) -> None:
    with pytest.raises(ConfigError) as info:
        SimulationConfig(scenario="space_creation", **kwargs)  # type: ignore[arg-type]
    assert info.value.code == code
    assert str(info.value) == message


def test_eval_seed_rule_wins_over_variant_rule() -> None:
    with pytest.raises(ConfigError) as info:
        SimulationConfig(42, "space_creation", split="eval")
    assert info.value.code == "dev_seed_in_eval_split"


def test_unknown_scenario_lists_valid_names() -> None:
    with pytest.raises(ConfigError) as info:
        SimulationConfig(42, "nope")  # type: ignore[arg-type]
    assert info.value.code == "invalid_scenario"
    assert "space_creation" in str(info.value)
    assert "demo_match" in str(info.value)


def test_seed_bounds_are_inclusive() -> None:
    SimulationConfig(1, "space_creation")
    SimulationConfig(9999, "space_creation")
    SimulationConfig(SEED_MAX, "space_creation", "D", "eval")


def test_hero_match_ids() -> None:
    assert SimulationConfig(42, "space_creation").match_id == "demo-blue-amber-001"
    assert SimulationConfig(42, "demo_match").match_id == "demo-blue-amber-002"
    assert HERO_MATCH_IDS[("space_creation", 42, "A", "dev")] == "demo-blue-amber-001"


def test_other_match_ids_are_opaque() -> None:
    match_id = SimulationConfig(43, "space_creation").match_id
    assert re.fullmatch(r"sim-[0-9a-f]{10}", match_id)
    assert "space" not in match_id
    assert "43" not in match_id
    assert (
        SimulationConfig(42, "space_creation", "B").match_id
        != SimulationConfig(42, "space_creation").match_id
    )


def test_canonical_json_is_stable() -> None:
    a = SimulationConfig(7, "space_creation", "B")
    b = SimulationConfig(7, "space_creation", "B")
    assert a.canonical_json() == b.canonical_json()
    assert a.canonical_json() == (
        '{"generator_version":"0.1.0","scenario":"space_creation","seed":7,"split":"dev","variant":"B"}'
    )


def test_variant_table() -> None:
    assert DEV_VARIANTS == ("A", "B", "C")
    assert EVAL_VARIANTS == ("D", "E", "F")
    d = VARIANTS["D"]
    assert (d.focus_team, d.period, d.y_mirror, d.build_up_passes, d.time_scale) == ("blue", 2, True, 4, 0.90)
    assert d.focus_attack_dir == -1
    a, b, c = VARIANTS["A"], VARIANTS["B"], VARIANTS["C"]
    assert (a.focus_team, a.period, a.y_mirror, a.key_actor_set, a.build_up_passes, a.time_scale) == (
        "blue",
        1,
        False,
        "primary",
        2,
        1.00,
    )
    assert (b.y_mirror, b.build_up_passes, b.key_actor_set) == (True, 3, "primary")
    assert (c.key_actor_set, c.build_up_passes, c.time_scale) == ("alternate", 1, 1.10)
    e, f = VARIANTS["E"], VARIANTS["F"]
    assert (e.focus_team, e.focus_attack_dir, e.build_up_passes, e.time_scale) == ("amber", -1, 0, 0.85)
    assert (f.focus_team, f.period, f.focus_attack_dir, f.decoy_run) == ("amber", 2, 1, True)
    assert not any(VARIANTS[v].decoy_run for v in "ABCDE")
