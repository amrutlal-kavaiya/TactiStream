"""`MatchMetadata` mirroring `contracts/schemas/match_metadata.schema.json`."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from tactistream.contracts.common import ContractModel, MatchId, PlayerId, Provenance, SchemaVersion, TeamId

AttackSign = Literal[1, -1]
PlayerRole = Literal["GK", "DF", "MF", "FW"]


class LocalizedName(ContractModel):
    en: str
    hi: str


class PitchSpec(ContractModel):
    length_m: Literal[105]
    width_m: Literal[68]
    origin: Literal["bottom_left"]


class Player(ContractModel):
    player_id: PlayerId
    shirt_number: Annotated[int, Field(ge=1, le=99)]
    role: PlayerRole
    display_name: LocalizedName


class Team(ContractModel):
    team_id: TeamId
    display_name: LocalizedName
    color_hex: Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
    players: Annotated[list[Player], Field(min_length=11)]


class AttackDirection(ContractModel):
    """Direction along x in which each team attacks this period: +1 or -1."""

    blue: AttackSign
    amber: AttackSign


class PeriodSpec(ContractModel):
    period: Annotated[int, Field(ge=1, le=2)]
    attack_direction: AttackDirection


class MatchMetadata(ContractModel):
    schema_version: SchemaVersion
    match_id: MatchId
    pitch: PitchSpec
    teams: Annotated[list[Team], Field(min_length=2, max_length=2)]
    periods: Annotated[list[PeriodSpec], Field(min_length=1)]
    frame_interval_ms: Literal[100]
    source: Provenance
