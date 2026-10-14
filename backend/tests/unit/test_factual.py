import pytest

from tactistream.agents.checks import check_packet
from tactistream.api.evidence import EvidenceIndex
from tactistream.contracts import InsightBundle, MatchEvent, MatchMetadata, MetricResult, validate
from tactistream.metrics.forward_progress import compute_forward_progress
from tactistream.narrative.factual import build_fact_bundle

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"


@pytest.fixture
def metric(pass_event: MatchEvent, metadata: MatchMetadata) -> MetricResult:
    return compute_forward_progress(pass_event, metadata, state_version=12)


@pytest.fixture
def bundle(pass_event: MatchEvent, metric: MetricResult, metadata: MatchMetadata) -> InsightBundle:
    return build_fact_bundle(
        pass_event, metric, metadata, state_version=12, trace_id=TRACE, now_session_ms=3000
    )


def test_bundle_has_four_variants(bundle: InsightBundle) -> None:
    assert (bundle.insight_id, bundle.insight_version) == ("ins-0042", 1)
    assert [(v.mode, v.language) for v in bundle.variants] == [
        ("fan", "en"),
        ("fan", "hi"),
        ("analyst", "en"),
        ("analyst", "hi"),
    ]


def test_variant_fields_follow_the_fact_path_rules(bundle: InsightBundle) -> None:
    for packet in bundle.variants:
        assert packet.insight_id == "ins-0042"
        assert packet.moment_id == "mom-0042"
        assert packet.claim_status == "verified_fact"
        assert packet.labels == ["synthetic"]
        assert packet.source_kind == "synthetic"
        assert packet.evidence_ids == ["evt-0042", "metric-forward_progress-0042"]
        assert packet.state_version == 12
        assert packet.as_of_session_ms == 3000
        assert packet.trace_id == TRACE
        assert packet.render.show_from_ms == 3900
        assert packet.render.show_until_ms == 9900
        assert packet.expires_at_session_ms == 33900
        assert (packet.render.panel, packet.render.priority, packet.render.annotations) == (
            "lower_third",
            3,
            [],
        )


def test_fan_english_text(bundle: InsightBundle) -> None:
    fan_en = bundle.variants[0]
    assert fan_en.title == "Forward pass"
    assert fan_en.body == "Blue 8 played a forward pass to Blue 11 (13.1 m forward)."


def test_bundle_and_variants_validate_against_schemas(bundle: InsightBundle) -> None:
    validate("ws_message.schema.json#/$defs/InsightBundle", bundle.model_dump(mode="json", exclude_none=True))


def test_every_variant_passes_output_checks(
    bundle: InsightBundle, pass_event: MatchEvent, metric: MetricResult, metadata: MatchMetadata
) -> None:
    evidence = EvidenceIndex()
    evidence.add("event", pass_event, session_clock_ms=3000)
    evidence.add("metric", metric, session_clock_ms=3000)
    for packet in bundle.variants:
        assert check_packet(packet, evidence, metadata, now_ms=3000) == []


def test_incomplete_pass_is_rejected(
    pass_event: MatchEvent, metric: MetricResult, metadata: MatchMetadata
) -> None:
    attempt = pass_event.model_copy(update={"outcome": "incomplete"})
    with pytest.raises(ValueError, match="outcome incomplete"):
        build_fact_bundle(attempt, metric, metadata, state_version=12, trace_id=TRACE, now_session_ms=3000)


@pytest.mark.parametrize("end_x", [50.0, 58.1])
def test_non_positive_progress_is_rejected(
    pass_event: MatchEvent, metadata: MatchMetadata, end_x: float
) -> None:
    backward = pass_event.model_copy(update={"end_m": (end_x, 28.0)})
    metric = compute_forward_progress(backward, metadata, state_version=12)
    with pytest.raises(ValueError, match="forward progress"):
        build_fact_bundle(backward, metric, metadata, state_version=12, trace_id=TRACE, now_session_ms=3000)


def attempted(pass_event: MatchEvent) -> MatchEvent:
    return pass_event.model_copy(update={"outcome": None, "recipient_id": None})


def test_attempted_pass_gets_an_attempted_card_without_numbers(
    pass_event: MatchEvent, metadata: MatchMetadata
) -> None:
    event = attempted(pass_event)
    metric = compute_forward_progress(event, metadata, state_version=12)
    bundle = build_fact_bundle(event, metric, metadata, state_version=12, trace_id=TRACE, now_session_ms=3000)

    fan_en = bundle.variants[0]
    assert (fan_en.title, fan_en.body) == ("Pass attempted", "Blue 8 attempted a forward pass.")
    assert len(bundle.variants) == 4
    assert all(p.evidence_ids == ["evt-0042", "metric-forward_progress-0042"] for p in bundle.variants)
    assert all("13.1" not in p.body for p in bundle.variants)
    evidence = EvidenceIndex()
    evidence.add("event", event, session_clock_ms=3000)
    evidence.add("metric", metric, session_clock_ms=3000)
    assert all(check_packet(p, evidence, metadata, now_ms=3000) == [] for p in bundle.variants)


def test_backward_attempted_pass_is_rejected(pass_event: MatchEvent, metadata: MatchMetadata) -> None:
    event = attempted(pass_event).model_copy(update={"end_m": (50.0, 28.0)})
    metric = compute_forward_progress(event, metadata, state_version=12)
    with pytest.raises(ValueError, match="forward progress"):
        build_fact_bundle(event, metric, metadata, state_version=12, trace_id=TRACE, now_session_ms=3000)
