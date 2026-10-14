"""Event Hubs round-trip: publish one envelope with a random `record_id` and read it back via `live-state`."""

from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tactistream.contracts import FeedEnvelope, MatchEvent, Provenance
from tactistream.smoke.foundry import SmokeError
from tactistream.transport.eventhubs_bus import EventHubsBus, EventHubsClientFactory, enqueued_since_subscribe

SMOKE_MATCH_ID = "smoke-check"


@dataclass(frozen=True)
class EventHubsSmokeResult:
    namespace: str
    hub: str
    consumer_group: str
    record_id: str
    round_trip_ms: int


def smoke_envelope(record_id: str, published_ms: int) -> FeedEnvelope:
    event = MatchEvent(
        schema_version="1.0",
        match_id=SMOKE_MATCH_ID,
        event_id=record_id,
        sequence=1,
        period=1,
        period_clock_ms=0,
        session_clock_ms=0,
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
        match_id=SMOKE_MATCH_ID,
        record_id=record_id,
        published_ms=published_ms,
        payload=event,
    )


async def run_eventhubs_smoke(
    namespace: str,
    hub: str,
    *,
    consumer_group: str = "live-state",
    credential: Any = None,
    client_factory: EventHubsClientFactory | None = None,
    clock: Callable[[], float] = time.perf_counter,
    timeout_s: float = 30.0,
) -> EventHubsSmokeResult:
    """Without an injected `credential`, an async `DefaultAzureCredential` is used."""
    if credential is None:
        from azure.identity.aio import DefaultAzureCredential

        async with DefaultAzureCredential() as owned:
            return await _round_trip(namespace, hub, consumer_group, owned, client_factory, clock, timeout_s)
    return await _round_trip(namespace, hub, consumer_group, credential, client_factory, clock, timeout_s)


async def _round_trip(
    namespace: str,
    hub: str,
    consumer_group: str,
    credential: Any,
    client_factory: EventHubsClientFactory | None,
    clock: Callable[[], float],
    timeout_s: float,
) -> EventHubsSmokeResult:
    bus = EventHubsBus(
        namespace, hub, credential, client_factory, starting_position=enqueued_since_subscribe()
    )
    try:
        stream = bus.subscribe(consumer_group)
        record_id = f"evt-{secrets.randbelow(10**12):012d}"
        sent = smoke_envelope(record_id, int(time.time() * 1000))
        started = clock()
        await bus.publish(sent)
        try:
            async with asyncio.timeout(timeout_s):
                async for received in stream:
                    if (received.kind, received.record_id) == (sent.kind, record_id):
                        break
                else:
                    raise SmokeError(f"{consumer_group} stream ended before {record_id} came back")
        except TimeoutError:
            raise SmokeError(
                f"envelope {record_id} not read back via {consumer_group} within {timeout_s:g} s"
            ) from None
        round_trip_ms = round((clock() - started) * 1000)
        if received.model_dump(mode="json") != sent.model_dump(mode="json"):
            raise SmokeError(f"read-back envelope {record_id} differs from the one sent")
        return EventHubsSmokeResult(namespace, hub, consumer_group, record_id, round_trip_ms)
    finally:
        await bus.close()
