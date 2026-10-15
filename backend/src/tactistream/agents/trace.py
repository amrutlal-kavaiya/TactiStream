"""Per-run `AgentTrace`: one `TraceStep` and OTel span per step; decisions only, never reasoning."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opentelemetry import trace as otel_trace

from tactistream.agents.context import ClaimRecord
from tactistream.contracts import AnalystOutput, FeedEnvelope, ProducerOutput, Verdict
from tactistream.contracts.trace import (
    AgentTrace,
    ClaimTraceEntry,
    FixtureKind,
    RunnerKind,
    RunOutcome,
    StepRole,
    StepStatus,
    ToolCallRecord,
    TraceCheckFailure,
    TraceStep,
    Usage,
)
from tactistream.contracts.ws import FallbackReason
from tactistream.transport.clock import Clock

SCHEMA_VERSION = "1.0"
MODEL_ROLES: frozenset[StepRole] = frozenset({"analyst", "verifier", "producer", "single_agent"})


def new_trace_id() -> str:
    """The current span's trace ID as 32 hex chars, so logs, spans and the trace line up; else a fresh one."""
    context = otel_trace.get_current_span().get_span_context()
    if context.is_valid:
        return format(context.trace_id, "032x")
    return uuid.uuid4().hex


@dataclass
class _OpenStep:
    index: int
    role: StepRole
    attempt: int
    prompt_version: str | None
    started_ms: int
    budget_ms: int | None
    injected_fault: FixtureKind | None
    input_ids: list[str]
    span: otel_trace.Span
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


class TraceRecorder:
    """Builds one `AgentTrace`; at most one step is open at a time and tool calls attach to it."""

    def __init__(
        self,
        *,
        trace_id: str,
        match_id: str,
        moment_id: str,
        insight_id: str,
        insight_version: int,
        state_version: int,
        as_of_session_ms: int,
        runner: RunnerKind,
        trigger_receipt_ms: int,
        deadline_ms: int,
        clock: Clock,
        model_deployment: str | None = None,
        fixture: FixtureKind | None = None,
        tracer: otel_trace.Tracer | None = None,
    ) -> None:
        self.trace_id = trace_id
        self.match_id = match_id
        self.moment_id = moment_id
        self.insight_id = insight_id
        self.insight_version = insight_version
        self.state_version = state_version
        self.as_of_session_ms = as_of_session_ms
        self.runner: RunnerKind = runner
        self.trigger_receipt_ms = trigger_receipt_ms
        self.deadline_ms = deadline_ms
        self.model_deployment = model_deployment
        self.fixture: FixtureKind | None = fixture
        self._clock = clock
        self._tracer = tracer or otel_trace.get_tracer("tactistream.agents")
        self._started_ms = clock.now_ms()
        self._steps: list[TraceStep] = []
        self._open: _OpenStep | None = None

    @property
    def steps(self) -> tuple[TraceStep, ...]:
        return tuple(self._steps)

    def start_step(
        self,
        role: StepRole,
        *,
        attempt: int = 1,
        prompt_version: str | None = None,
        budget_ms: int | None = None,
        input_ids: Sequence[str] = (),
        injected_fault: FixtureKind | None = None,
    ) -> int:
        if self._open is not None:
            raise RuntimeError(f"step {self._open.index} ({self._open.role}) is still open")
        index = len(self._steps)
        self._open = _OpenStep(
            index=index,
            role=role,
            attempt=attempt,
            prompt_version=prompt_version,
            started_ms=self._clock.now_ms(),
            budget_ms=budget_ms,
            injected_fault=injected_fault,
            input_ids=list(input_ids),
            span=self._tracer.start_span(f"agent.{role}"),
        )
        return index

    def record_tool_call(self, record: ToolCallRecord) -> None:
        if self._open is None:
            raise RuntimeError("tool call recorded with no open step")
        self._open.tool_calls.append(record)

    def end_step(
        self,
        status: StepStatus,
        *,
        error: str | None = None,
        injected_fault: FixtureKind | None = None,
        analyst_output: AnalystOutput | None = None,
        verdicts: Sequence[Verdict] | None = None,
        producer_output: ProducerOutput | None = None,
        check_failures: Sequence[TraceCheckFailure] | None = None,
        usage: Usage | None = None,
    ) -> TraceStep:
        open_step = self._open
        if open_step is None:
            raise RuntimeError("no open step to end")
        self._open = None
        step = TraceStep(
            index=open_step.index,
            role=open_step.role,
            attempt=open_step.attempt,
            prompt_version=open_step.prompt_version,
            started_ms=open_step.started_ms,
            latency_ms=max(0, self._clock.now_ms() - open_step.started_ms),
            budget_ms=open_step.budget_ms,
            status=status,
            error=error[:200] if error is not None else None,
            injected_fault=injected_fault or open_step.injected_fault,
            input_ids=open_step.input_ids,
            tool_calls=open_step.tool_calls,
            analyst_output=analyst_output,
            verdicts=list(verdicts) if verdicts is not None else None,
            producer_output=producer_output,
            check_failures=list(check_failures) if check_failures is not None else None,
            usage=usage,
        )
        self._steps.append(step)
        self._end_span(open_step.span, step)
        return step

    def finalize(
        self,
        *,
        outcome: RunOutcome,
        claims: Sequence[ClaimRecord],
        fallback_reason: FallbackReason | None = None,
        producer_output: ProducerOutput | None = None,
        check_failures: Sequence[TraceCheckFailure] | None = None,
        released_claim_ids: Sequence[str] | None = None,
        narrative_latency_ms: int | None = None,
    ) -> AgentTrace:
        if self._open is not None:
            self.end_step("failed", error="step did not finish before the run ended")
        return AgentTrace(
            schema_version=SCHEMA_VERSION,
            trace_id=self.trace_id,
            match_id=self.match_id,
            moment_id=self.moment_id,
            insight_id=self.insight_id,
            insight_version=self.insight_version,
            state_version=self.state_version,
            as_of_session_ms=self.as_of_session_ms,
            runner=self.runner,
            outcome=outcome,
            fallback_reason=fallback_reason,
            fixture=self.fixture,
            model_deployment=self.model_deployment,
            trigger_receipt_ms=self.trigger_receipt_ms,
            deadline_ms=self.deadline_ms,
            started_ms=self._started_ms,
            finished_ms=max(self._started_ms, self._clock.now_ms()),
            narrative_latency_ms=narrative_latency_ms,
            steps=list(self._steps),
            claims=[_claim_entry(record) for record in claims],
            producer_output=producer_output,
            check_failures=list(check_failures) if check_failures is not None else None,
            released_claim_ids=list(released_claim_ids) if released_claim_ids is not None else None,
            usage=_total_usage(self._steps),
        )

    def _end_span(self, span: otel_trace.Span, step: TraceStep) -> None:
        attributes: dict[str, Any] = {
            "gen_ai.agent.name": step.role,
            "tactistream.trace_id": self.trace_id,
            "tactistream.match_id": self.match_id,
            "tactistream.moment_id": self.moment_id,
            "tactistream.insight_id": self.insight_id,
            "tactistream.runner": self.runner,
            "tactistream.step.index": step.index,
            "tactistream.step.attempt": step.attempt,
            "tactistream.step.status": step.status,
            "tactistream.step.latency_ms": step.latency_ms,
        }
        if step.role in MODEL_ROLES:
            attributes["gen_ai.operation.name"] = "chat"
            if self.model_deployment is not None:
                attributes["gen_ai.request.model"] = self.model_deployment
        if step.usage is not None:
            if step.usage.tokens_in is not None:
                attributes["gen_ai.usage.input_tokens"] = step.usage.tokens_in
            if step.usage.tokens_out is not None:
                attributes["gen_ai.usage.output_tokens"] = step.usage.tokens_out
        if step.prompt_version is not None:
            attributes["tactistream.prompt_version"] = step.prompt_version
        if step.budget_ms is not None:
            attributes["tactistream.budget_ms"] = step.budget_ms
        if step.injected_fault is not None:
            attributes["tactistream.injected_fault"] = step.injected_fault
        if self.fixture is not None:
            attributes["tactistream.fixture"] = self.fixture
        span.set_attributes(attributes)
        if step.status != "ok" and step.status != "skipped":
            span.set_status(otel_trace.StatusCode.ERROR, step.error or step.status)
        span.end()


def _claim_entry(record: ClaimRecord) -> ClaimTraceEntry:
    return ClaimTraceEntry(
        claim=record.claim,
        attempt=record.attempt,
        precheck=record.precheck,
        model_verdict=record.model_verdict,
        final=record.final,
        status=record.status,
        superseded_by=record.superseded_by,
        injected_fault="bad_claim" if record.injected_fault == "bad_claim" else None,
    )


def _total_usage(steps: Sequence[TraceStep]) -> Usage:
    usages = [step.usage for step in steps if step.usage is not None]
    known = bool(usages) and all(u.tokens_in is not None and u.tokens_out is not None for u in usages)
    return Usage(
        model_calls=sum(u.model_calls for u in usages),
        tokens_in=sum(u.tokens_in or 0 for u in usages) if known else None,
        tokens_out=sum(u.tokens_out or 0 for u in usages) if known else None,
    )


class TraceStore:
    """Finished traces by `(match_id, trace_id)`; with `trace_dir`, also written as JSON files."""

    def __init__(self, trace_dir: Path | None = None) -> None:
        self._trace_dir = trace_dir
        self._traces: dict[tuple[str, str], AgentTrace] = {}

    def put(self, trace: AgentTrace) -> None:
        self._traces[(trace.match_id, trace.trace_id)] = trace
        if self._trace_dir is not None:
            path = self._trace_dir / trace.match_id / f"{trace.trace_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(trace.model_dump_json(exclude_none=True), encoding="utf-8")

    def get(self, match_id: str, trace_id: str) -> AgentTrace | None:
        return self._traces.get((match_id, trace_id))


def trace_envelope(trace: AgentTrace, published_ms: int) -> FeedEnvelope:
    return FeedEnvelope(
        schema_version=SCHEMA_VERSION,
        kind="agent_trace",
        match_id=trace.match_id,
        record_id=trace.trace_id,
        published_ms=published_ms,
        payload=trace,
    )
