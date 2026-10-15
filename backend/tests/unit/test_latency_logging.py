import logging

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import HistogramDataPoint, InMemoryMetricReader

from tactistream.contracts import LatencySample
from tactistream.telemetry.instruments import Instruments
from tactistream.telemetry.latency import LatencyRecorder

FAST_ATTRS = {
    "match_id": "demo-blue-amber-001",
    "target_id": "evt-0042",
    "target_kind": "event",
    "viewer_id": "v-1a2b3c4d",
}
NARRATIVE_FALLBACK = {
    "match_id": "demo-blue-amber-001",
    "target_id": "ins-0045:1",
    "viewer_id": "v-1a2b3c4d",
    "outcome": "fallback",
    "fallback_reason": "timeout",
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
}


@pytest.fixture
def reader() -> InMemoryMetricReader:
    return InMemoryMetricReader()


@pytest.fixture
def received() -> list[LatencySample]:
    return []


@pytest.fixture
def recorder(reader: InMemoryMetricReader, received: list[LatencySample]) -> LatencyRecorder:
    instruments = Instruments(MeterProvider(metric_readers=[reader]).get_meter("test"))
    return LatencyRecorder(
        instruments=instruments, on_sample=received.append, wall_ms=lambda: 1_792_310_400_000
    )


def latency_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "tactistream.latency"]


def test_record_builds_a_contract_sample_and_hands_it_to_the_hook(
    recorder: LatencyRecorder, received: list[LatencySample]
) -> None:
    sample = recorder.record("fast_overlay", 120, FAST_ATTRS)
    assert sample == LatencySample(
        sample_id="lat-fast_overlay-evt-0042-v-1a2b3c4d",
        match_id="demo-blue-amber-001",
        kind="fast_overlay",
        value_ms=120,
        outcome="released",
        target_id="evt-0042",
        viewer_id="v-1a2b3c4d",
        config="live",
        recorded_ms=1_792_310_400_000,
    )
    assert received == [sample]


def test_in_memory_samples_api_is_unchanged(recorder: LatencyRecorder) -> None:
    recorder.record("fast_overlay", 120, FAST_ATTRS)
    (kept,) = recorder.samples("fast_overlay")
    assert kept.ms == 120
    assert kept.attrs == FAST_ATTRS
    assert recorder.percentile("fast_overlay", 95) == 120


def test_record_logs_one_structured_record(
    recorder: LatencyRecorder, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="tactistream.latency"):
        recorder.record("fast_overlay", 120, FAST_ATTRS)
    (record,) = latency_records(caplog)
    assert record.getMessage() == "tactistream.latency"
    assert record.levelno == logging.INFO
    assert record.__dict__["kind"] == "fast_overlay"
    assert record.__dict__["value_ms"] == 120
    assert record.__dict__["outcome"] == "released"
    assert record.__dict__["match_id"] == "demo-blue-amber-001"
    assert record.__dict__["target_id"] == "evt-0042"
    assert record.__dict__["viewer_id"] == "v-1a2b3c4d"
    assert "trace_id" not in record.__dict__


def test_fallback_samples_are_logged_and_recorded_never_skipped(
    recorder: LatencyRecorder,
    reader: InMemoryMetricReader,
    received: list[LatencySample],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="tactistream.latency"):
        sample = recorder.record("narrative", 8000, NARRATIVE_FALLBACK)
    assert sample.outcome == "fallback"
    assert sample.fallback_reason == "timeout"
    assert received == [sample]
    (record,) = latency_records(caplog)
    assert record.__dict__["outcome"] == "fallback"
    assert record.__dict__["fallback_reason"] == "timeout"
    assert record.__dict__["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    data = reader.get_metrics_data()
    assert data is not None
    (metric,) = data.resource_metrics[0].scope_metrics[0].metrics
    assert metric.name == "tactistream.narrative_latency_ms"
    (point,) = metric.data.data_points
    assert isinstance(point, HistogramDataPoint)
    assert point.count == 1


def test_narrative_fallback_without_reason_is_rejected(recorder: LatencyRecorder) -> None:
    attrs = {k: v for k, v in NARRATIVE_FALLBACK.items() if k != "fallback_reason"}
    with pytest.raises(ValueError, match="fallback_reason"):
        recorder.record("narrative", 8000, attrs)


def test_failing_hook_does_not_break_recording(caplog: pytest.LogCaptureFixture) -> None:
    def broken(_: LatencySample) -> None:
        raise RuntimeError("publisher down")

    recorder = LatencyRecorder(on_sample=broken)
    recorder.record("fast_overlay", 5, FAST_ATTRS)
    assert [s.ms for s in recorder.samples("fast_overlay")] == [5]
    assert any("on_sample" in r.getMessage() for r in caplog.records)


def test_minimal_attrs_still_produce_a_valid_sample(recorder: LatencyRecorder) -> None:
    sample = recorder.record("fast_overlay", 7)
    assert sample.match_id == "unknown"
    assert sample.target_id == "unknown"
