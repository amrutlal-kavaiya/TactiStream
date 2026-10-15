"""OpenTelemetry instruments named in FR-018 (Azure Monitor stores them as `customMetrics`)."""

from __future__ import annotations

from typing import Literal, get_args

from opentelemetry import metrics

from tactistream.contracts.latency import LatencySample
from tactistream.contracts.ws import FallbackReason

AgentRole = Literal["analyst", "verifier", "producer", "single_agent"]
HistoryStatus = Literal["ok", "timeout", "error"]

_FALLBACK_REASONS = frozenset(get_args(FallbackReason))


class Instruments:
    def __init__(self, meter: metrics.Meter | None = None) -> None:
        meter = meter or metrics.get_meter("tactistream")
        self._latency = {
            "fast_overlay": meter.create_histogram(
                "tactistream.fast_overlay_latency_ms",
                unit="ms",
                description="Server receipt to display ack (upper bound: includes the ack return trip)",
            ),
            "narrative": meter.create_histogram(
                "tactistream.narrative_latency_ms",
                unit="ms",
                description="Trigger receipt to narrative release or fallback display ack",
            ),
        }
        self._fallbacks = meter.create_counter("tactistream.narrative_fallback_total")
        self._model_calls = meter.create_counter("tactistream.model_calls_total")
        self._model_tokens = meter.create_counter("tactistream.model_tokens_total", unit="{token}")
        self._model_call_ms = meter.create_histogram("tactistream.model_call_ms", unit="ms")
        self._history_query_ms = meter.create_histogram("tactistream.history_query_ms", unit="ms")
        self._analytics_dropped = meter.create_counter("tactistream.analytics_dropped_total")
        self._checkpoint_failures = meter.create_counter("tactistream.checkpoint_write_failures_total")

    def record_latency(self, sample: LatencySample) -> None:
        attributes = {"outcome": sample.outcome, "config": sample.config}
        if sample.fallback_reason is not None:
            attributes["fallback_reason"] = sample.fallback_reason
        self._latency[sample.kind].record(sample.value_ms, attributes=attributes)

    def record_fallback(self, reason: FallbackReason, *, match_id: str, config: str = "live") -> None:
        if reason not in _FALLBACK_REASONS:
            raise ValueError(f"unknown fallback reason {reason!r}")
        self._fallbacks.add(1, attributes={"reason": reason, "match_id": match_id, "config": config})

    def record_model_call(
        self, agent: AgentRole, model: str, input_tokens: int, output_tokens: int, duration_ms: int
    ) -> None:
        self._model_calls.add(1, attributes={"agent": agent, "model": model})
        self._model_tokens.add(
            input_tokens, attributes={"agent": agent, "direction": "input", "model": model}
        )
        self._model_tokens.add(
            output_tokens, attributes={"agent": agent, "direction": "output", "model": model}
        )
        self._model_call_ms.record(duration_ms, attributes={"agent": agent, "model": model})

    def record_history_query(self, duration_ms: int, status: HistoryStatus) -> None:
        self._history_query_ms.record(duration_ms, attributes={"status": status})

    def record_analytics_drop(self, kind: str) -> None:
        self._analytics_dropped.add(1, attributes={"kind": kind})

    def record_checkpoint_failure(self) -> None:
        self._checkpoint_failures.add(1)


_instruments: Instruments | None = None


def get_instruments() -> Instruments:
    """Process-wide instruments on the global meter (a proxy until `setup_telemetry` installs a provider)."""
    global _instruments
    if _instruments is None:
        _instruments = Instruments()
    return _instruments
