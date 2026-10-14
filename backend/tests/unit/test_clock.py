import asyncio

from tactistream.transport.clock import Clock, FakeClock, MonotonicClock


def test_fake_clock_starts_at_given_value() -> None:
    assert FakeClock(1_000).now_ms() == 1_000
    assert FakeClock().now_ms() == 0


async def test_sleep_completes_only_after_advance() -> None:
    clock = FakeClock(1_000)
    sleeper = asyncio.create_task(clock.sleep_ms(500))
    await asyncio.sleep(0)

    await clock.advance(499)
    assert not sleeper.done()
    assert clock.now_ms() == 1_499

    await clock.advance(1)
    assert sleeper.done()
    assert clock.now_ms() == 1_500


async def test_concurrent_sleepers_wake_in_deadline_order() -> None:
    clock = FakeClock()
    woke: list[tuple[str, int]] = []

    async def sleeper(name: str, ms: int) -> None:
        await clock.sleep_ms(ms)
        woke.append((name, clock.now_ms()))

    tasks = [asyncio.create_task(sleeper(name, ms)) for name, ms in [("c", 300), ("a", 100), ("b", 200)]]
    await asyncio.sleep(0)
    await clock.advance(1_000)
    await asyncio.gather(*tasks)

    assert woke == [("a", 100), ("b", 200), ("c", 300)]
    assert clock.now_ms() == 1_000


async def test_equal_deadlines_wake_in_registration_order() -> None:
    clock = FakeClock()
    woke: list[str] = []

    async def sleeper(name: str) -> None:
        await clock.sleep_ms(100)
        woke.append(name)

    tasks = [asyncio.create_task(sleeper(n)) for n in ["first", "second", "third"]]
    await asyncio.sleep(0)
    await clock.advance(100)
    await asyncio.gather(*tasks)
    assert woke == ["first", "second", "third"]


async def test_sleeps_scheduled_by_woken_tasks_fire_within_the_same_advance() -> None:
    clock = FakeClock()
    ticks: list[int] = []

    async def ticker() -> None:
        for _ in range(3):
            await clock.sleep_ms(100)
            ticks.append(clock.now_ms())

    task = asyncio.create_task(ticker())
    await asyncio.sleep(0)
    await clock.advance(250)
    assert ticks == [100, 200]
    await clock.advance(50)
    await task
    assert ticks == [100, 200, 300]


async def test_cancelled_sleeper_is_skipped() -> None:
    clock = FakeClock()
    cancelled = asyncio.create_task(clock.sleep_ms(100))
    survivor = asyncio.create_task(clock.sleep_ms(200))
    await asyncio.sleep(0)
    cancelled.cancel()
    await clock.advance(200)
    assert survivor.done()
    assert cancelled.cancelled()


async def test_non_positive_sleep_returns_immediately() -> None:
    clock = FakeClock(5)
    await clock.sleep_ms(0)
    await clock.sleep_ms(-10)
    assert clock.now_ms() == 5


async def test_monotonic_clock_advances_with_real_time() -> None:
    clock: Clock = MonotonicClock()
    start = clock.now_ms()
    await clock.sleep_ms(20)
    assert clock.now_ms() - start >= 19


def test_fake_clock_satisfies_protocol() -> None:
    clock: Clock = FakeClock()
    assert clock.now_ms() == 0
