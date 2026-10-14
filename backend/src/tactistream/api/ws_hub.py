"""Per-match WebSocket fan-out with a monotonic `seq` and bounded per-subscriber queues."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from tactistream.contracts import InsightBundle, ServerMessage, ServerMessageType, Snapshot, SnapshotPlayback
from tactistream.contracts.ws import ServerPayload
from tactistream.state.match_state import MatchState

QUEUE_MAXSIZE = 1000


class Subscription:
    """One connection's outbound queue. `get()` returns `None` once the subscription is closed."""

    def __init__(self, maxsize: int) -> None:
        self._queue: asyncio.Queue[ServerMessage | None] = asyncio.Queue(maxsize=maxsize)
        self.closed = False

    async def get(self) -> ServerMessage | None:
        if self.closed and self._queue.empty():
            return None
        return await self._queue.get()

    def offer(self, message: ServerMessage) -> bool:
        if self.closed:
            return False
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            self.close()
            return False
        return True

    def close(self) -> None:
        """Drop anything queued and wake the reader with the end marker."""
        if self.closed:
            return
        self.closed = True
        while not self._queue.empty():
            self._queue.get_nowait()
        self._queue.put_nowait(None)


class WsHub:
    def __init__(self, match_id: str, queue_maxsize: int = QUEUE_MAXSIZE) -> None:
        self.match_id = match_id
        self._queue_maxsize = queue_maxsize
        self._head_seq = 0
        self._subscribers: list[Subscription] = []

    @property
    def head_seq(self) -> int:
        return self._head_seq

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def subscribe(self) -> Subscription:
        subscription = Subscription(self._queue_maxsize)
        self._subscribers.append(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        subscription.close()
        if subscription in self._subscribers:
            self._subscribers.remove(subscription)

    def broadcast(
        self,
        type_: ServerMessageType,
        payload: ServerPayload,
        *,
        server_receipt_ms: int | None = None,
    ) -> ServerMessage:
        """Assign the next seq and enqueue for every subscriber; a full queue disconnects only that one."""
        self._head_seq += 1
        message = self.message(type_, payload, server_receipt_ms=server_receipt_ms)
        for subscription in list(self._subscribers):
            if not subscription.offer(message):
                self.unsubscribe(subscription)
        return message

    def message(
        self,
        type_: ServerMessageType,
        payload: ServerPayload,
        *,
        server_receipt_ms: int | None = None,
    ) -> ServerMessage:
        """A message stamped with the current head seq, not broadcast (snapshots, heartbeats, errors)."""
        return ServerMessage(
            type=type_,
            seq=self._head_seq,
            match_id=self.match_id,
            server_receipt_ms=server_receipt_ms,
            payload=payload,
        )

    def snapshot_for(
        self,
        state: MatchState,
        *,
        session_clock_ms: int,
        playback: SnapshotPlayback,
        insights: Sequence[InsightBundle] = (),
    ) -> ServerMessage:
        if state.metadata is None:
            raise RuntimeError("cannot snapshot a match without metadata")
        snapshot = Snapshot(
            metadata=state.metadata,
            state_version=state.state_version,
            session_clock_ms=session_clock_ms,
            events=list(state.events),
            latest_frame=state.latest_frame,
            moments=[],
            insights=list(insights),
            playback=playback,
        )
        return self.message("snapshot", snapshot)
