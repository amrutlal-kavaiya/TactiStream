import json
from pathlib import Path
from typing import Any

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tactistream.agents.context import ClaimRecord
from tactistream.agents.trace import TraceRecorder, TraceStore, new_trace_id, trace_envelope
from tactistream.contracts import AnalystOutput, FeedEnvelope, Verdict
from tactistream.contracts.schema_registry import validate
from tactistream.contracts.trace import AgentTrace, ToolCallRecord, Usage
from tactistream.transport.clock import FakeClock

EXAMPLES = Path(__file__).parents[3] / "contracts" / "examples"
TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
T0 = 1_760_422_600_000
FORBIDDEN_KEYS = {"reasoning", "thought", "prompt", "system"}


def analyst_output() -> AnalystOutput:
    return AnalystOutput.model_validate(json.loads((EXAMPLES / "analyst_output.json").read_text("utf-8")))


def ok(claim_id: str) -> Verdict:
    return Verdict(claim_id=claim_id, decision="approve", reason_codes=["ok"])


def tool_call(metric_id: str) -> ToolCallRecord:
    return ToolCallRecord(
        tool="get_metric", args={"metric_id": metric_id}, status="ok", result_ids=[metric_id], latency_ms=0
    )


def recorder(clock: FakeClock, tracer: otel_trace.Tracer | None = None) -> TraceRecorder:
    return TraceRecorder(
        trace_id=TRACE_ID,
        match_id="demo-blue-amber-001",
        moment_id="mom-0045",
        insight_id="ins-0045",
        insight_version=1,
        state_version=512,
        as_of_session_ms=46_500,
        runner="three_agent",
        trigger_receipt_ms=T0,
        deadline_ms=T0 + 8000,
        clock=clock,
        model_deployment="scripted",
        tracer=tracer,
    )


async def run_steps(clock: FakeClock, rec: TraceRecorder, analyst_usage: Usage) -> AgentTrace:
    rec.start_step("gate", input_ids=["mom-0045"])
    rec.end_step("ok")
    rec.start_step("analyst", prompt_version="analyst.v1", budget_ms=3500, input_ids=["mom-0045"])
    rec.record_tool_call(tool_call("metric-channel-0042"))
    rec.record_tool_call(tool_call("metric-defender_follow-0042"))
    await clock.advance(1400)
    output = analyst_output()
    rec.end_step("ok", analyst_output=output, usage=analyst_usage)
    rec.start_step("verifier", prompt_version="verifier.v1", budget_ms=2500, input_ids=["clm-0045-1"])
    await clock.advance(900)
    rec.end_step(
        "ok",
        verdicts=[ok("clm-0045-1"), ok("clm-0045-2")],
        usage=Usage(model_calls=1, tokens_in=1300, tokens_out=120),
    )
    records = [
        ClaimRecord(claim=c, attempt=1, final=ok(c.claim_id), status="approved") for c in output.claims
    ]
    return rec.finalize(outcome="released", claims=records, released_claim_ids=["clm-0045-2"])


async def test_steps_are_indexed_and_carry_tool_calls() -> None:
    clock = FakeClock(T0 + 20)
    trace = await run_steps(clock, recorder(clock), Usage(model_calls=1, tokens_in=1900, tokens_out=260))
    assert [step.index for step in trace.steps] == [0, 1, 2]
    assert [step.role for step in trace.steps] == ["gate", "analyst", "verifier"]
    analyst = trace.steps[1]
    assert [c.result_ids for c in analyst.tool_calls] == [
        ["metric-channel-0042"],
        ["metric-defender_follow-0042"],
    ]
    assert analyst.started_ms == T0 + 20
    assert analyst.latency_ms == 1400
    assert analyst.prompt_version == "analyst.v1"
    assert trace.steps[2].tool_calls == []
    assert (trace.started_ms, trace.finished_ms) == (T0 + 20, T0 + 20 + 2300)
    assert trace.model_deployment == "scripted"
    assert [entry.status for entry in trace.claims] == ["approved", "approved"]


async def test_finalized_trace_validates_and_has_no_private_reasoning() -> None:
    clock = FakeClock(T0)
    trace = await run_steps(clock, recorder(clock), Usage(model_calls=1, tokens_in=1900, tokens_out=260))
    dumped = trace.model_dump(mode="json", exclude_none=True)
    validate("agent_trace.schema.json", dumped)

    def keys(node: Any) -> set[str]:
        if isinstance(node, dict):
            return set(node) | {k for v in node.values() for k in keys(v)}
        if isinstance(node, list):
            return {k for v in node for k in keys(v)}
        return set()

    assert not keys(dumped) & FORBIDDEN_KEYS
    assert trace.usage == Usage(model_calls=2, tokens_in=3200, tokens_out=380)


async def test_tokens_are_null_when_any_step_lacks_usage() -> None:
    clock = FakeClock(T0)
    trace = await run_steps(clock, recorder(clock), Usage(model_calls=1, tokens_in=None, tokens_out=None))
    assert trace.usage == Usage(model_calls=2, tokens_in=None, tokens_out=None)
    dumped = trace.model_dump(mode="json", exclude_none=True)
    assert dumped["usage"] == {"model_calls": 2, "tokens_in": None, "tokens_out": None}
    validate("agent_trace.schema.json", dumped)


def test_tool_call_without_open_step_is_an_error() -> None:
    rec = recorder(FakeClock(T0))
    with pytest.raises(RuntimeError):
        rec.record_tool_call(tool_call("metric-channel-0042"))
    rec.start_step("gate")
    with pytest.raises(RuntimeError):
        rec.start_step("analyst")


def test_open_step_is_closed_as_failed_on_finalize() -> None:
    rec = recorder(FakeClock(T0))
    rec.start_step("analyst", prompt_version="analyst.v1")
    trace = rec.finalize(outcome="cancelled", claims=[])
    assert trace.steps[0].status == "failed"
    assert trace.outcome == "cancelled"


def test_finalize_records_fallback_and_fixture() -> None:
    rec = recorder(FakeClock(T0))
    rec.fixture = "model_timeout"
    rec.start_step("analyst", injected_fault="model_timeout")
    rec.end_step("timeout", error="analyst exceeded 3500 ms")
    trace = rec.finalize(outcome="fallback", fallback_reason="timeout", claims=[], narrative_latency_ms=3600)
    assert trace.fixture == "model_timeout"
    assert trace.fallback_reason == "timeout"
    assert trace.steps[0].injected_fault == "model_timeout"
    assert trace.narrative_latency_ms == 3600
    assert trace.usage == Usage(model_calls=0, tokens_in=None, tokens_out=None)


def test_each_step_emits_an_otel_span() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    rec = recorder(FakeClock(T0), tracer=provider.get_tracer("test"))
    rec.start_step("analyst", prompt_version="analyst.v1", budget_ms=3500)
    rec.end_step("ok", usage=Usage(model_calls=1, tokens_in=1900, tokens_out=260))
    rec.start_step("checks")
    rec.end_step("failed", error="unapproved_claim")
    spans = exporter.get_finished_spans()
    assert [span.name for span in spans] == ["agent.analyst", "agent.checks"]
    attrs = dict(spans[0].attributes or {})
    assert attrs["gen_ai.agent.name"] == "analyst"
    assert attrs["gen_ai.request.model"] == "scripted"
    assert attrs["gen_ai.usage.input_tokens"] == 1900
    assert attrs["gen_ai.usage.output_tokens"] == 260
    assert attrs["tactistream.trace_id"] == TRACE_ID
    assert attrs["tactistream.moment_id"] == "mom-0045"
    assert attrs["tactistream.step.index"] == 0
    assert attrs["tactistream.step.status"] == "ok"
    assert attrs["tactistream.prompt_version"] == "analyst.v1"
    assert attrs["tactistream.budget_ms"] == 3500
    assert dict(spans[1].attributes or {})["tactistream.step.status"] == "failed"


def test_trace_store_keeps_traces_per_match(tmp_path: Path) -> None:
    trace = AgentTrace.model_validate(json.loads((EXAMPLES / "agent_trace.json").read_text("utf-8")))
    store = TraceStore()
    store.put(trace)
    assert store.get("demo-blue-amber-001", TRACE_ID) is trace
    assert store.get("other-match-001", TRACE_ID) is None
    assert store.get("demo-blue-amber-001", "0" * 32) is None


def test_trace_store_writes_json_files(tmp_path: Path) -> None:
    trace = AgentTrace.model_validate(json.loads((EXAMPLES / "agent_trace.json").read_text("utf-8")))
    TraceStore(trace_dir=tmp_path).put(trace)
    path = tmp_path / "demo-blue-amber-001" / f"{TRACE_ID}.json"
    assert json.loads(path.read_text("utf-8")) == trace.model_dump(mode="json", exclude_none=True)


def test_trace_envelope() -> None:
    trace = AgentTrace.model_validate(json.loads((EXAMPLES / "agent_trace.json").read_text("utf-8")))
    envelope = trace_envelope(trace, published_ms=T0 + 5000)
    assert isinstance(envelope, FeedEnvelope)
    assert (envelope.kind, envelope.record_id, envelope.match_id) == ("agent_trace", TRACE_ID, trace.match_id)
    assert envelope.payload is trace
    validate("feed_envelope.schema.json", envelope.model_dump(mode="json", exclude_none=True))


def test_new_trace_id_uses_the_current_span() -> None:
    provider = TracerProvider()
    with provider.get_tracer("test").start_as_current_span("narrative") as span:
        assert new_trace_id() == format(span.get_span_context().trace_id, "032x")
    first, second = new_trace_id(), new_trace_id()
    assert first != second
    assert len(first) == 32
    assert int(first, 16) >= 0
