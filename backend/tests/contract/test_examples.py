import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from tactistream.contracts import (
    AnalystOutput,
    CandidateMoment,
    FeedEnvelope,
    InsightPacket,
    LatencySample,
    MatchEvent,
    MatchMetadata,
    MetricResult,
    Recap,
    TrackingFrame,
)
from tactistream.contracts.schema_registry import ContractError, validate

EXAMPLES = Path(__file__).parents[3] / "contracts" / "examples"

CASES: list[tuple[str, str, type[BaseModel]]] = [
    ("match_metadata.json", "match_metadata.schema.json", MatchMetadata),
    ("event.json", "event.schema.json", MatchEvent),
    ("tracking_frame.json", "tracking_frame.schema.json", TrackingFrame),
    ("metric_result.json", "metric_result.schema.json", MetricResult),
    ("candidate_moment.json", "candidate_moment.schema.json", CandidateMoment),
    ("analyst_output.json", "claim.schema.json#/$defs/AnalystOutput", AnalystOutput),
    ("insight_packet.json", "insight_packet.schema.json", InsightPacket),
    ("recap.json", "recap.schema.json", Recap),
    ("feed_envelope_event.json", "feed_envelope.schema.json", FeedEnvelope),
    ("latency_sample.json", "latency_sample.schema.json", LatencySample),
]


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    return data


def test_every_example_is_covered() -> None:
    assert {p.name for p in EXAMPLES.glob("*.json")} == {name for name, _, _ in CASES}


@pytest.mark.parametrize(("example", "schema", "model"), CASES, ids=[c[0] for c in CASES])
def test_example_validates_against_schema(example: str, schema: str, model: type[BaseModel]) -> None:
    validate(schema, load(example))


@pytest.mark.parametrize(("example", "schema", "model"), CASES, ids=[c[0] for c in CASES])
def test_example_round_trips_through_model(example: str, schema: str, model: type[BaseModel]) -> None:
    obj = load(example)
    assert model.model_validate(obj).model_dump(mode="json", exclude_none=True) == obj


def test_invisible_player_with_position_is_rejected() -> None:
    frame = load("tracking_frame.json")
    frame["players"][4] = {"player_id": "amber-05", "visible": False, "pos_m": [10.0, 10.0]}
    with pytest.raises(ContractError):
        validate("tracking_frame.schema.json", frame)
    with pytest.raises(ValidationError):
        TrackingFrame.model_validate(frame)


def test_unavailable_metric_with_value_is_rejected() -> None:
    metric = copy.deepcopy(load("metric_result.json"))
    metric["status"] = "unavailable"
    metric["unavailable_reason"] = "insufficient_tracking"
    assert "value" in metric
    with pytest.raises(ContractError):
        validate("metric_result.schema.json", metric)
    with pytest.raises(ValidationError):
        MetricResult.model_validate(metric)
