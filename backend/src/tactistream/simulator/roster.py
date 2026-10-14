"""Fictional Blue/Amber rosters, 4-3-3 formation slots and match metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Literal

from tactistream.contracts import (
    AttackDirection,
    LocalizedName,
    MatchMetadata,
    PeriodSpec,
    PitchSpec,
    Player,
    Provenance,
    Team,
    TeamId,
)

if TYPE_CHECKING:
    from tactistream.simulator.config import SimulationConfig

Point = tuple[float, float]
FormationPhase = Literal["in_possession", "out_of_possession", "kickoff"]
AttackSign = Literal[1, -1]

PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
CENTRE_SPOT: Point = (52.5, 34.0)
TEAMS: tuple[TeamId, TeamId] = ("blue", "amber")
SHIRTS = tuple(range(1, 12))
ROLES: Mapping[int, Literal["GK", "DF", "MF", "FW"]] = {
    1: "GK",
    2: "DF",
    3: "DF",
    4: "DF",
    5: "DF",
    6: "MF",
    7: "FW",
    8: "MF",
    9: "FW",
    10: "MF",
    11: "FW",
}
_TEAM_NAMES: Mapping[TeamId, tuple[str, str, str]] = {
    "blue": ("Blue", "ब्लू", "#3B82F6"),
    "amber": ("Amber", "एम्बर", "#F59E0B"),
}

PERIOD_1 = PeriodSpec(period=1, attack_direction=AttackDirection(blue=1, amber=-1))
PERIOD_2 = PeriodSpec(period=2, attack_direction=AttackDirection(blue=-1, amber=1))

# Normalized slots: the team attacks +x; a player's left is +y. Out of possession the block sits 10 m deeper.
_IN_POSSESSION: Mapping[int, Point] = {
    1: (6.0, 34.0),
    2: (32.0, 10.0),
    3: (32.0, 58.0),
    4: (32.0, 27.0),
    5: (32.0, 41.0),
    6: (50.0, 34.0),
    8: (50.0, 22.0),
    10: (50.0, 46.0),
    7: (64.0, 10.0),
    9: (64.0, 34.0),
    11: (64.0, 58.0),
}
_KICKOFF: Mapping[int, Point] = {
    1: (6.0, 34.0),
    2: (28.0, 10.0),
    3: (28.0, 58.0),
    4: (28.0, 27.0),
    5: (28.0, 41.0),
    6: (38.0, 34.0),
    8: (38.0, 22.0),
    10: (38.0, 46.0),
    7: (44.0, 12.0),
    9: (43.0, 34.0),
    11: (44.0, 56.0),
}
FORMATION_433: Mapping[FormationPhase, Mapping[int, Point]] = {
    "in_possession": dict(sorted(_IN_POSSESSION.items())),
    "out_of_possession": {n: (x if n == 1 else x - 10.0, y) for n, (x, y) in sorted(_IN_POSSESSION.items())},
    "kickoff": dict(sorted(_KICKOFF.items())),
}


def player_id(team: TeamId, shirt: int) -> str:
    return f"{team}-{shirt:02d}"


PLAYER_IDS: tuple[str, ...] = tuple(player_id(team, n) for team in TEAMS for n in SHIRTS)


def team_of(pid: str) -> TeamId:
    return "blue" if pid.startswith("blue-") else "amber"


def shirt_of(pid: str) -> int:
    return int(pid.rsplit("-", 1)[1])


def opponent(team: TeamId) -> TeamId:
    return "amber" if team == "blue" else "blue"


def attack_dir(team: TeamId, period: int) -> AttackSign:
    """Blue attacks +x in period 1 and -x in period 2; Amber the opposite."""
    blue: AttackSign = 1 if period == 1 else -1
    if team == "blue":
        return blue
    return -1 if blue == 1 else 1


def to_actual(pos: Point, direction: AttackSign) -> Point:
    """Map a normalized (attack +x) position to stadium coordinates for a team attacking `direction`."""
    if direction == 1:
        return pos
    return (PITCH_LENGTH_M - pos[0], PITCH_WIDTH_M - pos[1])


def slots(team: TeamId, phase: FormationPhase, direction: AttackSign) -> dict[str, Point]:
    return {player_id(team, n): to_actual(pos, direction) for n, pos in FORMATION_433[phase].items()}


def build_metadata(config: SimulationConfig, periods: Sequence[PeriodSpec]) -> MatchMetadata:
    teams = [
        Team(
            team_id=team,
            display_name=LocalizedName(en=_TEAM_NAMES[team][0], hi=_TEAM_NAMES[team][1]),
            color_hex=_TEAM_NAMES[team][2],
            players=[
                Player(
                    player_id=player_id(team, n),
                    shirt_number=n,
                    role=ROLES[n],
                    display_name=LocalizedName(
                        en=f"{_TEAM_NAMES[team][0]} {n}", hi=f"{_TEAM_NAMES[team][1]} {n}"
                    ),
                )
                for n in SHIRTS
            ],
        )
        for team in TEAMS
    ]
    return MatchMetadata(
        schema_version="1.0",
        match_id=config.match_id,
        pitch=PitchSpec(length_m=105, width_m=68, origin="bottom_left"),
        teams=teams,
        periods=list(periods),
        frame_interval_ms=100,
        source=Provenance(kind="synthetic", generator_version=config.generator_version, seed=config.seed),
    )
