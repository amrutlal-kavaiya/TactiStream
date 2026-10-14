from datetime import datetime

import httpx
import pytest
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport
from support.app_env import WS_PATH, receive, receive_until
from support.fake_eventhubs import FakeHub

from tactistream.api.app import create_app
from tactistream.settings import Settings
from tactistream.transport.clock import FakeClock
from tactistream.transport.eventhubs_bus import EventHubsBus

NAMESPACE = "tactistream.servicebus.windows.net"


def eventhubs_settings(**kw: object) -> Settings:
    values: dict[str, object] = {
        "static_dir": None,
        "bus": "eventhubs",
        "eventhubs_fully_qualified_namespace": NAMESPACE,
    }
    values.update(kw)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


async def test_eventhubs_bus_carries_a_session_to_the_card() -> None:
    hub = FakeHub()
    clock = FakeClock()
    app = create_app(eventhubs_settings(), clock=clock, eventhubs_client_factory=hub)
    assert isinstance(app.state.bus, EventHubsBus)
    async with (
        app.router.lifespan_context(app),
        ASGIWebSocketTransport(app=app) as transport,
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as client,
    ):
        health = await client.get("/healthz")
        assert health.json()["bus"] == "eventhubs"

        response = await client.post("/api/sessions", json={"scenario": "skeleton"})
        assert response.status_code == 200, response.text

        (consumer,) = hub.consumers["live-state"]
        assert isinstance(consumer.starting_position, datetime)
        assert hub.producers[0][:2] == (NAMESPACE, "tactistream-feed")
        assert all(key == response.json()["match_id"] for _, key in hub.sent)

        async with aconnect_ws(WS_PATH, client) as ws:
            assert (await receive(ws))["type"] == "snapshot"
            await client.post(f"/api/matches/{response.json()['match_id']}/control", json={"action": "play"})
            await clock.advance(4000)
            messages = await receive_until(ws, lambda m: m["type"] == "insight")
            assert messages[-1]["type"] == "insight"

        await app.state.registry.aclose()

    assert consumer.closed
    assert hub.producers[0][3].closed


def test_eventhubs_bus_requires_a_namespace() -> None:
    with pytest.raises(ValueError, match="Missing EVENTHUBS_FULLY_QUALIFIED_NAMESPACE"):
        create_app(
            eventhubs_settings(eventhubs_fully_qualified_namespace=None), eventhubs_client_factory=FakeHub()
        )
