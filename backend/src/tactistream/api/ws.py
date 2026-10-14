"""`/ws/matches/{match_id}`: snapshot on connect, live messages by seq, resume, display_ack, heartbeat."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from tactistream.api.session import MatchSession, SessionRegistry
from tactistream.api.ws_hub import Subscription
from tactistream.contracts import DisplayAckMsg, ResumeMsg, ServerMessage, parse_client_message
from tactistream.transport.clock import Clock

logger = logging.getLogger(__name__)

router = APIRouter()

HEARTBEAT_MS = 10_000
CLOSE_UNKNOWN_MATCH = 4404
CLOSE_TOO_SLOW = 1013


@router.websocket("/ws/matches/{match_id}")
async def match_socket(websocket: WebSocket, match_id: str) -> None:
    registry: SessionRegistry = websocket.app.state.registry
    session = registry.get(match_id)
    if session is None:
        await websocket.close(code=CLOSE_UNKNOWN_MATCH)
        return
    await websocket.accept()
    await MatchConnection(websocket, session, websocket.app.state.clock).run()


class MatchConnection:
    def __init__(self, websocket: WebSocket, session: MatchSession, clock: Clock) -> None:
        self._ws = websocket
        self._session = session
        self._clock = clock
        self._send_lock = asyncio.Lock()
        self._floor_seq = -1
        self._last_sent_seq = 0

    async def run(self) -> None:
        hub = self._session.hub
        subscription = hub.subscribe()
        await self._send_snapshot()
        receiver = asyncio.create_task(self._receive_loop())
        pump = asyncio.create_task(self._pump(subscription))
        heartbeat = asyncio.create_task(self._heartbeat())
        try:
            done, _ = await asyncio.wait({receiver, pump}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (receiver, pump, heartbeat):
                task.cancel()
            await asyncio.gather(receiver, pump, heartbeat, return_exceptions=True)
            hub.unsubscribe(subscription)
        if pump in done:
            with contextlib.suppress(Exception):
                await self._ws.close(code=CLOSE_TOO_SLOW)

    async def _send(self, message: ServerMessage) -> None:
        await self._ws.send_text(json.dumps(message.model_dump(mode="json", exclude_none=True)))
        self._last_sent_seq = max(self._last_sent_seq, message.seq)

    async def _send_snapshot(self) -> None:
        """Snapshot at head seq; queued live messages it already covers are skipped by the pump."""
        async with self._send_lock:
            snapshot = self._session.snapshot()
            self._floor_seq = snapshot.seq
            await self._send(snapshot)

    async def _pump(self, subscription: Subscription) -> None:
        while (message := await subscription.get()) is not None:
            async with self._send_lock:
                if message.seq > self._floor_seq:
                    await self._send(message)

    async def _receive_loop(self) -> None:
        with contextlib.suppress(WebSocketDisconnect):
            while True:
                await self._handle(await self._ws.receive_text())

    async def _handle(self, text: str) -> None:
        try:
            message = parse_client_message(text)
        except ValidationError as exc:
            await self._send_local("error", {"error": "invalid_message", "detail": str(exc.errors()[:1])})
            return
        if isinstance(message, ResumeMsg):
            await self._send_snapshot()
        elif isinstance(message, DisplayAckMsg):
            self._session.record_display_ack(message)

    async def _heartbeat(self) -> None:
        while True:
            await self._clock.sleep_ms(HEARTBEAT_MS)
            await self._send_local("heartbeat", {"session_clock_ms": self._session.replayer.session_clock_ms})

    async def _send_local(self, type_: str, payload: dict[str, Any]) -> None:
        """Connection-only message; carries the last seq this client has seen so it never skips ahead."""
        async with self._send_lock:
            message = ServerMessage.model_validate(
                {
                    "type": type_,
                    "seq": self._last_sent_seq,
                    "match_id": self._session.match_id,
                    "payload": payload,
                }
            )
            await self._send(message)
