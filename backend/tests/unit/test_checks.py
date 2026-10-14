import pytest

from tactistream.agents.checks import CheckFailure, check_packet
from tactistream.api.evidence import EvidenceIndex
from tactistream.contracts import InsightPacket, MatchEvent, MatchMetadata, RenderSpec
from tactistream.metrics.forward_progress import compute_forward_progress

FAN_EN = "Blue 8 played a forward pass to Blue 11 (13.1 m forward)."
FAN_HI = "ब्लू 8 ने ब्लू 11 को आगे की ओर पास दिया (13.1 मी आगे)।"


@pytest.fixture
def evidence(pass_event: MatchEvent, metadata: MatchMetadata) -> EvidenceIndex:
    index = EvidenceIndex()
    index.add("event", pass_event, session_clock_ms=3000)
    index.add(
        "metric", compute_forward_progress(pass_event, metadata, state_version=5), session_clock_ms=3000
    )
    return index


@pytest.fixture
def packet() -> InsightPacket:
    return InsightPacket(
        schema_version="1.0",
        insight_id="ins-0042",
        insight_version=1,
        match_id="demo-blue-amber-001",
        moment_id="mom-0042",
        state_version=5,
        as_of_session_ms=3000,
        mode="fan",
        language="en",
        source_kind="synthetic",
        claim_status="verified_fact",
        title="Forward pass",
        body=FAN_EN,
        labels=["synthetic"],
        evidence_ids=["evt-0042", "metric-forward_progress-0042"],
        claim_ids=[],
        render=RenderSpec(
            clock="session_clock_ms",
            show_from_ms=3900,
            show_until_ms=9900,
            priority=3,
            panel="lower_third",
            annotations=[],
        ),
        expires_at_session_ms=33900,
        trace_id="0" * 32,
    )


def codes(failures: list[CheckFailure]) -> list[str]:
    return [f.code for f in failures]


def test_valid_packet_passes(packet: InsightPacket, evidence: EvidenceIndex, metadata: MatchMetadata) -> None:
    assert check_packet(packet, evidence, metadata, now_ms=3000) == []


def test_valid_hindi_and_analyst_packets_pass(
    packet: InsightPacket, evidence: EvidenceIndex, metadata: MatchMetadata
) -> None:
    hindi = packet.model_copy(update={"language": "hi", "title": "आगे की ओर पास", "body": FAN_HI})
    analyst = packet.model_copy(
        update={"mode": "analyst", "body": f"{FAN_EN} Progress along attack axis: 13.1 m (evt-0042)."}
    )
    assert check_packet(hindi, evidence, metadata, now_ms=3000) == []
    assert check_packet(analyst, evidence, metadata, now_ms=3000) == []


def test_number_absent_from_evidence_is_unsupported(
    packet: InsightPacket, evidence: EvidenceIndex, metadata: MatchMetadata
) -> None:
    bad = packet.model_copy(update={"body": FAN_EN.replace("13.1", "14.0")})
    failures = check_packet(bad, evidence, metadata, now_ms=3000)
    assert codes(failures) == ["unsupported_number"]
    assert "14.0" in failures[0].detail


def test_number_in_title_is_checked_too(
    packet: InsightPacket, evidence: EvidenceIndex, metadata: MatchMetadata
) -> None:
    bad = packet.model_copy(update={"title": "Forward pass of 20 m"})
    assert codes(check_packet(bad, evidence, metadata, now_ms=3000)) == ["unsupported_number"]


def test_player_absent_from_evidence_subjects_is_unsupported(
    packet: InsightPacket, evidence: EvidenceIndex, metadata: MatchMetadata
) -> None:
    bad = packet.model_copy(update={"body": FAN_EN.replace("Blue 11", "Blue 7")})
    failures = check_packet(bad, evidence, metadata, now_ms=3000)
    assert codes(failures) == ["unsupported_player"]
    assert "Blue 7" in failures[0].detail


def test_evidence_id_not_in_index_is_unknown(
    packet: InsightPacket, evidence: EvidenceIndex, metadata: MatchMetadata
) -> None:
    bad = packet.model_copy(update={"evidence_ids": [*packet.evidence_ids, "evt-0099"]})
    failures = check_packet(bad, evidence, metadata, now_ms=3000)
    assert codes(failures) == ["unknown_evidence"]
    assert "evt-0099" in failures[0].detail


def test_evidence_not_yet_available_at_now_is_unknown(
    packet: InsightPacket, evidence: EvidenceIndex, metadata: MatchMetadata
) -> None:
    assert "unknown_evidence" in codes(check_packet(packet, evidence, metadata, now_ms=2999))


def test_evidence_id_in_text_must_be_cited(
    packet: InsightPacket, evidence: EvidenceIndex, metadata: MatchMetadata
) -> None:
    bad = packet.model_copy(update={"body": f"{FAN_EN} See evt-0043."})
    assert codes(check_packet(bad, evidence, metadata, now_ms=3000)) == ["unknown_evidence"]


def test_show_until_not_after_show_from_is_invalid_timing(
    packet: InsightPacket, evidence: EvidenceIndex, metadata: MatchMetadata
) -> None:
    bad = packet.model_copy(update={"render": packet.render.model_copy(update={"show_until_ms": 3900})})
    assert codes(check_packet(bad, evidence, metadata, now_ms=3000)) == ["invalid_timing"]


def test_packet_already_expired_at_now(
    packet: InsightPacket, evidence: EvidenceIndex, metadata: MatchMetadata
) -> None:
    assert codes(check_packet(packet, evidence, metadata, now_ms=33901)) == ["expired"]
    assert check_packet(packet, evidence, metadata, now_ms=33900) == []
