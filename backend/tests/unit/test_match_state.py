import random

import pytest

from tactistream.contracts import FeedEnvelope, InsightPacket
from tactistream.state.match_state import MatchState
from tactistream.transport.fixtures import load_fixture, skeleton_fixture_path


@pytest.fixture(scope="module")
def records() -> list[FeedEnvelope]:
    return load_fixture(skeleton_fixture_path())


def find(records: list[FeedEnvelope], record_id: str) -> FeedEnvelope:
    return next(r for r in records if r.record_id == record_id)


def test_each_accepted_record_increments_state_version(records: list[FeedEnvelope]) -> None:
    state = MatchState()
    assert state.state_version == 0

    delta = state.apply(records[0])
    assert (delta.state_version, delta.duplicate) == (1, False)
    assert delta.new_metadata is not None
    assert state.metadata == records[0].payload

    for expected, record_id in enumerate(["evt-0040", "evt-0041"], start=2):
        delta = state.apply(find(records, record_id))
        assert delta.state_version == expected
        assert [e.event_id for e in delta.new_events] == [record_id]
    assert state.state_version == 3


def test_duplicate_is_flagged_and_does_not_change_version(records: list[FeedEnvelope]) -> None:
    state = MatchState()
    state.apply(records[0])
    state.apply(find(records, "evt-0042"))

    delta = state.apply(find(records, "evt-0042"))
    assert delta.duplicate is True
    assert delta.new_events == []
    assert delta.state_version == state.state_version == 2
    assert [e.event_id for e in state.events] == ["evt-0042"]


def test_events_are_kept_sorted_by_sequence(records: list[FeedEnvelope]) -> None:
    state = MatchState()
    for record_id in ["evt-0042", "evt-0040", "evt-0041"]:
        state.apply(find(records, record_id))
    assert [e.sequence for e in state.events] == [40, 41, 42]


def test_server_receipt_ms_is_preserved_on_the_stored_record(records: list[FeedEnvelope]) -> None:
    state = MatchState()
    stamped = find(records, "evt-0042").model_copy(update={"server_receipt_ms": 1_792_000_003_012})
    delta = state.apply(stamped)
    assert delta.server_receipt_ms == 1_792_000_003_012
    stored = state.envelope("event", "evt-0042")
    assert stored is not None
    assert stored.server_receipt_ms == 1_792_000_003_012


def test_latest_frame_does_not_regress_on_an_older_frame(records: list[FeedEnvelope]) -> None:
    state = MatchState()
    newer = state.apply(find(records, "frm-000011"))
    older = state.apply(find(records, "frm-000010"))
    assert newer.new_frame is not None
    assert older.new_frame is None
    assert older.duplicate is False
    assert state.latest_frame is not None
    assert state.latest_frame.frame_id == "frm-000011"
    assert state.state_version == 2


def test_kinds_outside_live_state_are_ignored(records: list[FeedEnvelope]) -> None:
    packet = InsightPacket.model_validate_json(
        (skeleton_fixture_path().parents[2] / "contracts/examples/insight_packet.json").read_text()
    )
    envelope = FeedEnvelope(
        schema_version="1.0",
        kind="insight",
        match_id="demo-blue-amber-001",
        record_id="ins-0045:1",
        published_ms=0,
        payload=packet,
    )
    state = MatchState()
    delta = state.apply(envelope)
    assert (delta.state_version, delta.duplicate, delta.new_events) == (0, False, [])


def test_state_hash_is_identical_for_shuffled_input_with_duplicates(records: list[FeedEnvelope]) -> None:
    in_order = MatchState()
    for record in records:
        in_order.apply(record)

    noisy = records + records[::3]
    random.Random(42).shuffle(noisy)
    shuffled = MatchState()
    for record in noisy:
        shuffled.apply(record)

    assert shuffled.state_hash() == in_order.state_hash()
    assert shuffled.state_version == in_order.state_version == len(records)
    assert len(in_order.state_hash()) == 64


def test_state_hash_changes_when_content_changes(records: list[FeedEnvelope]) -> None:
    full = MatchState()
    partial = MatchState()
    for record in records:
        full.apply(record)
        if record.record_id != "evt-0043":
            partial.apply(record)
    assert full.state_hash() != partial.state_hash()
