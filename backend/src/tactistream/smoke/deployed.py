"""Deployed smoke: healthz → session → WebSocket snapshot → play → first event → optional soak → reset."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, WebSocketException

SCENARIO = "skeleton"
SNAPSHOT_TIMEOUT_S = 5.0
FIRST_EVENT_TIMEOUT_S = 15.0
HEARTBEAT_EVERY_S = 15


class DeployedSmokeError(Exception):
    """A failed check; `exit_code` 2 means the deployment was unreachable, 1 means a check failed."""

    def __init__(self, reason: str, *, exit_code: int = 1) -> None:
        super().__init__(reason)
        self.reason = reason
        self.exit_code = exit_code


@dataclass(frozen=True)
class DeployedSmokeResult:
    base_url: str
    healthz_ok: bool
    bus: str
    version: str
    match_id: str
    snapshot_ms: int
    first_event_ms: int
    soak_s: int
    heartbeats: int

    def summary(self) -> dict[str, Any]:
        return {"ok": True, **asdict(self)}


def _ws_url(base_url: str, path: str) -> str:
    parts = urlsplit(base_url)
    scheme = "wss" if parts.scheme == "https" else "ws"
    return urlunsplit((scheme, parts.netloc, path, "", ""))


def _elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def _close_code(exc: ConnectionClosed) -> str:
    return str(exc.rcvd.code) if exc.rcvd else "no close frame"


async def _next_of_type(
    socket: ClientConnection, wanted: str, timeout_s: float, stage: str
) -> dict[str, Any]:
    async def wait() -> dict[str, Any]:
        while True:
            message: dict[str, Any] = json.loads(await socket.recv())
            if message.get("type") == wanted:
                return message

    try:
        return await asyncio.wait_for(wait(), timeout_s)
    except TimeoutError as exc:
        raise DeployedSmokeError(f"{stage}: no {wanted} message within {timeout_s:g} s") from exc
    except ConnectionClosed as exc:
        raise DeployedSmokeError(f"{stage}: websocket closed ({_close_code(exc)})") from exc


async def _soak(socket: ClientConnection, soak_s: int) -> int:
    heartbeats = 0
    deadline = time.perf_counter() + soak_s
    try:
        while (remaining := deadline - time.perf_counter()) > 0:
            try:
                message = json.loads(await asyncio.wait_for(socket.recv(), remaining))
            except TimeoutError:
                break
            if message.get("type") == "heartbeat":
                heartbeats += 1
    except ConnectionClosed as exc:
        raise DeployedSmokeError(
            f"soak: websocket closed after {soak_s - (deadline - time.perf_counter()):.0f} s "
            f"({_close_code(exc)})"
        ) from exc
    expected = soak_s // HEARTBEAT_EVERY_S
    if heartbeats < expected:
        raise DeployedSmokeError(f"soak: {heartbeats} heartbeats in {soak_s} s, expected >= {expected}")
    return heartbeats


async def _post(client: httpx.AsyncClient, path: str, body: dict[str, Any], stage: str) -> dict[str, Any]:
    try:
        response = await client.post(path, json=body)
    except httpx.HTTPError as exc:
        raise DeployedSmokeError(f"{stage}: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise DeployedSmokeError(f"{stage}: HTTP {response.status_code} {response.text[:200]}")
    data: dict[str, Any] = response.json()
    return data


async def run_deployed_smoke(
    base_url: str, *, allow_memory: bool = False, timeout_s: float = 30, soak_s: int = 0
) -> DeployedSmokeResult:
    """Raise `DeployedSmokeError` with a one-line reason on the first failed check."""
    base_url = base_url.rstrip("/")
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout_s) as client:
        try:
            health = await client.get("/healthz")
        except httpx.HTTPError as exc:
            raise DeployedSmokeError(
                f"healthz: {base_url} unreachable ({type(exc).__name__})", exit_code=2
            ) from exc
        try:
            info: dict[str, Any] = health.json()
        except ValueError:
            info = {}
        if health.status_code != 200 or info.get("status") != "ok":
            raise DeployedSmokeError(f"healthz: HTTP {health.status_code} {health.text[:200]}")
        bus = str(info.get("bus"))
        if bus != "eventhubs" and not allow_memory:
            raise DeployedSmokeError(f"healthz: bus is {bus}, expected eventhubs")

        session = await _post(client, "/api/sessions", {"scenario": SCENARIO}, "session")
        match_id = str(session["match_id"])
        control = f"/api/matches/{match_id}/control"
        start = time.perf_counter()
        try:
            async with connect(
                _ws_url(base_url, str(session["ws_path"])), open_timeout=timeout_s, max_size=None
            ) as socket:
                await _next_of_type(socket, "snapshot", SNAPSHOT_TIMEOUT_S, "snapshot")
                snapshot_ms = _elapsed_ms(start)
                start = time.perf_counter()
                await _post(client, control, {"action": "play"}, "play")
                await _next_of_type(socket, "event", FIRST_EVENT_TIMEOUT_S, "first event")
                first_event_ms = _elapsed_ms(start)
                heartbeats = await _soak(socket, soak_s) if soak_s > 0 else 0
        except (OSError, WebSocketException) as exc:
            raise DeployedSmokeError(f"websocket: {type(exc).__name__}: {exc}") from exc
        finally:
            await _reset(client, control)
    return DeployedSmokeResult(
        base_url=base_url,
        healthz_ok=True,
        bus=bus,
        version=str(info.get("version")),
        match_id=match_id,
        snapshot_ms=snapshot_ms,
        first_event_ms=first_event_ms,
        soak_s=soak_s,
        heartbeats=heartbeats,
    )


async def _reset(client: httpx.AsyncClient, control: str) -> None:
    """Leave the demo match reset for the next viewer; a failed reset never masks the smoke result."""
    with contextlib.suppress(httpx.HTTPError):
        await client.post(control, json={"action": "reset"})
