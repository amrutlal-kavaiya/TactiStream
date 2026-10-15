"""Validation issue types shared by the possession state machine and the output validator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

IssueCode = Literal[
    "schema_invalid",
    "speed_exceeded",
    "accel_exceeded",
    "ball_detached",
    "pass_start_mismatch",
    "pass_end_mismatch",
    "pass_ball_speed",
    "event_coord_mismatch",
    "illegal_transition",
    "attack_direction_inconsistent",
    "sequence_gap",
    "frame_gap",
    "roster_incomplete",
    "out_of_bounds",
]


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: IssueCode
    record_id: str
    detail: str

    def line(self) -> str:
        return f"{self.code} {self.record_id} {self.detail}"
