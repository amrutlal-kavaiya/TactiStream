"""In-process `FeedBus` with the same delivery semantics as the Event Hubs adapter."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from tactistream.contracts import FeedEnvelope

_CLOSED = None


class InMemoryBus:
    """One unbounded `asyncio.Queue` per consumer group; consumers in the same group share it."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[FeedEnvelope | None]] = {}
        self._closed = False

    async def publish(self, envelope: FeedEnvelope) -> None:
        if self._closed:
            raise RuntimeError("bus is closed")
        for queue in self._queues.values():
            queue.put_nowait(envelope)

    def subscribe(self, consumer_group: str) -> AsyncIterator[FeedEnvelope]:
        queue = self._queues.get(consumer_group)
        if queue is None:
            queue = asyncio.Queue()
            if self._closed:
                queue.put_nowait(_CLOSED)
            else:
                self._queues[consumer_group] = queue
        return self._drain(queue)

    async def close(self) -> None:
        """End every subscriber's iterator after it has drained what was already published."""
        if self._closed:
            return
        self._closed = True
        for queue in self._queues.values():
            queue.put_nowait(_CLOSED)

    @staticmethod
    async def _drain(queue: asyncio.Queue[FeedEnvelope | None]) -> AsyncIterator[FeedEnvelope]:
        while True:
            item = await queue.get()
            if item is _CLOSED:
                queue.put_nowait(_CLOSED)
                return
            yield item
