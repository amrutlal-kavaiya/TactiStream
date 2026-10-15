import asyncio
from collections.abc import AsyncIterator

from tactistream.contracts import FeedEnvelope, MatchEvent, Provenance
from tactistream.transport.bus import FeedBus
from tactistream.transport.memory_bus import InMemoryBus


def envelope(match_id: str, sequence: int) -> FeedEnvelope:
    event = MatchEvent(
        schema_version="1.0",
        match_id=match_id,
        event_id=f"evt-{sequence:04d}",
        sequence=sequence,
        period=1,
        period_clock_ms=sequence * 100,
        session_clock_ms=sequence * 100,
        event_type="kickoff",
        team_id="blue",
        player_id="blue-10",
        start_m=(52.5, 34.0),
        outcome=None,
        source=Provenance(kind="synthetic"),
    )
    return FeedEnvelope(
        schema_version="1.0",
        kind="event",
        match_id=match_id,
        record_id=event.event_id,
        published_ms=1_000 + sequence,
        payload=event,
    )


async def take(it: AsyncIterator[FeedEnvelope], n: int) -> list[FeedEnvelope]:
    async def collect() -> list[FeedEnvelope]:
        return [await anext(it) for _ in range(n)]

    return await asyncio.wait_for(collect(), timeout=1)


def keys(envs: list[FeedEnvelope]) -> list[tuple[str, str]]:
    return [(e.match_id, e.record_id) for e in envs]


async def test_each_consumer_group_receives_all_envelopes_in_publish_order() -> None:
    bus: FeedBus = InMemoryBus()
    live = bus.subscribe("live-state")
    fabric = bus.subscribe("fabric")
    published = [
        envelope("match-a", 1),
        envelope("match-b", 1),
        envelope("match-a", 2),
        envelope("match-b", 2),
    ]
    for env in published:
        await bus.publish(env)

    assert keys(await take(live, 4)) == keys(published)
    assert keys(await take(fabric, 4)) == keys(published)


async def test_late_subscriber_receives_only_later_envelopes() -> None:
    bus = InMemoryBus()
    early = bus.subscribe("live-state")
    await bus.publish(envelope("match-a", 1))
    late = bus.subscribe("fabric")
    await bus.publish(envelope("match-a", 2))

    assert keys(await take(early, 2)) == [("match-a", "evt-0001"), ("match-a", "evt-0002")]
    assert keys(await take(late, 1)) == [("match-a", "evt-0002")]
    await bus.close()
    assert [e async for e in late] == []


async def test_duplicate_publish_is_delivered_twice() -> None:
    bus = InMemoryBus()
    live = bus.subscribe("live-state")
    env = envelope("match-a", 7)
    await bus.publish(env)
    await bus.publish(env)
    assert keys(await take(live, 2)) == [("match-a", "evt-0007"), ("match-a", "evt-0007")]


async def test_close_ends_iterators() -> None:
    bus = InMemoryBus()
    live = bus.subscribe("live-state")
    received: list[FeedEnvelope] = []

    async def consume() -> None:
        async for env in live:
            received.append(env)

    consumer = asyncio.create_task(consume())
    await bus.publish(envelope("match-a", 1))
    await bus.close()
    await asyncio.wait_for(consumer, timeout=1)
    assert keys(received) == [("match-a", "evt-0001")]


async def test_subscribe_after_close_yields_nothing() -> None:
    bus = InMemoryBus()
    await bus.close()
    assert [e async for e in bus.subscribe("live-state")] == []
