"""Match sessions: replay -> ingest -> state -> metric -> fact card -> checks -> WebSocket fan-out."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
import time
from collections.abc import AsyncIterator, Callable, Sequence
from functools import cache
from pathlib import Path

from tactistream.agents.checks import check_packet
from tactistream.api.evidence import EvidenceIndex
from tactistream.api.ws_hub import WsHub
from tactistream.contracts import (
    ContractError,
    DisplayAckMsg,
    FeedEnvelope,
    InsightBundle,
    MatchEvent,
    NarrativeStatus,
    ServerMessage,
    SnapshotPlayback,
    TrackingFrame,
    validate,
)
from tactistream.metrics.forward_progress import compute_forward_progress
from tactistream.narrative.factual import build_fact_bundle
from tactistream.narrative.render import TemplateError
from tactistream.state.match_state import MatchState, StateDelta
from tactistream.telemetry.latency import LatencyRecorder
from tactistream.transport.bus import FeedBus
from tactistream.transport.clock import Clock
from tactistream.transport.fixtures import load_fixture, skeleton_fixture_path
from tactistream.transport.replayer import FeedReplayer

logger = logging.getLogger(__name__)

LIVE_STATE_GROUP = "live-state"
READY_TIMEOUT_S = 5.0
SCENARIOS: dict[str, Callable[[], Path]] = {"skeleton": skeleton_fixture_path}

WallClock = Callable[[], int]


def wall_clock_ms() -> int:
    return time.time_ns() // 1_000_000


class UnknownScenarioError(ValueError):
    pass


@cache
def _scenario_records(path: Path) -> tuple[FeedEnvelope, ...]:
    return tuple(load_fixture(path))


class MatchSession:
    """One replay of one match, its live state, evidence index and WebSocket hub."""

    def __init__(
        self,
        records: Sequence[FeedEnvelope],
        bus: FeedBus,
        clock: Clock,
        wall_ms: WallClock,
        latency: LatencyRecorder,
    ) -> None:
        self.session_id = f"s-{secrets.token_hex(6)}"
        self.match_id = records[0].match_id
        self.replayer = FeedReplayer(records, bus, clock)
        self.state = MatchState()
        self.hub = WsHub(self.match_id)
        self.evidence = EvidenceIndex()
        self.insights: dict[str, InsightBundle] = {}
        self.rejected_count = 0
        self._wall_ms = wall_ms
        self._latency = latency
        self._insight_receipts: dict[str, int] = {}
        self._resets_pending = 0
        self._snapshot_after_reset = False
        self._ready = asyncio.Event()

    @property
    def playback(self) -> SnapshotPlayback:
        seed = self.state.metadata.source.seed if self.state.metadata else None
        return SnapshotPlayback(state=self.replayer.state.value, speed=self.replayer.speed, seed=seed or 0)

    async def start(self) -> None:
        """Publish the metadata and wait until it has been ingested, so snapshots are always possible."""
        await self.reset()
        await asyncio.wait_for(self._ready.wait(), timeout=READY_TIMEOUT_S)

    async def play(self) -> None:
        await self.replayer.play()

    def pause(self) -> None:
        self.replayer.pause()

    async def reset(self) -> None:
        """Rewind the replay; live state is cleared when the republished metadata comes back off the bus,
        so envelopes already in flight from the previous run never leak into the new one."""
        self._resets_pending += 1
        await self.replayer.reset()

    async def aclose(self) -> None:
        await self.replayer.aclose()
        self.hub.close()

    def snapshot(self) -> ServerMessage:
        return self.hub.snapshot_for(
            self.state,
            session_clock_ms=self.replayer.session_clock_ms,
            playback=self.playback,
            insights=list(self.insights.values()),
        )

    def ingest(self, envelope: FeedEnvelope) -> StateDelta | None:
        """Validate against the contract, stamp `server_receipt_ms`, dedupe/apply, then fan out."""
        try:
            validate("feed_envelope.schema.json", envelope.model_dump(mode="json", exclude_none=True))
        except ContractError as exc:
            self.rejected_count += 1
            logger.warning("rejected envelope %s/%s: %s", envelope.kind, envelope.record_id, exc)
            return None
        stamped = envelope.model_copy(update={"server_receipt_ms": self._wall_ms()})
        if stamped.kind == "metadata" and self._resets_pending > 0:
            self._resets_pending -= 1
            self._clear(snapshot=self.state.state_version > 0)
        delta = self.state.apply(stamped)
        if not delta.duplicate:
            self._on_delta(stamped, delta)
        return delta

    def record_display_ack(self, ack: DisplayAckMsg) -> int | None:
        """fast_overlay = ack receipt - target server receipt (upper bound: includes the ack trip)."""
        if ack.target_kind == "insight":
            receipt = self._insight_receipts.get(ack.target_id)
        else:
            stored = self.state.envelope("event", ack.target_id)
            receipt = stored.server_receipt_ms if stored else None
        if receipt is None:
            return None
        latency_ms = max(self._wall_ms() - receipt, 0)
        self._latency.record(
            "fast_overlay", latency_ms, {"target_kind": ack.target_kind, "match_id": self.match_id}
        )
        return latency_ms

    def _clear(self, *, snapshot: bool) -> None:
        self.state = MatchState()
        self.evidence.clear()
        self.insights.clear()
        self._insight_receipts.clear()
        self._snapshot_after_reset = snapshot

    def _on_delta(self, envelope: FeedEnvelope, delta: StateDelta) -> None:
        receipt = envelope.server_receipt_ms
        payload = envelope.payload
        if delta.new_metadata is not None:
            self._ready.set()
            if self._snapshot_after_reset:
                self._snapshot_after_reset = False
                self.hub.broadcast("snapshot", self.snapshot().payload)
        elif isinstance(payload, MatchEvent):
            self.evidence.add("event", payload, payload.session_clock_ms)
            self.hub.broadcast("event", payload, server_receipt_ms=receipt)
            if payload.event_type == "pass" and payload.outcome == "complete":
                self._explain_pass(payload, receipt)
        elif isinstance(payload, TrackingFrame):
            self.evidence.add("frame", payload, payload.session_clock_ms)
            if delta.new_frame is not None:
                self.hub.broadcast("frame", payload, server_receipt_ms=receipt)

    def _explain_pass(self, event: MatchEvent, receipt: int | None) -> None:
        metadata = self.state.metadata
        if metadata is None:
            logger.warning("pass %s arrived before metadata; no card", event.event_id)
            return
        now_ms = self.replayer.session_clock_ms
        trace_id = secrets.token_hex(16)
        metric = compute_forward_progress(event, metadata, self.state.state_version)
        self.evidence.add("metric", metric, event.session_clock_ms)
        self.hub.broadcast("metric", metric, server_receipt_ms=receipt)
        moment_id = f"mom-{event.sequence:04d}"
        try:
            bundle = build_fact_bundle(event, metric, metadata, self.state.state_version, trace_id, now_ms)
        except (TemplateError, ValueError) as exc:
            logger.warning("fact card for %s could not be rendered: %s", event.event_id, exc)
            self._fallback(moment_id, trace_id)
            return
        failures = [
            f for packet in bundle.variants for f in check_packet(packet, self.evidence, metadata, now_ms)
        ]
        if failures:
            logger.warning("fact card %s failed output checks: %s", bundle.insight_id, failures)
            self._fallback(moment_id, trace_id)
            return
        self.insights[bundle.insight_id] = bundle
        if receipt is not None:
            self._insight_receipts[bundle.insight_id] = receipt
        self.hub.broadcast("insight", bundle, server_receipt_ms=receipt)

    def _fallback(self, moment_id: str, trace_id: str) -> None:
        status = NarrativeStatus(
            moment_id=moment_id, stage="fallback", fallback_reason="output_check_failed", trace_id=trace_id
        )
        self.hub.broadcast("narrative_status", status)


class SessionRegistry:
    """In-memory sessions keyed by match_id, fed by one `live-state` consumer for the whole process."""

    def __init__(
        self,
        bus: FeedBus,
        clock: Clock,
        latency: LatencyRecorder,
        wall_ms: WallClock = wall_clock_ms,
    ) -> None:
        self._bus = bus
        self._clock = clock
        self._latency = latency
        self._wall_ms = wall_ms
        self._sessions: dict[str, MatchSession] = {}
        self._consumer: asyncio.Task[None] | None = None

    def get(self, match_id: str) -> MatchSession | None:
        return self._sessions.get(match_id)

    async def create(self, scenario: str) -> MatchSession:
        """Start a session for the scenario; one already running for that match is reset and reused."""
        locate = SCENARIOS.get(scenario)
        if locate is None:
            raise UnknownScenarioError(f"unknown scenario {scenario!r}")
        records = _scenario_records(locate())
        existing = self._sessions.get(records[0].match_id)
        if existing is not None:
            await existing.reset()
            return existing
        if self._consumer is None:
            self._consumer = asyncio.create_task(self._consume(self._bus.subscribe(LIVE_STATE_GROUP)))
        session = MatchSession(records, self._bus, self._clock, self._wall_ms, self._latency)
        self._sessions[session.match_id] = session
        await session.start()
        return session

    async def aclose(self) -> None:
        for session in self._sessions.values():
            await session.aclose()
        self._sessions.clear()
        if self._consumer is not None:
            self._consumer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._consumer
            self._consumer = None

    async def _consume(self, stream: AsyncIterator[FeedEnvelope]) -> None:
        async for envelope in stream:
            session = self._sessions.get(envelope.match_id)
            if session is None:
                continue
            try:
                session.ingest(envelope)
            except Exception:
                logger.exception("ingest failed for %s/%s", envelope.kind, envelope.record_id)
