"""Immutable per-run workflow context, deadline budgets and the append-only claim ledger."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tactistream.agents.model_client import Role

MIN_STEP_MS: Mapping[Role, int] = {"analyst": 800, "verifier": 600, "producer": 600, "single_agent": 800}


@dataclass(frozen=True)
class AgentBudgets:
    caps_ms: Mapping[Role, int]
    min_ms: Mapping[Role, int]
    reserve_ms: int = 400
    token_budget: int | None = None
    repair_min_remaining_ms: int = 3000
