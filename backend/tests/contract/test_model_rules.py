import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from tactistream.contracts import (
    AnalystOutput,
    ClientMessage,
    DisplayAckMsg,
    FeedEnvelope,
    InsightBundle,
    InsightPacket,
    MatchEvent,
    MatchMetadata,
    MetricResult,
    NarrativeStatus,
    ResumeMsg,
    ServerMessage,
    Snapshot,
    TrackingFrame,
)
from tactistream.contracts.schema_registry import ContractError, validate

EXAMPLES = Path(__file__).parents[3] / "contracts" / "examples"


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    return data


def dump(model: Any) -> Any:
    return model.model_dump(mode="json", exclude_none=True)


# --- common / ids -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_id", "evt-42"),
        ("player_id", "blue-8"),
        ("match_id", "Demo"),
        ("team_id", "red"),
        ("schema_version", "2.0"),
    ],
)
def test_event_id_formats_match_schema(field: str, value: str) -> None:
    obj = load("event.json")
    obj[field] = value
    with pytest.raises(ContractError):
        validate("event.schema.json", obj)
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(obj)


def test_metric_id_allows_player_suffix() -> None:
    obj = load("metric_result.json")
    obj["metric_id"] = "metric-contribution-0045-blue-09"
    obj["kind"] = "contribution"
    validate("metric_result.schema.json", obj)
    assert MetricResult.model_validate(obj).metric_id == "metric-contribution-0045-blue-09"


def test_point_out_of_bounds_rejected() -> None:
    obj = load("event.json")
    obj["end_m"] = [111.0, 30.0]
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(obj)


def test_models_are_frozen_and_forbid_extra() -> None:
    evt = MatchEvent.model_validate(load("event.json"))
    with pytest.raises(ValidationError):
        evt.sequence = 1  # type: ignore[misc]
    obj = load("event.json")
    obj["surprise"] = 1
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(obj)


# --- event rules --------------------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["end_m", "duration_ms"])
def test_pass_requires_end_and_duration(missing: str) -> None:
    obj = load("event.json")
    del obj[missing]
    with pytest.raises(ContractError):
        validate("event.schema.json", obj)
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(obj)


def test_complete_pass_requires_recipient() -> None:
    obj = load("event.json")
    del obj["recipient_id"]
    with pytest.raises(ContractError):
        validate("event.schema.json", obj)
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(obj)


def test_incomplete_pass_without_recipient_is_valid() -> None:
    obj = load("event.json")
    del obj["recipient_id"]
    obj["outcome"] = "incomplete"
    validate("event.schema.json", obj)
    assert dump(MatchEvent.model_validate(obj)) == obj


def test_null_outcome_is_kept_when_dumping_without_none() -> None:
    obj = load("event.json")
    del obj["recipient_id"]
    obj["outcome"] = None
    validate("event.schema.json", obj)
    out = dump(MatchEvent.model_validate(obj))
    assert out == obj
    validate("event.schema.json", out)


@pytest.mark.parametrize("event_type", ["carry", "shot"])
def test_carry_and_shot_require_end(event_type: str) -> None:
    obj = load("event.json")
    obj["event_type"] = event_type
    obj["outcome"] = None
    del obj["end_m"]
    with pytest.raises(ContractError):
        validate("event.schema.json", obj)
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(obj)


# --- tracking rules -----------------------------------------------------------------------------------


def test_visible_player_without_position_rejected() -> None:
    obj = load("tracking_frame.json")
    obj["players"][0] = {"player_id": "blue-08", "visible": True}
    with pytest.raises(ContractError):
        validate("tracking_frame.schema.json", obj)
    with pytest.raises(ValidationError):
        TrackingFrame.model_validate(obj)


def test_invisible_ball_with_position_rejected() -> None:
    obj = load("tracking_frame.json")
    obj["ball"] = {"visible": False, "pos_m": [1.0, 1.0]}
    with pytest.raises(ContractError):
        validate("tracking_frame.schema.json", obj)
    with pytest.raises(ValidationError):
        TrackingFrame.model_validate(obj)


# --- metric rules -------------------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["value", "unit"])
def test_ok_metric_requires_value_and_unit(missing: str) -> None:
    obj = load("metric_result.json")
    del obj[missing]
    with pytest.raises(ContractError):
        validate("metric_result.schema.json", obj)
    with pytest.raises(ValidationError):
        MetricResult.model_validate(obj)


def test_unavailable_metric_requires_reason() -> None:
    obj = load("metric_result.json")
    obj["status"] = "unavailable"
    del obj["value"]
    del obj["unit"]
    with pytest.raises(ContractError):
        validate("metric_result.schema.json", obj)
    with pytest.raises(ValidationError):
        MetricResult.model_validate(obj)
    obj["unavailable_reason"] = "insufficient_tracking"
    validate("metric_result.schema.json", obj)
    assert dump(MetricResult.model_validate(obj)) == obj


# --- claims -------------------------------------------------------------------------------------------


def test_analyst_output_allows_at_most_two_claims() -> None:
    obj = load("analyst_output.json")
    obj["claims"].append(obj["claims"][0])
    with pytest.raises(ContractError):
        validate("claim.schema.json#/$defs/AnalystOutput", obj)
    with pytest.raises(ValidationError):
        AnalystOutput.model_validate(obj)


# --- insight rules ------------------------------------------------------------------------------------


def test_insight_show_until_must_follow_show_from() -> None:
    obj = load("insight_packet.json")
    obj["render"]["show_until_ms"] = obj["render"]["show_from_ms"]
    with pytest.raises(ValidationError):
        InsightPacket.model_validate(obj)


def test_insight_expiry_not_before_show_until() -> None:
    obj = load("insight_packet.json")
    obj["expires_at_session_ms"] = obj["render"]["show_until_ms"] - 1
    with pytest.raises(ValidationError):
        InsightPacket.model_validate(obj)


# --- envelope -----------------------------------------------------------------------------------------


def test_envelope_payload_is_typed_by_kind() -> None:
    env = FeedEnvelope.model_validate(load("feed_envelope_event.json"))
    assert isinstance(env.payload, MatchEvent)

    meta = {
        "schema_version": "1.0",
        "kind": "metadata",
        "match_id": "demo-blue-amber-001",
        "record_id": "demo-blue-amber-001",
        "published_ms": 0,
        "payload": load("match_metadata.json"),
    }
    validate("feed_envelope.schema.json", meta)
    assert isinstance(FeedEnvelope.model_validate(meta).payload, MatchMetadata)

    frame = {**meta, "kind": "frame", "record_id": "frm-000423", "payload": load("tracking_frame.json")}
    assert isinstance(FeedEnvelope.model_validate(frame).payload, TrackingFrame)

    insight = {**meta, "kind": "insight", "record_id": "ins-0045:1", "payload": load("insight_packet.json")}
    validate("feed_envelope.schema.json", insight)
    parsed = FeedEnvelope.model_validate(insight)
    assert isinstance(parsed.payload, InsightPacket)
    assert dump(parsed) == insight


def test_envelope_rejects_payload_not_matching_kind() -> None:
    obj = load("feed_envelope_event.json")
    obj["kind"] = "frame"
    with pytest.raises(ContractError):
        validate("feed_envelope.schema.json", obj)
    with pytest.raises(ValidationError):
        FeedEnvelope.model_validate(obj)


def test_envelope_untyped_kinds_keep_dict_payload() -> None:
    obj = {
        "schema_version": "1.0",
        "kind": "latency",
        "match_id": "demo-blue-amber-001",
        "record_id": "lat-narrative-ins-0045:1-viewer",
        "published_ms": 1,
        "payload": {"anything": [1, 2]},
    }
    env = FeedEnvelope.model_validate(obj)
    assert env.payload == {"anything": [1, 2]}
    assert dump(env) == obj


def test_envelope_constructed_from_model_instance() -> None:
    evt = MatchEvent.model_validate(load("event.json"))
    env = FeedEnvelope(
        schema_version="1.0",
        kind="event",
        match_id=evt.match_id,
        record_id=evt.event_id,
        published_ms=5,
        payload=evt,
    )
    assert env.payload is evt
    validate("feed_envelope.schema.json", dump(env))


# --- websocket ----------------------------------------------------------------------------------------


def snapshot_obj() -> dict[str, Any]:
    packet = load("insight_packet.json")
    return {
        "metadata": load("match_metadata.json"),
        "state_version": 3,
        "session_clock_ms": 0,
        "events": [load("event.json")],
        "latest_frame": None,
        "moments": [load("candidate_moment.json")],
        "insights": [{"insight_id": "ins-0045", "insight_version": 1, "variants": [packet]}],
        "playback": {"state": "paused", "speed": 1.0, "seed": 42},
    }


@pytest.mark.parametrize(
    ("msg_type", "payload", "payload_type"),
    [
        ("event", load("event.json"), MatchEvent),
        ("frame", load("tracking_frame.json"), TrackingFrame),
        ("metric", load("metric_result.json"), MetricResult),
        ("snapshot", snapshot_obj(), Snapshot),
        (
            "insight",
            {"insight_id": "ins-0045", "insight_version": 1, "variants": [load("insight_packet.json")]},
            InsightBundle,
        ),
        (
            "narrative_status",
            {"moment_id": "mom-0042", "stage": "fallback", "fallback_reason": "output_check_failed"},
            NarrativeStatus,
        ),
        ("heartbeat", {"session_clock_ms": 1200}, dict),
    ],
)
def test_server_message_round_trip(msg_type: str, payload: dict[str, Any], payload_type: type) -> None:
    obj = {"type": msg_type, "seq": 7, "match_id": "demo-blue-amber-001", "payload": payload}
    validate("ws_message.schema.json#/$defs/ServerMessage", obj)
    msg = ServerMessage.model_validate(obj)
    assert isinstance(msg.payload, payload_type)
    out = dump(msg)
    assert out == obj
    validate("ws_message.schema.json#/$defs/ServerMessage", out)


def test_snapshot_keeps_null_latest_frame() -> None:
    out = dump(Snapshot.model_validate(snapshot_obj()))
    assert out["latest_frame"] is None


def test_client_message_discriminated_on_type() -> None:
    adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
    assert isinstance(adapter.validate_python({"type": "resume", "last_seq": -1}), ResumeMsg)
    ack = {"type": "display_ack", "target_kind": "insight", "target_id": "ins-0042", "server_seq": 9}
    validate("ws_message.schema.json#/$defs/ClientMessage", ack)
    assert isinstance(adapter.validate_python(ack), DisplayAckMsg)
    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "resume", "last_seq": -2})
    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "bogus"})
