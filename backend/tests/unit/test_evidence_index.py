import pytest

from tactistream.api.evidence import EvidenceIndex
from tactistream.contracts import FeedEnvelope, MatchEvent, MatchMetadata, TrackingFrame
from tactistream.metrics.forward_progress import compute_forward_progress


def test_records_resolve_by_their_id_and_kind(
    pass_event: MatchEvent, metadata: MatchMetadata, skeleton: list[FeedEnvelope]
) -> None:
    frame = next(env.payload for env in skeleton if isinstance(env.payload, TrackingFrame))
    metric = compute_forward_progress(pass_event, metadata, state_version=1)
    index = EvidenceIndex()
    index.add("event", pass_event, session_clock_ms=3000)
    index.add("frame", frame, session_clock_ms=0)
    index.add("metric", metric, session_clock_ms=3000)

    event_entry = index.resolve("evt-0042", as_of_ms=3000)
    assert event_entry is not None
    assert (event_entry.kind, event_entry.record) == ("event", pass_event)
    frame_entry = index.resolve("frm-000000", as_of_ms=0)
    assert frame_entry is not None
    assert frame_entry.kind == "frame"
    metric_entry = index.resolve("metric-forward_progress-0042", as_of_ms=5000)
    assert metric_entry is not None
    assert (metric_entry.kind, metric_entry.record) == ("metric", metric)
    assert "evt-0042" in index


def test_future_record_is_not_resolvable_before_its_time(pass_event: MatchEvent) -> None:
    index = EvidenceIndex()
    index.add("event", pass_event, session_clock_ms=3000)
    assert index.resolve("evt-0042", as_of_ms=2999) is None
    assert index.resolve("evt-0042", as_of_ms=3000) is not None


def test_unknown_id_is_none_and_clear_forgets_everything(pass_event: MatchEvent) -> None:
    index = EvidenceIndex()
    assert index.resolve("evt-9999", as_of_ms=10_000) is None
    index.add("event", pass_event, session_clock_ms=3000)
    index.clear()
    assert index.resolve("evt-0042", as_of_ms=10_000) is None


def test_record_kind_must_match_declared_kind(pass_event: MatchEvent) -> None:
    with pytest.raises(TypeError):
        EvidenceIndex().add("metric", pass_event, session_clock_ms=0)
