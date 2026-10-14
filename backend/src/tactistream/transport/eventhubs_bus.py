"""`FeedBus` over Azure Event Hubs: JSON bodies keyed by `match_id`, one async consumer per consumer group."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from azure.eventhub import EventData
from pydantic import ValidationError

from tactistream.contracts import FeedEnvelope

logger = logging.getLogger(__name__)

OnEvent = Callable[[Any, EventData | None], Awaitable[None]]
StartingPosition = str | datetime


class EventHubsProducer(Protocol):
    async def send_event(self, event_data: EventData, *, partition_key: str | None = None) -> None: ...

    async def close(self) -> None: ...


class EventHubsConsumer(Protocol):
    async def receive(
        self, on_event: OnEvent, *, starting_position: StartingPosition | None = None
    ) -> None: ...

    async def close(self) -> None: ...


class EventHubsClientFactory(Protocol):
    def producer(self, namespace: str, hub: str, credential: Any) -> EventHubsProducer: ...

    def consumer(
        self, namespace: str, hub: str, consumer_group: str, credential: Any
    ) -> EventHubsConsumer: ...


class AzureEventHubsClients:
    """`azure.eventhub.aio` clients; `credential` must be an async token credential."""

    def producer(self, namespace: str, hub: str, credential: Any) -> EventHubsProducer:
        from azure.eventhub.aio import EventHubProducerClient

        client: EventHubsProducer = EventHubProducerClient(
            fully_qualified_namespace=namespace, eventhub_name=hub, credential=credential
        )
        return client

    def consumer(self, namespace: str, hub: str, consumer_group: str, credential: Any) -> EventHubsConsumer:
        from azure.eventhub.aio import EventHubConsumerClient

        client: EventHubsConsumer = EventHubConsumerClient(
            fully_qualified_namespace=namespace,
            eventhub_name=hub,
            consumer_group=consumer_group,
            credential=credential,
        )
        return client


@dataclass(frozen=True)
class _Failure:
    error: Exception


_CLOSED = None
_Item = FeedEnvelope | _Failure | None


@dataclass
class _Group:
    consumer: EventHubsConsumer
    queue: asyncio.Queue[_Item]
    task: asyncio.Task[None]


class EventHubsBus:
    """Consumers in one group share a queue fed by a single receiving client.

    `starting_position` is resolved when the receive link opens, so with `"@latest"` envelopes published
    between `subscribe()` and link open are not seen; an enqueued-time `datetime` closes that gap.
    """

    def __init__(
        self,
        namespace: str,
        hub: str,
        credential: Any,
        client_factory: EventHubsClientFactory | None = None,
        *,
        starting_position: StartingPosition = "@latest",
    ) -> None:
        self._namespace = namespace
        self._hub = hub
        self._credential = credential
        self._factory = client_factory or AzureEventHubsClients()
        self._starting_position = starting_position
        self._producer: EventHubsProducer | None = None
        self._groups: dict[str, _Group] = {}
        self._closed = False

    async def publish(self, envelope: FeedEnvelope) -> None:
        if self._closed:
            raise RuntimeError("bus is closed")
        if self._producer is None:
            self._producer = self._factory.producer(self._namespace, self._hub, self._credential)
        body = json.dumps(envelope.model_dump(mode="json", exclude_none=True), separators=(",", ":"))
        event = EventData(body)
        event.content_type = "application/json"
        await self._producer.send_event(event, partition_key=envelope.match_id)

    def subscribe(self, consumer_group: str) -> AsyncIterator[FeedEnvelope]:
        if self._closed:
            queue: asyncio.Queue[_Item] = asyncio.Queue()
            queue.put_nowait(_CLOSED)
            return self._drain(queue)
        group = self._groups.get(consumer_group) or self._start(consumer_group)
        return self._drain(group.queue)

    async def close(self) -> None:
        """Stop every consumer and the producer; subscribers end after draining what was already received."""
        if self._closed:
            return
        self._closed = True
        for group in self._groups.values():
            await group.consumer.close()
            group.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await group.task
            group.queue.put_nowait(_CLOSED)
        if self._producer is not None:
            await self._producer.close()

    def _start(self, consumer_group: str) -> _Group:
        queue: asyncio.Queue[_Item] = asyncio.Queue()
        consumer = self._factory.consumer(self._namespace, self._hub, consumer_group, self._credential)

        async def on_event(_context: Any, event: EventData | None) -> None:
            if event is None:
                return
            try:
                envelope = FeedEnvelope.model_validate_json(event.body_as_str())
            except (ValidationError, TypeError, UnicodeDecodeError) as exc:
                logger.warning("skipping undecodable event in %s: %s", consumer_group, exc)
                return
            queue.put_nowait(envelope)

        async def receive() -> None:
            try:
                await consumer.receive(on_event, starting_position=self._starting_position)
            except Exception as exc:
                logger.error("receive failed for consumer group %s: %s", consumer_group, exc)
                queue.put_nowait(_Failure(exc))
            else:
                queue.put_nowait(_CLOSED)

        group = _Group(consumer, queue, asyncio.get_running_loop().create_task(receive()))
        self._groups[consumer_group] = group
        return group

    @staticmethod
    async def _drain(queue: asyncio.Queue[_Item]) -> AsyncIterator[FeedEnvelope]:
        while True:
            item = await queue.get()
            if item is _CLOSED or isinstance(item, _Failure):
                queue.put_nowait(item)
                if isinstance(item, _Failure):
                    raise item.error
                return
            yield item
