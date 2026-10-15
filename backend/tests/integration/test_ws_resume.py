from httpx_ws import aconnect_ws
from support.app_env import WS_PATH, Message, app_env, receive, receive_until


def event_ids(events: list[Message]) -> list[str]:
    return [e["event_id"] for e in events]


async def test_reconnect_with_resume_gets_snapshot_with_each_event_once_then_newer_messages() -> None:
    async with app_env() as env:
        await env.start_session()
        async with aconnect_ws(WS_PATH, env.client) as ws:
            await receive(ws)
            await env.control("play")
            await env.clock.advance(1500)
            seen = await receive_until(
                ws, lambda m: m["type"] == "event" and m["payload"]["event_id"] == "evt-0041"
            )
            last_seq = seen[-1]["seq"]

        await env.clock.advance(2500)

        async with aconnect_ws(WS_PATH, env.client) as ws:
            assert (await receive(ws))["type"] == "snapshot"
            await ws.send_json({"type": "resume", "last_seq": last_seq})
            snapshot = await receive(ws)
            assert snapshot["type"] == "snapshot"
            assert snapshot["seq"] > last_seq
            events = snapshot["payload"]["events"]
            assert event_ids(events) == ["evt-0040", "evt-0041", "evt-0042", "evt-0043"]
            assert [b["insight_id"] for b in snapshot["payload"]["insights"]] == ["ins-0042"]

            await env.clock.advance(1000)
            live = await receive_until(
                ws, lambda m: m["type"] == "frame" and m["payload"]["frame_index"] == 50
            )
            assert all(m["seq"] > snapshot["seq"] for m in live)
            assert [m["seq"] for m in live] == list(
                range(snapshot["seq"] + 1, snapshot["seq"] + 1 + len(live))
            )
            live_events = [m["payload"]["event_id"] for m in live if m["type"] == "event"]
            assert not set(live_events) & set(event_ids(events))


async def test_messages_queued_before_resume_are_not_replayed_after_the_snapshot() -> None:
    async with app_env() as env:
        await env.start_session()
        async with aconnect_ws(WS_PATH, env.client) as ws:
            first = await receive(ws)
            await env.control("play")
            await env.clock.advance(4000)
            await ws.send_json({"type": "resume", "last_seq": first["seq"]})

            before = await receive_until(ws, lambda m: m["type"] == "snapshot")
            resumed = before[-1]
            await env.clock.advance(500)
            after = await receive_until(
                ws, lambda m: m["type"] == "frame" and m["payload"]["frame_index"] == 45
            )

            assert all(m["seq"] <= resumed["seq"] for m in before)
            assert [m["seq"] for m in after] == list(
                range(resumed["seq"] + 1, resumed["seq"] + 1 + len(after))
            )
            assert event_ids(resumed["payload"]["events"]) == ["evt-0040", "evt-0041", "evt-0042", "evt-0043"]


async def test_invalid_client_message_gets_a_non_fatal_error() -> None:
    async with app_env() as env:
        await env.start_session()
        async with aconnect_ws(WS_PATH, env.client) as ws:
            snapshot = await receive(ws)
            await ws.send_json({"type": "bogus"})
            error = await receive(ws)
            assert error["type"] == "error"
            assert error["payload"]["error"] == "invalid_message"
            assert error["seq"] == snapshot["seq"]
            await ws.send_json({"type": "resume", "last_seq": -1})
            assert (await receive(ws))["type"] == "snapshot"


async def test_display_ack_records_fast_overlay_latency() -> None:
    async with app_env() as env:
        await env.start_session()
        async with aconnect_ws(WS_PATH, env.client) as ws:
            await receive(ws)
            await env.control("play")
            await env.clock.advance(3000)
            insight = (await receive_until(ws, lambda m: m["type"] == "insight"))[-1]
            await ws.send_json(
                {
                    "type": "display_ack",
                    "target_kind": "insight",
                    "target_id": "ins-0042",
                    "server_seq": insight["seq"],
                }
            )
            await ws.send_json({"type": "resume", "last_seq": insight["seq"]})
            await receive_until(ws, lambda m: m["type"] == "snapshot")
        samples = env.app.state.latency.samples("fast_overlay")
        assert len(samples) == 1
        assert samples[0].attrs["target_kind"] == "insight"
