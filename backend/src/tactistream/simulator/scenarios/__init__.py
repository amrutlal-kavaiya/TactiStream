"""Scenario families: one module per family, registered in FAMILIES."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np

from tactistream.simulator.config import ScenarioName, VariantSpec
from tactistream.simulator.scenarios import press_turnover, space_creation, switch_escape
from tactistream.simulator.script import SegmentResult

Family = Callable[[np.random.Generator, VariantSpec], SegmentResult]

FAMILIES: Mapping[ScenarioName, Family] = {
    "space_creation": space_creation.build,
    "press_turnover": press_turnover.build,
    "switch_escape": switch_escape.build,
}
