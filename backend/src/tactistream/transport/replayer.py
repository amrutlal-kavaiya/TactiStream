"""Replays recorded envelopes onto a `FeedBus` against an injectable clock."""

from __future__ import annotations

import asyncio
import contextlib
import math
from collections.abc import Sequence
from enum import StrEnum

from tactistream.contracts import FeedEnvelope
from tactistream.transport.bus import FeedBus
from tactistream.transport.clock import Clock
from tactistream.transport.fixtures import envelope_time_ms


class PlaybackState(StrEnum):
    PLAYING = "playing"
    PAUSED = "paused"
    ENDED = "ended"


class FeedReplayer:
    """Publishes each record once the session clock reaches its `session_clock_ms`.

    Records must be in replay order (metadata first). The session clock runs at `speed` times the
    injected clock while playing and is frozen otherwise.
    """

    def __init__(
        self, records: Sequence[FeedEnvelope], bus: FeedBus, clock: Clock, speed: float = 1.0
    ) -> None:
        if speed <= 0:
            raise ValueError("speed must be positive")
        self.records = list(records)
        self.bus = bus
        self.clock = clock
        self.speed = speed
        self._state = PlaybackState.PAUSED
        self._cursor = 0
        self._base_ms = 0
        self._started_at_ms = 0
        self._task: asyncio.Task[None] | None = None

    @property
    def state(self) -> PlaybackState:
        return self._state

    @property
    def session_clock_ms(self) -> int:
        if self._state is not PlaybackState.PLAYING:
            return self._base_ms
        return self._base_ms + int((self.clock.now_ms() - self._started_at_ms) * self.speed)

    async def play(self) -> None:
        if self._state is not PlaybackState.PAUSED:
            return
        self._started_at_ms = self.clock.now_ms()
        self._state = PlaybackState.PLAYING
        self._task = asyncio.create_task(self._run())

    def pause(self) -> None:
        if self._state is not PlaybackState.PLAYING:
            return
        self._base_ms = self.session_clock_ms
        self._state = PlaybackState.PAUSED
        self._cancel()

    async def reset(self) -> None:
        """Rewind to session time 0 (paused) and republish the leading metadata records."""
        self._cancel()
        self._state = PlaybackState.PAUSED
        self._base_ms = 0
        self._cursor = 0
        while self._cursor < len(self.records) and self.records[self._cursor].kind == "metadata":
            await self.bus.publish(self.records[self._cursor])
            self._cursor += 1

    async def aclose(self) -> None:
        task = self._task
        self.pause()
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    def _cancel(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        while self._cursor < len(self.records):
            record = self.records[self._cursor]
            due_ms = envelope_time_ms(record)
            while (now_ms := self.session_clock_ms) < due_ms:
                await self.clock.sleep_ms(math.ceil((due_ms - now_ms) / self.speed))
            await self.bus.publish(record)
            self._cursor += 1
        self._base_ms = self.session_clock_ms
        self._state = PlaybackState.ENDED
        self._task = None
