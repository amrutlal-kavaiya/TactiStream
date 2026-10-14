import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import WebSocketDisconnect

from tactistream.api.session import MatchSession, SessionRegistry
from tactistream.api.ws import MatchConnection
from tactistream.contracts import MatchEvent
from tactistream.telemetry.latency import LatencyRecorder
from tactistream.transport.clock import FakeClock
from tactistream.transport.memory_bus import InMemoryBus


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.incoming: asyncio.Queue[str | None] = asyncio.Queue()

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def receive_text(self) -> str:
        item = await self.incoming.get()
        if item is None:
            raise WebSocketDisconnect()
        return item

    async def close(self, code: int = 1000) -> None:
        pass


@pytest.fixture
async def session() -> AsyncIterator[MatchSession]:
    registry = SessionRegistry(InMemoryBus(), FakeClock(), LatencyRecorder())
    yield await registry.create("skeleton")
    await registry.aclose()


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


async def test_resume_snapshot_supersedes_messages_still_queued_for_the_client(
    session: MatchSession, pass_event: MatchEvent
) -> None:
    socket = FakeSocket()
    connection = asyncio.create_task(MatchConnection(socket, session, FakeClock()).run())
    await settle()
    assert [m["type"] for m in socket.sent] == ["snapshot"]

    socket.incoming.put_nowait(json.dumps({"type": "resume", "last_seq": 0}))
    for _ in range(3):
        session.hub.broadcast("event", pass_event)
    await settle()
    session.hub.broadcast("event", pass_event)
    await settle()

    assert [(m["type"], m["seq"]) for m in socket.sent] == [
        ("snapshot", 0),
        ("snapshot", 3),
        ("event", 4),
    ]
    socket.incoming.put_nowait(None)
    await asyncio.wait_for(connection, timeout=1)
    assert session.hub.subscriber_count == 0
