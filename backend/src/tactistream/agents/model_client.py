"""Model access for the agents: one JSON-in/JSON-out call per role, scripted or live."""

from __future__ import annotations

from typing import Literal

Role = Literal["analyst", "verifier", "producer", "single_agent"]
