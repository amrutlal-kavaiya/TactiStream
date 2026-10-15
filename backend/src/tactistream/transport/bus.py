"""Feed transport abstraction shared by the in-memory bus and Azure Event Hubs."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from tactistream.contracts import FeedEnvelope


class FeedBus(Protocol):
    """At-least-once, per-match ordered delivery of envelopes to every consumer group.

    A consumer group sees only envelopes published after it subscribed. Duplicates are possible; dedupe
    is the ingesting service's job.
    """

    async def publish(self, envelope: FeedEnvelope) -> None: ...

    def subscribe(self, consumer_group: str) -> AsyncIterator[FeedEnvelope]: ...
