"""`forward_progress.v1`: how far a pass moves the ball along the passing team's attack direction."""

from __future__ import annotations

from tactistream.contracts import MatchEvent, MatchMetadata, MetricInputs, MetricResult, MetricWindow

DEFINITION_VERSION = "forward_progress.v1"


def compute_forward_progress(event: MatchEvent, metadata: MatchMetadata, state_version: int) -> MetricResult:
    """(end_x - start_x) x attack sign, metres, 1 decimal. Measures the attempt, whatever its outcome."""
    if event.event_type != "pass" or event.end_m is None or event.duration_ms is None:
        raise ValueError(f"forward_progress needs a pass event, got {event.event_type} {event.event_id}")
    period = next((p for p in metadata.periods if p.period == event.period), None)
    if period is None:
        raise ValueError(f"no attack direction for period {event.period}")
    direction = period.attack_direction
    sign = direction.blue if event.team_id == "blue" else direction.amber
    value = round((event.end_m[0] - event.start_m[0]) * sign, 1)
    subjects = [event.player_id] + ([event.recipient_id] if event.recipient_id else [])
    return MetricResult(
        schema_version="1.0",
        match_id=event.match_id,
        metric_id=f"metric-forward_progress-{event.sequence:04d}",
        kind="forward_progress",
        definition_version=DEFINITION_VERSION,
        status="ok",
        value=value,
        unit="m",
        subject_ids=subjects,
        window=MetricWindow(
            start_ms=event.session_clock_ms, end_ms=event.session_clock_ms + event.duration_ms
        ),
        inputs=MetricInputs(event_ids=[event.event_id], frame_ids=[]),
        state_version=state_version,
    )
