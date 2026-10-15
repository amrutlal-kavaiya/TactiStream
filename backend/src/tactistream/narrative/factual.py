"""Deterministic fact card for a completed pass; the same path 004 falls back to when agents fail."""

from __future__ import annotations

import itertools

from tactistream.contracts import (
    InsightBundle,
    InsightPacket,
    Language,
    MatchEvent,
    MatchMetadata,
    MetricResult,
    RenderSpec,
    SlotValue,
    ViewerMode,
)
from tactistream.contracts.insight import InsightLabel
from tactistream.narrative.render import RenderContext, render_claim, render_title

SHOW_FOR_MS = 6000
EXPIRES_AFTER_MS = 30000
MODES: tuple[ViewerMode, ...] = ("fan", "analyst")
LANGUAGES: tuple[Language, ...] = ("en", "hi")


def build_fact_bundle(
    event: MatchEvent,
    metric: MetricResult,
    metadata: MatchMetadata,
    state_version: int,
    trace_id: str,
    now_session_ms: int,
) -> InsightBundle:
    """Fact card in every (mode, language), shown from the end of the pass for 6 s.

    A completed pass gets `fact.forward_pass`; a pass without a recorded outcome gets `fact.pass_attempted`
    (no progress number). Either needs positive forward progress.
    """
    if event.event_type != "pass":
        raise ValueError(f"fact cards need a pass, got {event.event_type} {event.event_id}")
    if metric.value is None or metric.value <= 0:
        raise ValueError(f"fact cards need positive forward progress, got {metric.value}")
    passer = SlotValue(kind="player", player_id=event.player_id)
    if event.outcome == "complete" and event.recipient_id is not None:
        template, title_template = "fact.forward_pass", "title.forward_pass"
        slots = {
            "passer": passer,
            "receiver": SlotValue(kind="player", player_id=event.recipient_id),
            "progress": SlotValue(kind="metric", metric_id=metric.metric_id),
        }
    elif event.outcome is None:
        template, title_template = "fact.pass_attempted", "title.pass_attempted"
        slots = {"passer": passer}
    else:
        raise ValueError(f"no fact card for a pass with outcome {event.outcome} ({event.event_id})")
    context = RenderContext(metadata=metadata, metrics={metric.metric_id: metric})
    show_from_ms = event.session_clock_ms + (event.duration_ms or 0)
    render = RenderSpec(
        clock="session_clock_ms",
        show_from_ms=show_from_ms,
        show_until_ms=show_from_ms + SHOW_FOR_MS,
        priority=3,
        panel="lower_third",
        annotations=[],
    )
    insight_id = f"ins-{event.sequence:04d}"
    labels: list[InsightLabel] = ["synthetic"] if event.source.kind == "synthetic" else []
    variants = [
        InsightPacket(
            schema_version="1.0",
            insight_id=insight_id,
            insight_version=1,
            match_id=event.match_id,
            moment_id=f"mom-{event.sequence:04d}",
            state_version=state_version,
            as_of_session_ms=now_session_ms,
            mode=mode,
            language=language,
            source_kind=event.source.kind,
            claim_status="verified_fact",
            title=render_title(title_template, mode, language).text,
            body=render_claim(template, slots, mode, language, context=context).text,
            labels=labels,
            evidence_ids=[event.event_id, metric.metric_id],
            claim_ids=[],
            render=render,
            expires_at_session_ms=show_from_ms + EXPIRES_AFTER_MS,
            trace_id=trace_id,
        )
        for mode, language in itertools.product(MODES, LANGUAGES)
    ]
    return InsightBundle(insight_id=insight_id, insight_version=1, variants=variants)
