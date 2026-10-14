import pytest

from tactistream.contracts import AttackDirection, MatchEvent, MatchMetadata, PeriodSpec, validate
from tactistream.metrics.forward_progress import compute_forward_progress


def test_completed_pass_progress_along_blue_attack_direction(
    pass_event: MatchEvent, metadata: MatchMetadata
) -> None:
    metric = compute_forward_progress(pass_event, metadata, state_version=7)

    assert metric.kind == "forward_progress"
    assert metric.metric_id == "metric-forward_progress-0042"
    assert metric.status == "ok"
    assert metric.value == 13.1
    assert metric.unit == "m"
    assert metric.definition_version == "forward_progress.v1"
    assert metric.inputs.event_ids == ["evt-0042"]
    assert metric.inputs.frame_ids == []
    assert metric.subject_ids == ["blue-08", "blue-11"]
    assert (metric.window.start_ms, metric.window.end_ms) == (3000, 3900)
    assert metric.state_version == 7
    assert metric.match_id == "demo-blue-amber-001"
    validate("metric_result.schema.json", metric.model_dump(mode="json", exclude_none=True))


def test_reversed_attack_direction_negates_progress(pass_event: MatchEvent, metadata: MatchMetadata) -> None:
    flipped = metadata.model_copy(
        update={"periods": [PeriodSpec(period=1, attack_direction=AttackDirection(blue=-1, amber=1))]}
    )
    assert compute_forward_progress(pass_event, flipped, state_version=1).value == -13.1


def test_pass_without_outcome_is_still_measured(pass_event: MatchEvent, metadata: MatchMetadata) -> None:
    attempt = pass_event.model_copy(update={"outcome": None, "recipient_id": None})
    metric = compute_forward_progress(attempt, metadata, state_version=1)
    assert metric.value == 13.1
    assert metric.subject_ids == ["blue-08"]


def test_non_pass_event_is_rejected(events: dict[str, MatchEvent], metadata: MatchMetadata) -> None:
    with pytest.raises(ValueError, match="pass"):
        compute_forward_progress(events["evt-0041"], metadata, state_version=1)


def test_period_without_attack_direction_is_rejected(pass_event: MatchEvent, metadata: MatchMetadata) -> None:
    second_half = pass_event.model_copy(update={"period": 2})
    with pytest.raises(ValueError, match="period 2"):
        compute_forward_progress(second_half, metadata, state_version=1)
