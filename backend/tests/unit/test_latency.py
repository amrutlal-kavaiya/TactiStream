import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import HistogramDataPoint, InMemoryMetricReader

from tactistream.telemetry.latency import LatencyRecorder


def test_p95_of_1_to_100_is_95() -> None:
    recorder = LatencyRecorder()
    for ms in range(1, 101):
        recorder.record("fast_overlay", ms)
    assert recorder.percentile("fast_overlay", 95) == 95


def test_percentile_uses_nearest_rank() -> None:
    recorder = LatencyRecorder()
    for ms in [40, 10, 30, 20]:
        recorder.record("narrative", ms)
    assert recorder.percentile("narrative", 50) == 20
    assert recorder.percentile("narrative", 100) == 40
    assert recorder.percentile("narrative", 1) == 10


def test_kinds_are_kept_separate_and_empty_kind_has_no_percentile() -> None:
    recorder = LatencyRecorder()
    recorder.record("fast_overlay", 5, {"target_kind": "event"})
    assert recorder.percentile("narrative", 95) is None
    assert [s.ms for s in recorder.samples("fast_overlay")] == [5]
    assert recorder.samples("fast_overlay")[0].attrs == {"target_kind": "event"}


@pytest.mark.parametrize("p", [0, -1, 101])
def test_percentile_out_of_range_rejected(p: float) -> None:
    recorder = LatencyRecorder()
    recorder.record("fast_overlay", 1)
    with pytest.raises(ValueError):
        recorder.percentile("fast_overlay", p)


def test_negative_latency_rejected() -> None:
    with pytest.raises(ValueError):
        LatencyRecorder().record("fast_overlay", -1)


def test_samples_are_exported_to_otel_histograms() -> None:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    recorder = LatencyRecorder(meter=provider.get_meter("test"))
    recorder.record("fast_overlay", 120, {"target_kind": "insight"})
    recorder.record("fast_overlay", 80, {"target_kind": "insight"})
    recorder.record("narrative", 4000)

    data = reader.get_metrics_data()
    assert data is not None
    points: dict[str, HistogramDataPoint] = {}
    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                for point in metric.data.data_points:
                    assert isinstance(point, HistogramDataPoint)
                    points[metric.name] = point
    assert points["tactistream.fast_overlay_latency_ms"].count == 2
    assert points["tactistream.fast_overlay_latency_ms"].sum == 200
    assert dict(points["tactistream.fast_overlay_latency_ms"].attributes or {}) == {
        "outcome": "released",
        "config": "live",
    }
    assert points["tactistream.narrative_latency_ms"].count == 1
