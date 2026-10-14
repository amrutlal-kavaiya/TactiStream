import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tactistream.contracts import LatencySample
from tactistream.contracts.schema_registry import ContractError, validate

EXAMPLE = Path(__file__).parents[3] / "contracts" / "examples" / "latency_sample.json"
SCHEMA = "latency_sample.schema.json"


def example() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    return data


def narrative_fallback() -> dict[str, Any]:
    sample = copy.deepcopy(example())
    sample.update(
        kind="narrative",
        outcome="fallback",
        fallback_reason="timeout",
        target_id="ins-0045:1",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        sample_id="lat-narrative-ins-0045:1-v-1a2b3c4d",
    )
    return sample


def test_example_validates_and_round_trips() -> None:
    obj = example()
    validate(SCHEMA, obj)
    assert LatencySample.model_validate(obj).model_dump(mode="json", exclude_none=True) == obj


def test_narrative_fallback_with_reason_is_accepted() -> None:
    obj = narrative_fallback()
    validate(SCHEMA, obj)
    assert LatencySample.model_validate(obj).fallback_reason == "timeout"


def test_narrative_fallback_without_reason_is_rejected_by_both() -> None:
    obj = narrative_fallback()
    del obj["fallback_reason"]
    with pytest.raises(ContractError):
        validate(SCHEMA, obj)
    with pytest.raises(ValidationError, match="fallback_reason"):
        LatencySample.model_validate(obj)


def test_negative_value_is_rejected_by_both() -> None:
    obj = example()
    obj["value_ms"] = -1
    with pytest.raises(ContractError):
        validate(SCHEMA, obj)
    with pytest.raises(ValidationError):
        LatencySample.model_validate(obj)


@pytest.mark.parametrize(("field", "value"), [("kind", "recap"), ("outcome", "dropped"), ("extra", 1)])
def test_unknown_values_are_rejected_by_both(field: str, value: object) -> None:
    obj = example()
    obj[field] = value
    with pytest.raises(ContractError):
        validate(SCHEMA, obj)
    with pytest.raises(ValidationError):
        LatencySample.model_validate(obj)
