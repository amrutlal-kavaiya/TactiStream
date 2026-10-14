"""Scenario families: one module per family, registered in FAMILIES."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np

from tactistream.simulator.config import ScenarioName, VariantSpec
from tactistream.simulator.scenarios import space_creation
from tactistream.simulator.script import SegmentResult

Family = Callable[[np.random.Generator, VariantSpec], SegmentResult]

FAMILIES: Mapping[ScenarioName, Family] = {
    "space_creation": space_creation.build,
}
