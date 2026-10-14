import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest

from tactistream.api import session as session_module
from tactistream.api.session import MatchSession, SessionRegistry, SessionStartError, UnknownScenarioError
from tactistream.api.ws_hub import Subscription
from tactistream.contracts import (
    DisplayAckMsg,
    FeedEnvelope,
    InsightBundle,
    MatchEvent,
    NarrativeStatus,
    ServerMessage,
    Snapshot,
)
from tactistream.telemetry.latency import LatencyRecorder
from tactistream.transport.clock import FakeClock
from tactistream.transport.memory_bus import InMemoryBus

FAN_EN = "Blue 8 played a forward pass to Blue 11 (13.1 m forward)."


class WallClock:
    def __init__(self) -> None:
        self.now = 1_792_000_000_000

    def __call__(self) -> int:
        return self.now


@dataclass
class World:
    registry: SessionRegistry
    clock: FakeClock
    bus: InMemoryBus
    wall: WallClock
    latency: LatencyRecorder


@pytest.fixture
async def world() -> AsyncIterator[World]:
    clock, bus, wall, latency = FakeClock(), InMemoryBus(), WallClock(), LatencyRecorder()
    registry = SessionRegistry(bus=bus, clock=clock, wall_ms=wall, latency=latency)
    yield World(registry, clock, bus, wall, latency)
    await registry.aclose()


async def drain(sub: Subscription) -> list[ServerMessage]:
    messages: list[ServerMessage] = []
    while True:
        try:
            message = await asyncio.wait_for(sub.get(), timeout=0.05)
        except TimeoutError:
            return messages
        if message is None:
            return messages
        messages.append(message)


def summary(messages: list[ServerMessage]) -> list[str]:
    out = []
    for m in messages:
        if m.type == "event" and isinstance(m.payload, MatchEvent):
            out.append(f"event:{m.payload.event_id}")
        elif m.type != "frame":
            out.append(m.type)
    return out


async def started(world: World) -> MatchSession:
    return await world.registry.create("skeleton")


async def test_create_starts_a_paused_session_with_metadata(world: World) -> None:
    session = await started(world)
    assert session.match_id == "demo-blue-amber-001"
    assert session.session_id.startswith("s-")
    assert session.state.metadata is not None
    assert session.playback.state == "paused"
    assert world.registry.get("demo-blue-amber-001") is session


async def test_unknown_scenario_is_rejected(world: World) -> None:
    with pytest.raises(UnknownScenarioError):
        await world.registry.create("space_creation")


async def test_playing_through_the_pass_broadcasts_events_metric_and_insight(world: World) -> None:
    session = await started(world)
    sub = session.hub.subscribe()
    await session.play()
    await world.clock.advance(4000)

    messages = await drain(sub)
    assert summary(messages) == [
        "event:evt-0040",
        "event:evt-0041",
        "event:evt-0042",
        "metric",
        "insight",
        "event:evt-0043",
    ]
    assert [m.seq for m in messages] == list(range(1, len(messages) + 1))
    insight = next(m for m in messages if m.type == "insight")
    assert isinstance(insight.payload, InsightBundle)
    assert len(insight.payload.variants) == 4
    assert insight.payload.variants[0].body == FAN_EN
    assert insight.server_receipt_ms == world.wall.now
    assert sum(1 for m in messages if m.type == "frame") == 41


async def test_ingest_stamps_receipt_time(world: World) -> None:
    session = await started(world)
    world.wall.now += 250
    await session.play()
    await world.clock.advance(0)
    stored = session.state.envelope("event", "evt-0040")
    assert stored is not None
    assert stored.server_receipt_ms == world.wall.now


async def test_schema_invalid_envelope_is_dropped(world: World, skeleton: list[FeedEnvelope]) -> None:
    session = await started(world)
    version = session.state.state_version
    bad = skeleton[1].model_copy(update={"published_ms": -5})
    await world.bus.publish(bad)
    await world.clock.advance(0)
    assert session.rejected_count == 1
    assert session.state.state_version == version


async def test_duplicate_envelope_is_broadcast_once(world: World, skeleton: list[FeedEnvelope]) -> None:
    session = await started(world)
    sub = session.hub.subscribe()
    await world.bus.publish(skeleton[1])
    await world.bus.publish(skeleton[1])
    await world.clock.advance(0)
    assert summary(await drain(sub)) == ["event:evt-0040"]


async def test_failed_output_check_sends_fallback_status_instead_of_insight(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = session_module.build_fact_bundle

    def tampered(*args: object, **kwargs: object) -> InsightBundle:
        bundle = real(*args, **kwargs)
        variants = [v.model_copy(update={"body": v.body.replace("13.1", "14.0")}) for v in bundle.variants]
        return bundle.model_copy(update={"variants": variants})

    monkeypatch.setattr(session_module, "build_fact_bundle", tampered)
    session = await started(world)
    sub = session.hub.subscribe()
    await session.play()
    await world.clock.advance(3000)

    messages = await drain(sub)
    assert "insight" not in summary(messages)
    status = next(m for m in messages if m.type == "narrative_status")
    assert isinstance(status.payload, NarrativeStatus)
    assert (status.payload.moment_id, status.payload.stage, status.payload.fallback_reason) == (
        "mom-0042",
        "fallback",
        "output_check_failed",
    )
    assert session.insights == {}


async def test_reset_clears_state_and_pushes_an_empty_snapshot(world: World) -> None:
    session = await started(world)
    await session.play()
    await world.clock.advance(4000)
    sub = session.hub.subscribe()
    head = session.hub.head_seq

    await session.reset()
    await world.clock.advance(0)
    messages = await drain(sub)
    assert [m.type for m in messages] == ["snapshot"]
    snapshot = messages[0].payload
    assert isinstance(snapshot, Snapshot)
    assert messages[0].seq == head + 1
    assert (snapshot.events, snapshot.insights, snapshot.session_clock_ms) == ([], [], 0)
    assert snapshot.playback.state == "paused"
    assert session.insights == {}
    assert "evt-0042" not in session.evidence

    await session.play()
    await world.clock.advance(4000)
    assert summary(await drain(sub)).count("insight") == 1


async def test_creating_the_same_scenario_again_resets_the_running_session(world: World) -> None:
    first = await started(world)
    await first.play()
    await world.clock.advance(1000)
    second = await world.registry.create("skeleton")
    await world.clock.advance(0)
    assert second is first
    assert second.playback.state == "paused"
    assert second.state.events == []


async def test_display_ack_records_fast_overlay_latency_from_receipt(world: World) -> None:
    session = await started(world)
    await session.play()
    await world.clock.advance(3000)
    world.wall.now += 420

    ack = DisplayAckMsg(type="display_ack", target_kind="insight", target_id="ins-0042", server_seq=9)
    assert session.record_display_ack(ack) == 420
    unknown = DisplayAckMsg(type="display_ack", target_kind="event", target_id="evt-0999", server_seq=9)
    assert session.record_display_ack(unknown) is None
    samples = world.latency.samples("fast_overlay")
    assert [s.ms for s in samples] == [420]
    assert samples[0].attrs["target_kind"] == "insight"


def pass_variant(skeleton: list[FeedEnvelope], **changes: object) -> FeedEnvelope:
    """evt-0042 re-timed to session time 0 so it is due while the session is still paused at 0."""
    original = next(env for env in skeleton if env.record_id == "evt-0042")
    assert isinstance(original.payload, MatchEvent)
    timed = {"session_clock_ms": 0, "period_clock_ms": 0, **changes}
    return original.model_copy(update={"payload": original.payload.model_copy(update=timed)})


async def published_alone(world: World, envelope: FeedEnvelope) -> list[ServerMessage]:
    session = await started(world)
    sub = session.hub.subscribe()
    await world.bus.publish(envelope)
    await world.clock.advance(0)
    return await drain(sub)


@pytest.mark.parametrize(("end_m", "progress"), [((50.0, 28.0), -8.1), ((58.1, 20.0), 0.0)])
async def test_backward_or_zero_progress_pass_gets_no_card(
    world: World, skeleton: list[FeedEnvelope], end_m: tuple[float, float], progress: float
) -> None:
    messages = await published_alone(world, pass_variant(skeleton, end_m=end_m))
    assert summary(messages) == ["event:evt-0042", "metric"]
    metric = messages[1].payload
    assert getattr(metric, "value", None) == progress


async def test_pass_without_outcome_gets_an_attempted_card(
    world: World, skeleton: list[FeedEnvelope]
) -> None:
    messages = await published_alone(world, pass_variant(skeleton, outcome=None, recipient_id=None))
    assert summary(messages) == ["event:evt-0042", "metric", "insight"]
    bundle = messages[2].payload
    assert isinstance(bundle, InsightBundle)
    assert bundle.variants[0].body == "Blue 8 attempted a forward pass."


async def test_backward_pass_without_outcome_gets_no_card(world: World, skeleton: list[FeedEnvelope]) -> None:
    variant = pass_variant(skeleton, outcome=None, recipient_id=None, end_m=(50.0, 28.0))
    assert summary(await published_alone(world, variant)) == ["event:evt-0042", "metric"]


async def test_incomplete_pass_gets_no_card(world: World, skeleton: list[FeedEnvelope]) -> None:
    variant = pass_variant(skeleton, outcome="incomplete")
    assert summary(await published_alone(world, variant)) == ["event:evt-0042"]


class SilentBus(InMemoryBus):
    async def publish(self, envelope: FeedEnvelope) -> None:
        return None


async def test_session_whose_metadata_never_arrives_is_not_registered() -> None:
    registry = SessionRegistry(SilentBus(), FakeClock(), LatencyRecorder(), ready_timeout_s=0.05)
    with pytest.raises(SessionStartError):
        await registry.create("skeleton")
    assert registry.get("demo-blue-amber-001") is None
    await registry.aclose()
