"""Shared harness for integration tests: the ASGI app on a FakeClock, an httpx client and WS helpers."""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI
from httpx_ws import AsyncWebSocketSession
from httpx_ws.transport import ASGIWebSocketTransport
from tactistream.api.app import create_app

from tactistream.contracts import validate
from tactistream.settings import Settings
from tactistream.transport.bus import FeedBus
from tactistream.transport.clock import FakeClock
from tactistream.transport.memory_bus import InMemoryBus

MATCH = "demo-blue-amber-001"
WS_PATH = f"/ws/matches/{MATCH}"

Message = dict[str, Any]


@dataclass
class Env:
    app: FastAPI
    client: httpx.AsyncClient
    clock: FakeClock

    async def start_session(self) -> Message:
        response = await self.client.post("/api/sessions", json={"scenario": "skeleton"})
        assert response.status_code == 200, response.text
        body: Message = response.json()
        return body

    async def control(self, action: str) -> Message:
        response = await self.client.post(f"/api/matches/{MATCH}/control", json={"action": action})
        assert response.status_code == 200, response.text
        body: Message = response.json()
        return body


async def make_env(bus: FeedBus | None = None) -> AsyncIterator[Env]:
    clock = FakeClock()
    app = create_app(Settings(_env_file=None), clock=clock, bus=bus or InMemoryBus(), static_dir=None)
    async with (
        ASGIWebSocketTransport(app=app) as transport,
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as client,
    ):
        yield Env(app, client, clock)
        await app.state.registry.aclose()


async def receive(ws: AsyncWebSocketSession) -> Message:
    message: Message = await ws.receive_json(timeout=2)
    validate("ws_message.schema.json#/$defs/ServerMessage", message)
    return message


async def receive_until(ws: AsyncWebSocketSession, done: Callable[[Message], bool]) -> list[Message]:
    messages: list[Message] = []
    while True:
        message = await receive(ws)
        messages.append(message)
        if done(message):
            return messages


def non_frame_summary(messages: list[Message]) -> list[str]:
    return [
        f"event:{m['payload']['event_id']}" if m["type"] == "event" else m["type"]
        for m in messages
        if m["type"] not in ("frame", "heartbeat")
    ]
