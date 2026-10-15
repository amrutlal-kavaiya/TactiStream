"""In-memory latency samples plus OpenTelemetry histograms for the fast overlay and narrative paths."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from opentelemetry import metrics

LatencyKind = Literal["fast_overlay", "narrative"]
AttrValue = str | bool | int | float

_HISTOGRAMS: dict[LatencyKind, tuple[str, str]] = {
    "fast_overlay": (
        "tactistream.fast_overlay_latency_ms",
        "Server receipt to display ack (upper bound: includes the ack return trip)",
    ),
    "narrative": ("tactistream.narrative_latency_ms", "Server receipt to narrative release or fallback"),
}


@dataclass(frozen=True)
class LatencySample:
    kind: LatencyKind
    ms: int
    attrs: dict[str, AttrValue] = field(default_factory=dict)


class LatencyRecorder:
    def __init__(self, meter: metrics.Meter | None = None) -> None:
        meter = meter or metrics.get_meter("tactistream")
        self._histograms = {
            kind: meter.create_histogram(name, unit="ms", description=description)
            for kind, (name, description) in _HISTOGRAMS.items()
        }
        self._samples: dict[LatencyKind, list[LatencySample]] = {kind: [] for kind in _HISTOGRAMS}

    def record(self, kind: LatencyKind, ms: int, attrs: Mapping[str, AttrValue] | None = None) -> None:
        if ms < 0:
            raise ValueError("latency cannot be negative")
        sample = LatencySample(kind=kind, ms=ms, attrs=dict(attrs or {}))
        self._samples[kind].append(sample)
        self._histograms[kind].record(ms, attributes=sample.attrs)

    def samples(self, kind: LatencyKind) -> list[LatencySample]:
        return list(self._samples[kind])

    def percentile(self, kind: LatencyKind, p: float) -> int | None:
        """Nearest-rank percentile (`0 < p <= 100`); `None` when no samples were recorded."""
        if not 0 < p <= 100:
            raise ValueError("percentile must be in (0, 100]")
        values = sorted(s.ms for s in self._samples[kind])
        if not values:
            return None
        rank = math.ceil(p * len(values) / 100)
        return values[rank - 1]
