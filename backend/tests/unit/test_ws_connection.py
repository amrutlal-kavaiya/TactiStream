import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import WebSocketDisconnect
from starlette.websockets import WebSocketDisconnected

from tactistream.api.session import MatchSession, SessionRegistry
from tactistream.api.ws import MatchConnection
from tactistream.contracts import MatchEvent
from tactistream.telemetry.latency import LatencyRecorder
from tactistream.transport.clock import FakeClock
from tactistream.transport.memory_bus import InMemoryBus


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.incoming: asyncio.Queue[str | Exception | None] = asyncio.Queue()
        self.close_code: int | None = None
        self.send_error: Exception | None = None

    async def send_text(self, text: str) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.sent.append(json.loads(text))

    async def receive_text(self) -> str:
        item = await self.incoming.get()
        if item is None:
            raise WebSocketDisconnect()
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self, code: int = 1000) -> None:
        self.close_code = code


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


async def open_connection(session: MatchSession) -> tuple[FakeSocket, asyncio.Task[None]]:
    socket = FakeSocket()
    task = asyncio.create_task(MatchConnection(socket, session, FakeClock()).run())
    await settle()
    return socket, task


async def test_server_shutdown_closes_with_going_away(session: MatchSession) -> None:
    socket, task = await open_connection(session)
    session.hub.close()
    await asyncio.wait_for(task, timeout=1)
    assert socket.close_code == 1001


async def test_overflowing_client_is_closed_with_try_again_later(
    session: MatchSession, pass_event: MatchEvent
) -> None:
    socket, task = await open_connection(session)
    for _ in range(1001):
        session.hub.broadcast("event", pass_event)
    await asyncio.wait_for(task, timeout=1)
    assert socket.close_code == 1013


async def test_receiver_failure_is_logged_and_closes_with_internal_error(
    session: MatchSession, caplog: pytest.LogCaptureFixture
) -> None:
    socket, task = await open_connection(session)
    socket.incoming.put_nowait(RuntimeError("boom"))
    await asyncio.wait_for(task, timeout=1)
    assert socket.close_code == 1011
    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert errors
    assert errors[0].exc_info is not None
    assert "boom" in str(errors[0].exc_info[1])
    assert session.hub.subscriber_count == 0


@pytest.mark.parametrize(
    "error",
    [
        WebSocketDisconnect(code=1006),
        WebSocketDisconnected('Cannot call "send" once a close message has been sent.'),
    ],
    ids=["disconnect", "already-closed"],
)
async def test_client_gone_mid_send_is_a_normal_disconnect(
    session: MatchSession, pass_event: MatchEvent, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    socket, task = await open_connection(session)
    socket.send_error = error
    session.hub.broadcast("event", pass_event)
    await asyncio.wait_for(task, timeout=1)
    assert socket.close_code is None
    assert [r for r in caplog.records if r.levelname == "ERROR"] == []
    assert session.hub.subscriber_count == 0
