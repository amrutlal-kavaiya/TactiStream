"""Simulation configuration, variants and split guards."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Literal, get_args

from tactistream.contracts import TeamId

ScenarioName = Literal[
    "space_creation",
    "press_turnover",
    "switch_escape",
    "run_no_channel",
    "press_no_turnover",
    "switch_closed",
    "tracking_gap",
    "demo_match",
]
Variant = Literal["A", "B", "C", "D", "E", "F"]
Split = Literal["dev", "eval"]
KeyActorSet = Literal["primary", "alternate", "second_alternate"]
ConfigErrorCode = Literal[
    "invalid_seed",
    "invalid_variant",
    "invalid_scenario",
    "eval_seed_requires_eval_split",
    "eval_variant_requires_eval_split",
    "dev_seed_in_eval_split",
]

SCENARIOS: tuple[ScenarioName, ...] = get_args(ScenarioName)
DEV_SEEDS = range(1, 10_000)
EVAL_SEED_MIN = 10_000
SEED_MAX = 2**31 - 1
DEV_VARIANTS: tuple[Variant, ...] = ("A", "B", "C")
EVAL_VARIANTS: tuple[Variant, ...] = ("D", "E", "F")
GENERATOR_VERSION = "0.1.0"
HERO_MATCH_IDS: Mapping[tuple[str, int, str, str], str] = {
    ("space_creation", 42, "A", "dev"): "demo-blue-amber-001",
    ("demo_match", 42, "A", "dev"): "demo-blue-amber-002",
}


class ConfigError(ValueError):
    """A configuration the generator refuses; `str(error)` is the CLI message."""

    def __init__(self, code: ConfigErrorCode, message: str) -> None:
        super().__init__(message)
        self.code: ConfigErrorCode = code
        self.message = message


@dataclass(frozen=True, slots=True)
class VariantSpec:
    variant: Variant
    split: Split
    focus_team: TeamId
    period: Literal[1, 2]
    y_mirror: bool
    key_actor_set: KeyActorSet
    build_up_passes: int
    time_scale: float
    decoy_run: bool

    @property
    def focus_attack_dir(self) -> Literal[1, -1]:
        """Direction along x the focus team attacks in this variant's period (Blue attacks +x in period 1)."""
        blue_dir = 1 if self.period == 1 else -1
        return blue_dir if self.focus_team == "blue" else -blue_dir


VARIANTS: Mapping[Variant, VariantSpec] = {
    "A": VariantSpec("A", "dev", "blue", 1, False, "primary", 2, 1.00, False),
    "B": VariantSpec("B", "dev", "blue", 1, True, "primary", 3, 1.00, False),
    "C": VariantSpec("C", "dev", "blue", 1, False, "alternate", 1, 1.10, False),
    "D": VariantSpec("D", "eval", "blue", 2, True, "second_alternate", 4, 0.90, False),
    "E": VariantSpec("E", "eval", "amber", 1, False, "primary", 0, 0.85, False),
    "F": VariantSpec("F", "eval", "amber", 2, True, "alternate", 2, 1.15, True),
}


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    seed: int
    scenario: ScenarioName
    variant: Variant = "A"
    split: Split = "dev"
    generator_version: str = GENERATOR_VERSION

    def __post_init__(self) -> None:
        if not 1 <= self.seed <= SEED_MAX:
            raise ConfigError("invalid_seed", f"seed must be in 1..{SEED_MAX}")
        if self.scenario not in SCENARIOS:
            raise ConfigError(
                "invalid_scenario", f"unknown scenario {self.scenario!r}; valid: {', '.join(SCENARIOS)}"
            )
        if self.variant not in VARIANTS:
            raise ConfigError("invalid_variant", f"unknown variant {self.variant!r}; valid: A-F")
        if self.split == "dev":
            if self.seed >= EVAL_SEED_MIN:
                raise ConfigError(
                    "eval_seed_requires_eval_split", f"seed {self.seed} is reserved for split=eval"
                )
            if self.variant in EVAL_VARIANTS:
                raise ConfigError(
                    "eval_variant_requires_eval_split", f"variant {self.variant} is reserved for split=eval"
                )
        elif self.split == "eval":
            if self.seed < EVAL_SEED_MIN:
                raise ConfigError("dev_seed_in_eval_split", f"split=eval requires seed >= {EVAL_SEED_MIN}")
            if self.variant not in EVAL_VARIANTS:
                raise ConfigError("invalid_variant", "split=eval requires variant D, E or F")
            if self.scenario == "demo_match":
                raise ConfigError("invalid_variant", "demo_match is a development program (split=dev only)")
        else:
            raise ConfigError("invalid_variant", f"unknown split {self.split!r}; valid: dev, eval")

    @property
    def spec(self) -> VariantSpec:
        return VARIANTS[self.variant]

    @property
    def match_id(self) -> str:
        hero = HERO_MATCH_IDS.get((self.scenario, self.seed, self.variant, self.split))
        if hero is not None:
            return hero
        return "sim-" + hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()[:10]

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
