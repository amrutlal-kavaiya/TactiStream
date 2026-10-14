import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from support.fake_eventhubs import FakeHub

from tactistream.contracts import FeedEnvelope
from tactistream.transport.bus import FeedBus
from tactistream.transport.eventhubs_bus import EventHubsBus

NAMESPACE = "tactistream.servicebus.windows.net"
HUB = "tactistream-feed"
CRED = object()


def make_bus(hub: FakeHub, **kw: object) -> EventHubsBus:
    return EventHubsBus(NAMESPACE, HUB, CRED, client_factory=hub, **kw)  # type: ignore[arg-type]


def dump(envelope: FeedEnvelope) -> dict[str, object]:
    return envelope.model_dump(mode="json", exclude_none=True)


async def take(it: AsyncIterator[FeedEnvelope], n: int) -> list[FeedEnvelope]:
    async def collect() -> list[FeedEnvelope]:
        return [await anext(it) for _ in range(n)]

    return await asyncio.wait_for(collect(), timeout=1)


async def test_publish_sends_json_body_with_match_id_partition_key(skeleton: list[FeedEnvelope]) -> None:
    hub = FakeHub()
    bus: FeedBus = make_bus(hub)
    for envelope in skeleton[:2]:
        await bus.publish(envelope)

    assert [(json.loads(body), key) for body, key in hub.sent] == [
        (dump(e), e.match_id) for e in skeleton[:2]
    ]
    assert [(ns, name, cred) for ns, name, cred, _ in hub.producers] == [(NAMESPACE, HUB, CRED)]


async def test_subscribe_yields_parsed_envelopes_from_latest_and_stamps_nothing(
    skeleton: list[FeedEnvelope],
) -> None:
    hub = FakeHub()
    bus = make_bus(hub)
    live = bus.subscribe("live-state")
    consumer = await hub.receiving("live-state")
    stamped = skeleton[1].model_copy(update={"server_receipt_ms": 77})
    await bus.publish(skeleton[0])
    await bus.publish(stamped)

    received = await take(live, 2)
    assert all(isinstance(e, FeedEnvelope) for e in received)
    assert [dump(e) for e in received] == [dump(skeleton[0]), dump(stamped)]
    assert received[0].server_receipt_ms is None
    assert received[1].server_receipt_ms == 77
    assert hub.consumer_args == [(NAMESPACE, HUB, "live-state", CRED)]
    assert consumer.starting_position == "@latest"
    await bus.close()


async def test_each_consumer_group_gets_its_own_client_and_every_envelope(
    skeleton: list[FeedEnvelope],
) -> None:
    hub = FakeHub()
    bus = make_bus(hub)
    live = bus.subscribe("live-state")
    fabric = bus.subscribe("fabric")
    await hub.receiving("live-state")
    await hub.receiving("fabric")
    await bus.publish(skeleton[0])

    assert [e.record_id for e in await take(live, 1)] == [skeleton[0].record_id]
    assert [e.record_id for e in await take(fabric, 1)] == [skeleton[0].record_id]
    assert sorted(hub.consumers) == ["fabric", "live-state"]
    await bus.close()


async def test_subscribers_in_one_group_share_a_client(skeleton: list[FeedEnvelope]) -> None:
    hub = FakeHub()
    bus = make_bus(hub)
    first = bus.subscribe("live-state")
    second = bus.subscribe("live-state")
    await hub.receiving("live-state")
    await bus.publish(skeleton[0])
    await bus.publish(skeleton[1])

    got = [e.record_id for e in await take(first, 1)] + [e.record_id for e in await take(second, 1)]
    assert sorted(got) == sorted(e.record_id for e in skeleton[:2])
    assert len(hub.consumers["live-state"]) == 1
    await bus.close()


async def test_starting_position_is_configurable(skeleton: list[FeedEnvelope]) -> None:
    hub = FakeHub()
    since = datetime(2026, 10, 14, tzinfo=UTC)
    bus = make_bus(hub, starting_position=since)
    bus.subscribe("live-state")
    consumer = await hub.receiving("live-state")
    assert consumer.starting_position == since
    await bus.close()


async def test_undecodable_bodies_are_skipped(skeleton: list[FeedEnvelope]) -> None:
    hub = FakeHub()
    bus = make_bus(hub)
    live = bus.subscribe("live-state")
    await hub.receiving("live-state")
    await hub.deliver("live-state", "not json")
    await hub.deliver("live-state", json.dumps({"kind": "event"}))
    await bus.publish(skeleton[0])

    assert [e.record_id for e in await take(live, 1)] == [skeleton[0].record_id]
    await bus.close()


async def test_receive_failure_surfaces_from_the_iterator() -> None:
    hub = FakeHub(consumer_error=PermissionError("unauthorized"))
    bus = make_bus(hub)
    live = bus.subscribe("live-state")
    with pytest.raises(PermissionError, match="unauthorized"):
        await asyncio.wait_for(anext(live), timeout=1)
    await bus.close()


async def test_close_ends_iterators_and_closes_clients(skeleton: list[FeedEnvelope]) -> None:
    hub = FakeHub()
    bus = make_bus(hub)
    live = bus.subscribe("live-state")
    consumer = await hub.receiving("live-state")
    await bus.publish(skeleton[0])
    await bus.close()
    await bus.close()

    assert [e.record_id async for e in live] == [skeleton[0].record_id]
    assert consumer.closed
    assert hub.producers[0][3].closed
    with pytest.raises(RuntimeError, match="closed"):
        await bus.publish(skeleton[1])
    assert [e async for e in bus.subscribe("fabric")] == []
