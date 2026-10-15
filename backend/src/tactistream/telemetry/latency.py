"""Latency samples: kept in memory, recorded as histograms, logged per sample, handed to an optional hook."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from opentelemetry import metrics
from pydantic import ValidationError

from tactistream.contracts.latency import LatencyKind
from tactistream.contracts.latency import LatencySample as LatencySampleRecord
from tactistream.telemetry.correlation import current_trace_id
from tactistream.telemetry.instruments import Instruments, get_instruments

AttrValue = str | bool | int | float
SampleHook = Callable[[LatencySampleRecord], None]

LATENCY_LOG = "tactistream.latency"
latency_logger = logging.getLogger(LATENCY_LOG)
latency_logger.setLevel(logging.INFO)
logger = logging.getLogger(__name__)

_KINDS: tuple[LatencyKind, ...] = ("fast_overlay", "narrative")


@dataclass(frozen=True)
class LatencySample:
    kind: LatencyKind
    ms: int
    attrs: dict[str, AttrValue] = field(default_factory=dict)


def _wall_clock_ms() -> int:
    return time.time_ns() // 1_000_000


class LatencyRecorder:
    """`record(kind, ms, attrs)` builds the contract sample from the `match_id`, `target_id`, `viewer_id`,
    `outcome`, `fallback_reason`, `trace_id` and `config` attrs; all attrs stay on the in-memory sample."""

    def __init__(
        self,
        meter: metrics.Meter | None = None,
        *,
        instruments: Instruments | None = None,
        on_sample: SampleHook | None = None,
        wall_ms: Callable[[], int] = _wall_clock_ms,
    ) -> None:
        self._instruments = instruments or (Instruments(meter) if meter is not None else get_instruments())
        self._on_sample = on_sample
        self._wall_ms = wall_ms
        self._samples: dict[LatencyKind, list[LatencySample]] = {kind: [] for kind in _KINDS}

    def record(
        self, kind: LatencyKind, ms: int, attrs: Mapping[str, AttrValue] | None = None
    ) -> LatencySampleRecord:
        if ms < 0:
            raise ValueError("latency cannot be negative")
        attrs = dict(attrs or {})
        sample = self._build(kind, ms, attrs)
        self._samples[kind].append(LatencySample(kind=kind, ms=ms, attrs=attrs))
        self._instruments.record_latency(sample)
        latency_logger.info(LATENCY_LOG, extra=_log_attributes(sample))
        if self._on_sample is not None:
            try:
                self._on_sample(sample)
            except Exception:
                logger.exception("latency on_sample hook failed for %s", sample.sample_id)
        return sample

    def _build(self, kind: LatencyKind, ms: int, attrs: Mapping[str, AttrValue]) -> LatencySampleRecord:
        target_id = str(attrs.get("target_id", "unknown"))
        viewer_id = str(attrs.get("viewer_id", "unknown"))
        fields: dict[str, Any] = {
            "sample_id": f"lat-{kind}-{target_id}-{viewer_id}",
            "match_id": attrs.get("match_id", "unknown"),
            "kind": kind,
            "value_ms": ms,
            "outcome": attrs.get("outcome", "released"),
            "fallback_reason": attrs.get("fallback_reason"),
            "target_id": target_id,
            "viewer_id": viewer_id,
            "trace_id": attrs.get("trace_id") or current_trace_id(),
            "config": attrs.get("config", "live"),
            "recorded_ms": self._wall_ms(),
        }
        try:
            return LatencySampleRecord.model_validate(fields)
        except ValidationError as exc:
            raise ValueError(f"invalid latency sample: {exc.errors()[0]['msg']}") from exc

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


def _log_attributes(sample: LatencySampleRecord) -> dict[str, Any]:
    """`extra` for the log record; Azure Monitor maps these to `customDimensions`."""
    return sample.model_dump(
        mode="json",
        exclude_none=True,
        include={
            "sample_id",
            "kind",
            "value_ms",
            "outcome",
            "fallback_reason",
            "match_id",
            "target_id",
            "viewer_id",
            "trace_id",
            "config",
        },
    )
