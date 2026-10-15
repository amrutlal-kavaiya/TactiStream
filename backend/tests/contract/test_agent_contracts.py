import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tactistream.contracts import (
    AnalystOutput,
    FeedEnvelope,
    InsightPacket,
    NarrativeStatus,
    SlotValue,
)
from tactistream.contracts.schema_registry import ContractError, validate
from tactistream.contracts.trace import AgentTrace, TraceStep

EXAMPLES = Path(__file__).parents[3] / "contracts" / "examples"


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    return data


def dump(model: Any) -> Any:
    return model.model_dump(mode="json", exclude_none=True)


def test_agent_trace_example_validates_and_round_trips() -> None:
    trace = load("agent_trace.json")
    validate("agent_trace.schema.json", trace)
    assert dump(AgentTrace.model_validate(trace)) == trace


def test_agent_trace_example_is_the_complete_bad_claim_run() -> None:
    trace = AgentTrace.model_validate(load("agent_trace.json"))
    assert trace.fixture == "bad_claim"
    assert [step.role for step in trace.steps] == [
        "gate",
        "analyst",
        "verifier_precheck",
        "verifier",
        "analyst",
        "verifier_precheck",
        "verifier",
        "producer",
        "checks",
    ]
    revised = next(entry for entry in trace.claims if entry.status == "revised")
    assert revised.claim.claim_id == "clm-0045-2"
    assert revised.superseded_by == "clm-0045-3"
    assert revised.final is not None
    assert {"template_kind_mismatch", "value_mismatch"} <= set(revised.final.reason_codes)
    assert trace.released_claim_ids == ["clm-0045-3", "clm-0045-1"]


def test_metric_slot_carries_asserted_value_and_unit() -> None:
    slot = {"kind": "metric", "metric_id": "metric-channel-0042", "value": 3.4, "unit": "m"}
    validate("claim.schema.json#/$defs/SlotValue", slot)
    assert SlotValue.model_validate(slot).value == 3.4
    bad = {**slot, "unit": "furlong"}
    with pytest.raises(ContractError):
        validate("claim.schema.json#/$defs/SlotValue", bad)
    with pytest.raises(ValidationError):
        SlotValue.model_validate(bad)


def test_analyst_output_example_has_values_on_metric_slots() -> None:
    output = AnalystOutput.model_validate(load("analyst_output.json"))
    metric_slots = [s for c in output.claims for s in c.slots.values() if s.kind == "metric"]
    assert metric_slots
    assert all(s.value is not None and s.unit == "m" for s in metric_slots)


def test_packet_with_demo_fixture_label_validates() -> None:
    packet = load("insight_packet.json")
    packet["labels"] = [*packet.get("labels", []), "demo_fixture"]
    validate("insight_packet.schema.json", packet)
    assert "demo_fixture" in (InsightPacket.model_validate(packet).labels or [])


def test_fallback_status_with_no_supported_claim_validates() -> None:
    status = {"moment_id": "mom-0045", "stage": "fallback", "fallback_reason": "no_supported_claim"}
    validate("ws_message.schema.json#/$defs/NarrativeStatus", status)
    assert NarrativeStatus.model_validate(status).fallback_reason == "no_supported_claim"


def test_trace_step_with_private_reasoning_is_rejected() -> None:
    trace = load("agent_trace.json")
    trace["steps"][1]["reasoning"] = "I think the run forced the defender"
    with pytest.raises(ContractError):
        validate("agent_trace.schema.json", trace)
    with pytest.raises(ValidationError):
        TraceStep.model_validate(trace["steps"][1])


def test_fallback_trace_needs_a_reason() -> None:
    trace = load("agent_trace.json")
    trace["outcome"] = "fallback"
    with pytest.raises(ValidationError, match="fallback_reason"):
        AgentTrace.model_validate(trace)


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        ("fallback", "insufficient_tracking"),
        ("released", "timeout"),
        ("abstained", None),
        ("abstained", "timeout"),
    ],
)
def test_outcome_and_fallback_reason_must_agree(outcome: str, reason: str | None) -> None:
    trace = load("agent_trace.json")
    trace["outcome"] = outcome
    trace.pop("fallback_reason", None)
    if reason is not None:
        trace["fallback_reason"] = reason
    with pytest.raises(ValidationError):
        AgentTrace.model_validate(trace)


def test_released_expired_trace_is_allowed() -> None:
    trace = load("agent_trace.json")
    trace["fallback_reason"] = "expired"
    assert AgentTrace.model_validate(trace).fallback_reason == "expired"


def test_finish_before_start_is_rejected() -> None:
    trace = load("agent_trace.json")
    trace["finished_ms"] = trace["started_ms"] - 1
    with pytest.raises(ValidationError, match="finished_ms"):
        AgentTrace.model_validate(trace)


def test_step_indices_must_be_contiguous() -> None:
    trace = load("agent_trace.json")
    trace["steps"][3]["index"] = 7
    with pytest.raises(ValidationError, match="index"):
        AgentTrace.model_validate(trace)


def test_released_claims_must_be_approved() -> None:
    trace = load("agent_trace.json")
    trace["released_claim_ids"] = ["clm-0045-2"]
    with pytest.raises(ValidationError, match="clm-0045-2"):
        AgentTrace.model_validate(trace)


def test_feed_envelope_parses_agent_trace_payload() -> None:
    trace = load("agent_trace.json")
    envelope = {
        "schema_version": "1.0",
        "kind": "agent_trace",
        "match_id": trace["match_id"],
        "record_id": trace["trace_id"],
        "published_ms": trace["finished_ms"],
        "payload": trace,
    }
    validate("feed_envelope.schema.json", envelope)
    parsed = FeedEnvelope.model_validate(envelope)
    assert isinstance(parsed.payload, AgentTrace)
    assert dump(parsed) == envelope
    broken = copy.deepcopy(envelope)
    del broken["payload"]["steps"]
    with pytest.raises(ContractError):
        validate("feed_envelope.schema.json", broken)
    with pytest.raises(ValidationError):
        FeedEnvelope.model_validate(broken)
