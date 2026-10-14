"""simulate(config) -> SimulationOutput: family dispatch, contract records and manifest. No I/O."""

from __future__ import annotations

from dataclasses import dataclass

from tactistream.contracts import MatchEvent, MatchMetadata, TrackingFrame
from tactistream.simulator.config import SimulationConfig
from tactistream.simulator.manifest import GenerationManifest


@dataclass(frozen=True, slots=True)
class SimulationOutput:
    config: SimulationConfig
    metadata: MatchMetadata
    events: tuple[MatchEvent, ...]
    frames: tuple[TrackingFrame, ...]
    manifest: GenerationManifest
