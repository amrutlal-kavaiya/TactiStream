"""In-memory stand-in for the async Event Hubs producer/consumer clients used by `EventHubsBus`."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from azure.eventhub import EventData

OnEvent = Callable[[Any, EventData | None], Awaitable[None]]
OnError = Callable[[Any, Exception], Awaitable[None]]


class FakeProducer:
    def __init__(self, hub: "FakeHub") -> None:
        self.hub = hub
        self.closed = False

    async def send_event(self, event_data: EventData, *, partition_key: str | None = None) -> None:
        body = event_data.body_as_str()
        self.hub.sent.append((body, partition_key))
        delivered = self.hub.transform(body)
        if delivered is None:
            return
        self.hub.log.append((datetime.now(UTC), delivered))
        for consumer in [c for group in self.hub.consumers.values() for c in group]:
            await consumer.push(delivered)

    async def close(self) -> None:
        self.closed = True


class FakeConsumer:
    """`@latest` sees only sends after `receive` starts; a datetime position replays the hub log from then.

    Like the SDK, `receive` never raises for service errors: it reports them to `on_error` and keeps going.
    """

    def __init__(self, hub: "FakeHub", consumer_group: str) -> None:
        self.hub = hub
        self.consumer_group = consumer_group
        self.on_event: OnEvent | None = None
        self.on_error: OnError | None = None
        self.starting_position: str | datetime | None = None
        self.receiving = asyncio.Event()
        self.stopped = asyncio.Event()
        self.closed = False
        self.cancelled = False
        self.ended = asyncio.Event()

    async def receive(
        self,
        on_event: OnEvent,
        *,
        starting_position: str | datetime | None = None,
        on_error: OnError | None = None,
    ) -> None:
        self.on_event = on_event
        self.on_error = on_error
        self.starting_position = starting_position
        try:
            if self.hub.consumer_error is not None:
                await self.fail(self.hub.consumer_error)
            if isinstance(starting_position, datetime):
                for enqueued, body in list(self.hub.log):
                    if enqueued >= starting_position:
                        await on_event(None, EventData(body))
            self.receiving.set()
            await self.stopped.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        finally:
            self.ended.set()

    async def fail(self, error: Exception) -> None:
        if self.on_error is not None:
            await self.on_error(None, error)

    async def push(self, body: str) -> None:
        if self.on_event is not None and self.receiving.is_set():
            await self.on_event(None, EventData(body))

    async def close(self) -> None:
        self.closed = True
        self.stopped.set()


class FakeHub:
    """Client factory: every send is delivered (after `transform`; `None` drops it) to receiving consumers."""

    def __init__(
        self,
        consumer_error: Exception | None = None,
        transform: Callable[[str], str | None] = lambda body: body,
    ) -> None:
        self.consumer_error = consumer_error
        self.transform = transform
        self.sent: list[tuple[str, str | None]] = []
        self.log: list[tuple[datetime, str]] = []
        self.producers: list[tuple[str, str, Any, FakeProducer]] = []
        self.consumers: dict[str, list[FakeConsumer]] = {}
        self.consumer_args: list[tuple[str, str, str, Any]] = []

    def producer(self, namespace: str, hub: str, credential: Any) -> FakeProducer:
        producer = FakeProducer(self)
        self.producers.append((namespace, hub, credential, producer))
        return producer

    def consumer(self, namespace: str, hub: str, consumer_group: str, credential: Any) -> FakeConsumer:
        consumer = FakeConsumer(self, consumer_group)
        self.consumers.setdefault(consumer_group, []).append(consumer)
        self.consumer_args.append((namespace, hub, consumer_group, credential))
        return consumer

    async def receiving(self, consumer_group: str) -> FakeConsumer:
        async def wait() -> FakeConsumer:
            while not self.consumers.get(consumer_group):
                await asyncio.sleep(0)
            consumer = self.consumers[consumer_group][0]
            await consumer.receiving.wait()
            return consumer

        return await asyncio.wait_for(wait(), timeout=1)

    async def deliver(self, consumer_group: str, body: str) -> None:
        for consumer in self.consumers[consumer_group]:
            await consumer.push(body)
