from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from httpx_ws import WebSocketDisconnect, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport
from support.app_env import MATCH, WS_PATH, Message, app_env, non_frame_summary, receive, receive_until

from tactistream.api import session as session_module
from tactistream.api.app import create_app
from tactistream.contracts import FeedEnvelope
from tactistream.settings import Settings
from tactistream.transport.bus import FeedBus
from tactistream.transport.clock import FakeClock
from tactistream.transport.memory_bus import InMemoryBus

FAN_EN = "Blue 8 played a forward pass to Blue 11 (13.1 m forward)."


async def test_healthz() -> None:
    async with app_env() as env:
        response = await env.client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "0.1.0", "bus": "memory", "agents": "off"}


async def test_session_play_delivers_events_metric_and_verified_insight() -> None:
    async with app_env() as env:
        body = await env.start_session()
        assert body["match_id"] == MATCH
        assert body["session_id"].startswith("s-")
        assert body["ws_path"] == WS_PATH

        async with aconnect_ws(WS_PATH, env.client) as ws:
            snapshot = await receive(ws)
            assert snapshot["type"] == "snapshot"
            assert snapshot["payload"]["events"] == []
            assert snapshot["payload"]["playback"] == {"state": "paused", "speed": 1.0, "seed": 42}

            played = await env.control("play")
            assert played == {
                "playback": {"state": "playing", "speed": 1.0, "seed": 42},
                "session_clock_ms": 0,
            }
            await env.clock.advance(4000)

            messages = await receive_until(ws, lambda m: m["type"] == "insight")
            assert non_frame_summary(messages) == [
                "event:evt-0040",
                "event:evt-0041",
                "event:evt-0042",
                "metric",
                "insight",
            ]
            seqs = [m["seq"] for m in messages]
            assert seqs == list(range(snapshot["seq"] + 1, snapshot["seq"] + 1 + len(messages)))

            insight = messages[-1]["payload"]
            assert len(insight["variants"]) == 4
            fan_en = next(v for v in insight["variants"] if (v["mode"], v["language"]) == ("fan", "en"))
            assert fan_en["body"] == FAN_EN
            assert fan_en["claim_status"] == "verified_fact"
            assert messages[-1]["server_receipt_ms"] > 0


async def test_unknown_scenario_is_422() -> None:
    async with app_env() as env:
        response = await env.client.post("/api/sessions", json={"scenario": "nope"})
        assert response.status_code == 422
        assert response.json()["error"] == "invalid_scenario"


async def test_malformed_session_request_uses_error_envelope() -> None:
    async with app_env() as env:
        response = await env.client.post("/api/sessions", json={})
        assert response.status_code == 422
        assert set(response.json()) == {"error", "detail"}


async def test_control_errors() -> None:
    async with app_env() as env:
        missing = await env.client.post("/api/matches/demo-nope-001/control", json={"action": "play"})
        assert (missing.status_code, missing.json()["error"]) == (404, "match_not_found")

        await env.start_session()
        invalid = await env.client.post(f"/api/matches/{MATCH}/control", json={"action": "seek", "to_ms": 5})
        assert (invalid.status_code, invalid.json()["error"]) == (422, "invalid_action")


async def test_pause_and_reset_report_playback() -> None:
    async with app_env() as env:
        await env.start_session()
        await env.control("play")
        await env.clock.advance(1500)
        paused = await env.control("pause")
        assert paused == {"playback": {"state": "paused", "speed": 1.0, "seed": 42}, "session_clock_ms": 1500}
        reset = await env.control("reset")
        assert reset["session_clock_ms"] == 0
        assert reset["playback"]["state"] == "paused"


async def test_unknown_match_websocket_is_closed_with_4404() -> None:
    async with app_env() as env:
        with pytest.raises(WebSocketDisconnect) as closed:
            async with aconnect_ws("/ws/matches/demo-nope-001", env.client) as ws:
                await ws.receive_json(timeout=1)
        assert closed.value.code == 4404


async def test_static_dir_is_served_when_present(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<title>TactiStream</title>", encoding="utf-8")
    app = create_app(Settings(_env_file=None, static_dir=tmp_path), clock=FakeClock())
    async with (
        ASGIWebSocketTransport(app=app) as transport,
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as client,
    ):
        page = await client.get("/")
        health = await client.get("/healthz")
    assert page.status_code == 200
    assert "TactiStream" in page.text
    assert health.status_code == 200


class DuplicatingSwappingBus:
    """Delivers every envelope twice, with each adjacent pair swapped (metadata passes straight through)."""

    def __init__(self) -> None:
        self.inner = InMemoryBus()
        self._held: FeedEnvelope | None = None

    async def publish(self, envelope: FeedEnvelope) -> None:
        if envelope.kind == "metadata":
            for _ in range(2):
                await self.inner.publish(envelope)
            return
        if self._held is None:
            self._held = envelope
            return
        first, self._held = self._held, None
        for item in (envelope, first, first, envelope):
            await self.inner.publish(item)

    def subscribe(self, consumer_group: str) -> AsyncIterator[FeedEnvelope]:
        return self.inner.subscribe(consumer_group)


async def play_to_end(bus: FeedBus | None) -> tuple[list[Message], str]:
    async with app_env(bus) as env:
        await env.start_session()
        async with aconnect_ws(WS_PATH, env.client) as ws:
            await receive(ws)
            await env.control("play")
            await env.clock.advance(6000)
            messages = await receive_until(
                ws, lambda m: m["type"] == "frame" and m["payload"]["frame_index"] == 59
            )
        session = env.app.state.registry.get(MATCH)
        return messages, session.state.state_hash()


async def test_duplicated_and_swapped_delivery_yields_one_card_and_the_same_state() -> None:
    clean_messages, clean_hash = await play_to_end(None)
    noisy_messages, noisy_hash = await play_to_end(DuplicatingSwappingBus())

    assert noisy_hash == clean_hash
    assert [m["type"] for m in noisy_messages].count("insight") == 1
    noisy_events = [m["payload"]["event_id"] for m in noisy_messages if m["type"] == "event"]
    assert sorted(noisy_events) == ["evt-0040", "evt-0041", "evt-0042", "evt-0043"]
    assert [m["type"] for m in clean_messages].count("insight") == 1


class SilentBus(InMemoryBus):
    async def publish(self, envelope: FeedEnvelope) -> None:
        return None


async def test_session_start_timeout_is_503_with_error_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_module, "READY_TIMEOUT_S", 0.05)
    async with app_env(SilentBus()) as env:
        response = await env.client.post("/api/sessions", json={"scenario": "skeleton"})
        assert response.status_code == 503
        assert response.json()["error"] == "session_start_timeout"
        assert set(response.json()) == {"error", "detail"}
        missing = await env.client.post(f"/api/matches/{MATCH}/control", json={"action": "play"})
        assert missing.status_code == 404
