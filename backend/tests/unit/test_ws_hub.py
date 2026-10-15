import asyncio

from tactistream.api.ws_hub import WsHub
from tactistream.contracts import FeedEnvelope, MatchEvent, Snapshot, SnapshotPlayback, validate
from tactistream.state.match_state import MatchState

MATCH = "demo-blue-amber-001"
PLAYBACK = SnapshotPlayback(state="paused", speed=1.0, seed=42)


def test_broadcast_assigns_consecutive_seq_from_one(pass_event: MatchEvent) -> None:
    hub = WsHub(MATCH)
    assert hub.head_seq == 0
    seqs = [hub.broadcast("event", pass_event).seq for _ in range(3)]
    assert seqs == [1, 2, 3]
    assert hub.head_seq == 3


async def test_subscribers_receive_the_same_seq_order(pass_event: MatchEvent) -> None:
    hub = WsHub(MATCH)
    a, b = hub.subscribe(), hub.subscribe()
    for _ in range(3):
        hub.broadcast("event", pass_event, server_receipt_ms=17)

    for sub in (a, b):
        received = [await asyncio.wait_for(sub.get(), timeout=1) for _ in range(3)]
        assert [m.seq for m in received if m is not None] == [1, 2, 3]
        assert all(m is not None and m.server_receipt_ms == 17 for m in received)


def test_snapshot_reflects_state_at_head_seq(skeleton: list[FeedEnvelope], pass_event: MatchEvent) -> None:
    state = MatchState()
    for env in skeleton[:4]:
        state.apply(env)
    hub = WsHub(MATCH)
    hub.broadcast("event", pass_event)
    hub.broadcast("event", pass_event)

    message = hub.snapshot_for(state, session_clock_ms=100, playback=PLAYBACK)
    assert (message.type, message.seq) == ("snapshot", 2)
    assert hub.head_seq == 2
    snapshot = message.payload
    assert isinstance(snapshot, Snapshot)
    assert [e.event_id for e in snapshot.events] == [e.event_id for e in state.events]
    assert snapshot.latest_frame == state.latest_frame
    assert snapshot.state_version == state.state_version
    assert (snapshot.insights, snapshot.moments) == ([], [])
    validate(
        "ws_message.schema.json#/$defs/ServerMessage", message.model_dump(mode="json", exclude_none=True)
    )


async def test_slow_subscriber_is_disconnected_without_blocking_others(pass_event: MatchEvent) -> None:
    hub = WsHub(MATCH)
    slow, fast = hub.subscribe(), hub.subscribe()
    for _ in range(1000):
        hub.broadcast("event", pass_event)
    for _ in range(1000):
        await fast.get()

    hub.broadcast("event", pass_event)
    assert slow.closed
    assert not fast.closed
    assert await asyncio.wait_for(slow.get(), timeout=1) is None
    message = await asyncio.wait_for(fast.get(), timeout=1)
    assert message is not None
    assert message.seq == 1001
    assert hub.subscriber_count == 1


async def test_unsubscribe_stops_delivery(pass_event: MatchEvent) -> None:
    hub = WsHub(MATCH)
    sub = hub.subscribe()
    hub.unsubscribe(sub)
    hub.broadcast("event", pass_event)
    assert hub.subscriber_count == 0
    assert await asyncio.wait_for(sub.get(), timeout=1) is None
