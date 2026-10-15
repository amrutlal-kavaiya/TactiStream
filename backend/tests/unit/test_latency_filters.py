from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import HistogramDataPoint, InMemoryMetricReader

from tactistream.telemetry.latency import AttrValue, LatencyRecorder


def attrs(ms: int) -> dict[str, AttrValue]:
    if ms // 1000 % 2:
        return {"outcome": "released", "target_id": f"ins-{ms}"}
    return {"outcome": "fallback", "fallback_reason": "timeout", "target_id": f"ins-{ms}"}


def narrative_recorder(meter_provider: MeterProvider | None = None) -> LatencyRecorder:
    meter = meter_provider.get_meter("test") if meter_provider is not None else None
    recorder = LatencyRecorder(meter=meter)
    for ms in range(1000, 10_001, 1000):
        recorder.record("narrative", ms, attrs(ms))
    return recorder


def test_percentile_filters_on_sample_attrs() -> None:
    recorder = narrative_recorder()
    assert recorder.percentile("narrative", 95, outcome="released") == 9000
    assert recorder.percentile("narrative", 50, outcome="released") == 5000
    assert recorder.percentile("narrative", 100, outcome="fallback") == 10_000
    assert recorder.percentile("narrative", 95, outcome="abstained") is None
    assert recorder.percentile("narrative", 95, outcome="fallback", fallback_reason="timeout") == 10_000


def test_unfiltered_percentile_includes_all_samples() -> None:
    recorder = narrative_recorder()
    assert recorder.percentile("narrative", 95) == 10_000
    assert recorder.percentile("narrative", 50) == 5000


def test_count_filters_on_sample_attrs() -> None:
    recorder = narrative_recorder()
    assert recorder.count("narrative") == 10
    assert recorder.count("narrative", outcome="fallback") == 5
    assert recorder.count("narrative", outcome="released") == 5
    assert recorder.count("narrative", outcome="fallback", fallback_reason="expired") == 0
    assert recorder.count("fast_overlay") == 0


def test_histogram_points_carry_outcome_and_fallback_reason() -> None:
    reader = InMemoryMetricReader()
    narrative_recorder(MeterProvider(metric_readers=[reader]))
    data = reader.get_metrics_data()
    assert data is not None
    points = [
        point
        for resource_metrics in data.resource_metrics
        for scope_metrics in resource_metrics.scope_metrics
        for metric in scope_metrics.metrics
        if metric.name == "tactistream.narrative_latency_ms"
        for point in metric.data.data_points
    ]
    by_attrs = {tuple(sorted((point.attributes or {}).items())): point for point in points}
    assert all(isinstance(point, HistogramDataPoint) for point in points)
    released = by_attrs[(("config", "live"), ("outcome", "released"))]
    fallback = by_attrs[(("config", "live"), ("fallback_reason", "timeout"), ("outcome", "fallback"))]
    assert (released.count, fallback.count) == (5, 5)
