import re

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tactistream.telemetry.correlation import current_trace_id, workflow_span

HEX32 = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def tracer(exporter: InMemorySpanExporter) -> trace.Tracer:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test")


def test_yielded_id_is_the_exported_span_trace_id(
    tracer: trace.Tracer, exporter: InMemorySpanExporter
) -> None:
    with workflow_span("demo-blue-amber-001", "mom-0045", tracer=tracer) as trace_id:
        assert HEX32.match(trace_id)
        assert current_trace_id() == trace_id
    (span,) = exporter.get_finished_spans()
    assert span.name == "tactistream.explain_moment"
    assert format(span.context.trace_id, "032x") == trace_id
    assert dict(span.attributes or {}) == {
        "match_id": "demo-blue-amber-001",
        "moment_id": "mom-0045",
        "config": "live",
    }


def test_config_attribute_is_passed_through(tracer: trace.Tracer, exporter: InMemorySpanExporter) -> None:
    with workflow_span("demo-blue-amber-001", "mom-0045", config="single_agent", tracer=tracer):
        pass
    (span,) = exporter.get_finished_spans()
    assert (span.attributes or {})["config"] == "single_agent"


def test_nested_spans_share_the_trace_id(tracer: trace.Tracer, exporter: InMemorySpanExporter) -> None:
    with (
        workflow_span("demo-blue-amber-001", "mom-0045", tracer=tracer) as trace_id,
        tracer.start_as_current_span("tactistream.model_call"),
    ):
        assert current_trace_id() == trace_id
    child, parent = exporter.get_finished_spans()
    assert child.context.trace_id == parent.context.trace_id
    assert child.parent is not None and child.parent.span_id == parent.context.span_id


def test_current_trace_id_outside_a_span_is_none() -> None:
    assert current_trace_id() is None


def test_unconfigured_telemetry_still_yields_valid_distinct_ids() -> None:
    tracer = trace.NoOpTracerProvider().get_tracer("test")
    with workflow_span("demo-blue-amber-001", "mom-0045", tracer=tracer) as first:
        assert HEX32.match(first)
    with workflow_span("demo-blue-amber-001", "mom-0046", tracer=tracer) as second:
        assert HEX32.match(second)
    assert first != second
