from typing import Any

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import HistogramDataPoint, InMemoryMetricReader, NumberDataPoint

from tactistream.contracts import LatencySample
from tactistream.telemetry.instruments import Instruments, get_instruments

Point = tuple[dict[str, Any], float]


@pytest.fixture
def reader() -> InMemoryMetricReader:
    return InMemoryMetricReader()


@pytest.fixture
def instruments(reader: InMemoryMetricReader) -> Instruments:
    return Instruments(MeterProvider(metric_readers=[reader]).get_meter("test"))


def points(reader: InMemoryMetricReader) -> dict[str, list[Point]]:
    data = reader.get_metrics_data()
    found: dict[str, list[Point]] = {}
    if data is None:
        return found
    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                for point in metric.data.data_points:
                    value = point.sum if isinstance(point, HistogramDataPoint) else point.value
                    assert isinstance(point, HistogramDataPoint | NumberDataPoint)
                    found.setdefault(metric.name, []).append((dict(point.attributes or {}), value))
    return found


def sample(**overrides: Any) -> LatencySample:
    fields: dict[str, Any] = {
        "sample_id": "lat-fast_overlay-evt-0042-v-1a2b3c4d",
        "match_id": "demo-blue-amber-001",
        "kind": "fast_overlay",
        "value_ms": 120,
        "outcome": "released",
        "target_id": "evt-0042",
        "viewer_id": "v-1a2b3c4d",
        "recorded_ms": 1,
    }
    fields.update(overrides)
    return LatencySample.model_validate(fields)


def test_record_latency_routes_by_kind(instruments: Instruments, reader: InMemoryMetricReader) -> None:
    instruments.record_latency(sample())
    instruments.record_latency(
        sample(kind="narrative", value_ms=4000, outcome="fallback", fallback_reason="timeout")
    )
    found = points(reader)
    assert found["tactistream.fast_overlay_latency_ms"] == [({"outcome": "released", "config": "live"}, 120)]
    assert found["tactistream.narrative_latency_ms"] == [
        ({"outcome": "fallback", "config": "live", "fallback_reason": "timeout"}, 4000)
    ]


def test_record_fallback(instruments: Instruments, reader: InMemoryMetricReader) -> None:
    instruments.record_fallback("timeout", match_id="demo-blue-amber-001")
    assert points(reader)["tactistream.narrative_fallback_total"] == [
        ({"reason": "timeout", "match_id": "demo-blue-amber-001", "config": "live"}, 1)
    ]


def test_unknown_fallback_reason_raises(instruments: Instruments) -> None:
    with pytest.raises(ValueError, match="fallback reason"):
        instruments.record_fallback("bored", match_id="demo-blue-amber-001")  # type: ignore[arg-type]


def test_record_model_call_counts_calls_and_tokens_by_direction(
    instruments: Instruments, reader: InMemoryMetricReader
) -> None:
    instruments.record_model_call("analyst", "gpt-x", input_tokens=1900, output_tokens=210, duration_ms=1400)
    found = points(reader)
    assert found["tactistream.model_calls_total"] == [({"agent": "analyst", "model": "gpt-x"}, 1)]
    assert sorted(found["tactistream.model_tokens_total"], key=lambda p: p[1]) == [
        ({"agent": "analyst", "direction": "output", "model": "gpt-x"}, 210),
        ({"agent": "analyst", "direction": "input", "model": "gpt-x"}, 1900),
    ]


def test_record_history_query(instruments: Instruments, reader: InMemoryMetricReader) -> None:
    instruments.record_history_query(320, "ok")
    assert points(reader)["tactistream.history_query_ms"] == [({"status": "ok"}, 320)]


def test_record_analytics_drop(instruments: Instruments, reader: InMemoryMetricReader) -> None:
    instruments.record_analytics_drop("insight")
    instruments.record_analytics_drop("insight")
    assert points(reader)["tactistream.analytics_dropped_total"] == [({"kind": "insight"}, 2)]


def test_record_checkpoint_failure(instruments: Instruments, reader: InMemoryMetricReader) -> None:
    instruments.record_checkpoint_failure()
    assert points(reader)["tactistream.checkpoint_write_failures_total"] == [({}, 1)]


def test_get_instruments_is_a_lazy_singleton() -> None:
    assert get_instruments() is get_instruments()
