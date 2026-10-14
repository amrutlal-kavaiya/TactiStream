"""Deterministic synthetic match simulator: (scenario, seed, variant) -> records + ground-truth manifest."""

from tactistream.simulator.config import SimulationConfig
from tactistream.simulator.engine import SimulationOutput, simulate
from tactistream.simulator.validate import validate_output

__all__ = ["SimulationConfig", "SimulationOutput", "simulate", "validate_output"]
