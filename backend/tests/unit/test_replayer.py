import asyncio
import json
import random
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from tactistream.contracts import FeedEnvelope
from tactistream.transport.clock import FakeClock
from tactistream.transport.fixtures import load_fixture, skeleton_fixture_path
from tactistream.transport.memory_bus import InMemoryBus
from tactistream.transport.replayer import FeedReplayer, PlaybackState


class Harness:
    def __init__(self, speed: float = 1.0) -> None:
        self.clock = FakeClock()
        self.bus = InMemoryBus()
        self.published: list[FeedEnvelope] = []
        self.replayer = FeedReplayer(
            records=load_fixture(skeleton_fixture_path()), bus=self.bus, clock=self.clock, speed=speed
        )
        self._collector = asyncio.create_task(self._collect(self.bus.subscribe("test")))

    async def _collect(self, stream: AsyncIterator[FeedEnvelope]) -> None:
        async for env in stream:
            self.published.append(env)

    def ids(self) -> list[str]:
        return [env.record_id for env in self.published]

    async def close(self) -> None:
        self.replayer.pause()
        await self.bus.close()
        await self._collector


@pytest.fixture
async def h() -> AsyncIterator[Harness]:
    harness = Harness()
    yield harness
    await harness.close()


async def test_pass_is_published_when_clock_reaches_its_session_time(h: Harness) -> None:
    await h.replayer.play()
    await h.clock.advance(2999)
    assert "evt-0041" in h.ids()
    assert "evt-0042" not in h.ids()

    await h.clock.advance(1)
    assert "evt-0042" in h.ids()
    assert "evt-0043" not in h.ids()


async def test_pause_stops_publishing_while_clock_advances(h: Harness) -> None:
    await h.replayer.play()
    await h.clock.advance(1000)
    h.replayer.pause()
    count = len(h.published)

    await h.clock.advance(5000)
    assert len(h.published) == count
    assert h.replayer.state is PlaybackState.PAUSED
    assert h.replayer.session_clock_ms == 1000


async def test_play_resumes_from_paused_session_time(h: Harness) -> None:
    await h.replayer.play()
    await h.clock.advance(1000)
    h.replayer.pause()
    await h.clock.advance(5000)

    await h.replayer.play()
    await h.clock.advance(2000)
    assert h.replayer.session_clock_ms == 3000
    assert "evt-0042" in h.ids()
    assert "evt-0043" not in h.ids()
    assert h.ids().count("frm-000010") == 1


async def test_reset_rewinds_to_zero_and_republishes_metadata_first(h: Harness) -> None:
    await h.replayer.play()
    await h.clock.advance(2000)
    before = len(h.published)

    await h.replayer.reset()
    await h.clock.advance(0)
    assert h.replayer.session_clock_ms == 0
    assert h.replayer.state is PlaybackState.PAUSED
    assert [env.kind for env in h.published[before:]] == ["metadata"]

    await h.clock.advance(1000)
    assert len(h.published) == before + 1

    await h.replayer.play()
    await h.clock.advance(0)
    assert h.published[before + 1].record_id == "evt-0040"


async def test_state_becomes_ended_after_last_record(h: Harness) -> None:
    await h.replayer.play()
    await h.clock.advance(5899)
    assert h.replayer.state is PlaybackState.PLAYING

    await h.clock.advance(1)
    assert h.replayer.state is PlaybackState.ENDED
    assert h.ids() == [env.record_id for env in h.replayer.records]
    assert h.replayer.session_clock_ms == 5900

    await h.clock.advance(1000)
    assert h.replayer.session_clock_ms == 5900


async def test_double_speed_halves_wall_time() -> None:
    harness = Harness(speed=2.0)
    await harness.replayer.play()
    await harness.clock.advance(1499)
    assert "evt-0042" not in harness.ids()
    await harness.clock.advance(1)
    assert "evt-0042" in harness.ids()
    assert harness.replayer.session_clock_ms == 3000
    await harness.close()


def test_load_fixture_orders_metadata_first_then_time_with_events_before_frames(tmp_path: Path) -> None:
    lines = skeleton_fixture_path().read_text(encoding="utf-8").splitlines()
    shuffled = lines[:]
    random.Random(7).shuffle(shuffled)
    path = tmp_path / "shuffled.jsonl"
    path.write_text("\n".join(shuffled) + "\n", encoding="utf-8")

    records = load_fixture(path)
    assert [r.record_id for r in records] == [json.loads(line)["record_id"] for line in lines]
    assert records[0].kind == "metadata"
    assert [r.record_id for r in records[1:3]] == ["evt-0040", "frm-000000"]


def test_load_fixture_rejects_envelopes_that_break_the_schema(tmp_path: Path) -> None:
    line = json.loads(skeleton_fixture_path().read_text(encoding="utf-8").splitlines()[1])
    line["published_ms"] = "5"
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(line) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"bad.jsonl:1"):
        load_fixture(path)
