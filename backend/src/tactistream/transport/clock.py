"""Injectable clocks so replay timing is testable without real sleeps."""

from __future__ import annotations

import asyncio
import heapq
import itertools
import time
from typing import Protocol


class Clock(Protocol):
    def now_ms(self) -> int: ...

    async def sleep_ms(self, ms: int) -> None: ...


class MonotonicClock:
    """Real time from `time.monotonic`."""

    def now_ms(self) -> int:
        return time.monotonic_ns() // 1_000_000

    async def sleep_ms(self, ms: int) -> None:
        await asyncio.sleep(max(ms, 0) / 1000)


class FakeClock:
    """Manually advanced clock.

    `advance` steps through pending deadlines in order (ties in registration order), setting `now_ms` to
    each deadline before waking its sleepers and letting them run, so sleeps scheduled by woken tasks inside
    the advanced window also fire.
    """

    def __init__(self, start_ms: int = 0, settle_rounds: int = 20) -> None:
        self._now = start_ms
        self._settle_rounds = settle_rounds
        self._order = itertools.count()
        self._sleepers: list[tuple[int, int, asyncio.Future[None]]] = []

    def now_ms(self) -> int:
        return self._now

    async def sleep_ms(self, ms: int) -> None:
        if ms <= 0:
            await asyncio.sleep(0)
            return
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        heapq.heappush(self._sleepers, (self._now + ms, next(self._order), future))
        await future

    async def advance(self, ms: int) -> None:
        if ms < 0:
            raise ValueError("cannot advance a clock backwards")
        target = self._now + ms
        await self._settle()
        while self._sleepers and self._sleepers[0][0] <= target:
            deadline = self._sleepers[0][0]
            self._now = deadline
            while self._sleepers and self._sleepers[0][0] == deadline:
                _, _, future = heapq.heappop(self._sleepers)
                if not future.done():
                    future.set_result(None)
            await self._settle()
        self._now = target
        await self._settle()

    async def _settle(self) -> None:
        for _ in range(self._settle_rounds):
            await asyncio.sleep(0)
