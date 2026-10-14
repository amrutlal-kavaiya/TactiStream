"""FastAPI application factory and the `tactistream-api` entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tactistream import __version__
from tactistream.api import routes_evidence, routes_sessions, ws
from tactistream.api.errors import ApiError, install_error_handlers
from tactistream.api.session import SessionRegistry, WallClock, wall_clock_ms
from tactistream.settings import Settings
from tactistream.telemetry.latency import LatencyRecorder
from tactistream.telemetry.otel import setup_telemetry
from tactistream.transport.bus import FeedBus
from tactistream.transport.clock import Clock, MonotonicClock
from tactistream.transport.memory_bus import InMemoryBus

_RESERVED_PREFIXES = frozenset({"api", "ws", "healthz"})


def create_app(
    settings: Settings | None = None,
    clock: Clock | None = None,
    bus: FeedBus | None = None,
    *,
    wall_ms: WallClock = wall_clock_ms,
) -> FastAPI:
    """Build the app. Tests inject a `FakeClock` and bus; `static_dir` is mounted only if it exists."""
    settings = settings or Settings()
    setup_telemetry(settings)
    owned_bus: InMemoryBus | None = None
    if bus is None:
        if settings.bus != "memory":
            raise NotImplementedError(f"TACTISTREAM_BUS={settings.bus} is not available yet; use memory")
        bus = owned_bus = InMemoryBus()
    clock = clock or MonotonicClock()
    latency = LatencyRecorder()
    registry = SessionRegistry(bus, clock, latency, wall_ms, data_dir=settings.data_dir)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await registry.aclose()
        if owned_bus is not None:
            await owned_bus.close()

    app = FastAPI(title="TactiStream", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.registry = registry
    app.state.clock = clock
    app.state.latency = latency
    install_error_handlers(app)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "bus": settings.bus, "agents": settings.agents}

    app.include_router(routes_sessions.router)
    app.include_router(routes_evidence.router)
    app.include_router(ws.router)
    static_dir = settings.static_dir
    _install_frontend(app, static_dir if static_dir is not None and static_dir.is_dir() else None)
    return app


def _install_frontend(app: FastAPI, static_dir: Path | None) -> None:
    """Catch-all GET registered last: deep links get `index.html`; reserved prefixes get the 404 envelope."""
    if static_dir is not None and (static_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
    root = static_dir.resolve() if static_dir is not None else None

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str) -> FileResponse:
        if path.split("/", 1)[0] in _RESERVED_PREFIXES or root is None:
            raise ApiError(404, "not_found", f"no route for /{path}")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        index = root / "index.html"
        if not index.is_file():
            raise ApiError(404, "not_found", "frontend build has no index.html")
        return FileResponse(index)


def main() -> None:
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)
