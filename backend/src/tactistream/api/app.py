"""FastAPI application factory and the `tactistream-api` entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from tactistream import __version__
from tactistream.api import routes_evidence, routes_sessions, ws
from tactistream.api.errors import install_error_handlers
from tactistream.api.session import SessionRegistry, WallClock, wall_clock_ms
from tactistream.settings import Settings
from tactistream.telemetry.latency import LatencyRecorder
from tactistream.telemetry.otel import setup_telemetry
from tactistream.transport.bus import FeedBus
from tactistream.transport.clock import Clock, MonotonicClock
from tactistream.transport.eventhubs_bus import EventHubsBus, EventHubsClientFactory, enqueued_since_subscribe
from tactistream.transport.memory_bus import InMemoryBus


def create_app(
    settings: Settings | None = None,
    clock: Clock | None = None,
    bus: FeedBus | None = None,
    *,
    wall_ms: WallClock = wall_clock_ms,
    eventhubs_client_factory: EventHubsClientFactory | None = None,
) -> FastAPI:
    """Build the app. Tests inject a `FakeClock` and bus; `static_dir` is mounted only if it exists."""
    settings = settings or Settings()
    setup_telemetry(settings)
    owned_bus: InMemoryBus | EventHubsBus | None = None
    credential: AsyncDefaultAzureCredential | None = None
    if bus is None and settings.bus == "eventhubs":
        namespace = settings.eventhubs_fully_qualified_namespace
        if not namespace:
            raise ValueError(
                "Missing EVENTHUBS_FULLY_QUALIFIED_NAMESPACE (required by TACTISTREAM_BUS=eventhubs)"
            )
        credential = AsyncDefaultAzureCredential()
        bus = owned_bus = EventHubsBus(
            namespace,
            settings.eventhubs_name,
            credential,
            eventhubs_client_factory,
            starting_position=enqueued_since_subscribe(),
        )
    elif bus is None:
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
        if credential is not None:
            await credential.close()

    app = FastAPI(title="TactiStream", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.bus = bus
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
    if static_dir is not None and static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    return app


def main() -> None:
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)
