"""Catalog-driven rendering of 004 templates.

Built on hand-constructed contract objects (skeleton metadata, contract-example metrics, a hero-like
shot) until 003's hero world exists; the hero-world variant of these assertions lands with T008/T009.
"""

import itertools
import json
from pathlib import Path

import pytest

from tactistream.contracts import (
    Language,
    MatchEvent,
    MatchMetadata,
    MetricResult,
    SlotValue,
    ViewerMode,
)
from tactistream.metrics.forward_progress import compute_forward_progress
from tactistream.narrative.render import RenderContext, TemplateError, render_claim, render_title

EXAMPLES = Path(__file__).parents[3] / "contracts" / "examples"
VARIANTS: list[tuple[ViewerMode, Language]] = list(itertools.product(("fan", "analyst"), ("en", "hi")))

INTERP_SLOTS = {
    "runner": SlotValue(kind="player", player_id="blue-09"),
    "defender": SlotValue(kind="player", player_id="amber-04"),
    "channel_gain": SlotValue(kind="metric", metric_id="metric-channel-0042", value=3.4, unit="m"),
}
SHOT_SLOTS = {
    "shooter": SlotValue(kind="player", player_id="blue-11"),
    "shot": SlotValue(kind="event_time", event_id="evt-0045"),
}
PASS_SLOTS = {
    "passer": SlotValue(kind="player", player_id="blue-08"),
    "receiver": SlotValue(kind="player", player_id="blue-11"),
    "progress": SlotValue(kind="metric", metric_id="metric-forward_progress-0042"),
}


@pytest.fixture
def channel() -> MetricResult:
    data = json.loads((EXAMPLES / "metric_result.json").read_text(encoding="utf-8"))
    return MetricResult.model_validate(data)


@pytest.fixture
def shot(pass_event: MatchEvent) -> MatchEvent:
    return pass_event.model_copy(
        update={
            "event_id": "evt-0045",
            "sequence": 45,
            "event_type": "shot",
            "player_id": "blue-11",
            "recipient_id": None,
            "outcome": "on_target",
        }
    )


@pytest.fixture
def context(
    metadata: MatchMetadata, pass_event: MatchEvent, shot: MatchEvent, channel: MetricResult
) -> RenderContext:
    progress = compute_forward_progress(pass_event, metadata, state_version=5)
    return RenderContext(
        metadata=metadata,
        metrics={channel.metric_id: channel, progress.metric_id: progress},
        events={pass_event.event_id: pass_event, shot.event_id: shot},
    )


def test_interp_fan_english(context: RenderContext) -> None:
    rendered = render_claim("interp.space_opened_by_run", INTERP_SLOTS, "fan", "en", context=context)
    assert rendered.text == "Blue 9's run helped create room for the pass."


def test_interp_analyst_english(context: RenderContext) -> None:
    rendered = render_claim("interp.space_opened_by_run", INTERP_SLOTS, "analyst", "en", context=context)
    assert rendered.text == (
        "Amber 4 shifted toward Blue 9 while the passing channel widened by 3.4 m. "
        "The next forward pass used that space."
    )


def test_interp_hindi(context: RenderContext) -> None:
    fan = render_claim("interp.space_opened_by_run", INTERP_SLOTS, "fan", "hi", context=context).text
    assert "ब्लू 9" in fan
    analyst = render_claim("interp.space_opened_by_run", INTERP_SLOTS, "analyst", "hi", context=context).text
    assert "3.4" in analyst
    assert "एम्बर 4" in analyst


def test_engine_value_wins_over_agent_value(context: RenderContext) -> None:
    slots = {**INTERP_SLOTS, "channel_gain": INTERP_SLOTS["channel_gain"].model_copy(update={"value": 5.3})}
    rendered = render_claim("interp.space_opened_by_run", slots, "analyst", "en", context=context)
    assert "3.4 m" in rendered.text
    assert "5.3" not in rendered.text
    assert rendered.numbers == ["3.4"]


def test_unavailable_metric_slot_raises(context: RenderContext, channel: MetricResult) -> None:
    unavailable = channel.model_copy(
        update={"status": "unavailable", "value": None, "unavailable_reason": "insufficient_tracking"}
    )
    broken = RenderContext(
        metadata=context.metadata, metrics={channel.metric_id: unavailable}, events=context.events
    )
    with pytest.raises(TemplateError, match="unavailable"):
        render_claim("interp.space_opened_by_run", INTERP_SLOTS, "analyst", "en", context=broken)


def test_metric_of_a_kind_the_slot_does_not_allow_raises(context: RenderContext) -> None:
    slots = {**INTERP_SLOTS, "channel_gain": PASS_SLOTS["progress"]}
    with pytest.raises(TemplateError, match="channel_gain"):
        render_claim("interp.space_opened_by_run", slots, "analyst", "en", context=context)


def test_metric_lookup_takes_precedence(context: RenderContext, channel: MetricResult) -> None:
    seen: list[str] = []

    def lookup(metric_id: str) -> MetricResult:
        seen.append(metric_id)
        return channel.model_copy(update={"value": 2.0})

    rendered = render_claim(
        "interp.space_opened_by_run", INTERP_SLOTS, "analyst", "en", context=context, metric_lookup=lookup
    )
    assert "widened by 2.0 m" in rendered.text
    assert seen == ["metric-channel-0042"]


def test_metric_lookup_key_error_is_a_template_error(context: RenderContext) -> None:
    def lookup(metric_id: str) -> MetricResult:
        raise KeyError(metric_id)

    with pytest.raises(TemplateError, match="metric-channel-0042"):
        render_claim(
            "interp.space_opened_by_run", INTERP_SLOTS, "fan", "en", context=context, metric_lookup=lookup
        )


def test_shot_fact_with_derived_outcome(context: RenderContext) -> None:
    assert render_claim("fact.shot", SHOT_SLOTS, "fan", "en", context=context).text == (
        "Blue 11 took a shot: on target."
    )
    analyst = render_claim("fact.shot", SHOT_SLOTS, "analyst", "en", context=context).text
    assert analyst == "Blue 11 took a shot: on target (evt-0045)."
    assert render_claim("fact.shot", SHOT_SLOTS, "fan", "hi", context=context).text == (
        "ब्लू 11 ने शॉट लिया: लक्ष्य पर।"
    )


def test_event_time_slot_needs_a_known_event(context: RenderContext) -> None:
    slots = {**SHOT_SLOTS, "shot": SlotValue(kind="event_time", event_id="evt-0099")}
    with pytest.raises(TemplateError, match="evt-0099"):
        render_claim("fact.shot", slots, "fan", "en", context=context)


def test_turnover_renders_team_and_event(context: RenderContext, shot: MatchEvent) -> None:
    turnover = shot.model_copy(
        update={
            "event_id": "evt-0061",
            "event_type": "interception",
            "player_id": "amber-06",
            "team_id": "amber",
            "outcome": "won",
        }
    )
    ctx = RenderContext(metadata=context.metadata, events={turnover.event_id: turnover})
    slots = {
        "winner": SlotValue(kind="player", player_id="amber-06"),
        "loser_team": SlotValue(kind="team", team_id="blue"),
        "event": SlotValue(kind="event_time", event_id="evt-0061"),
    }
    fan = render_claim("fact.turnover", slots, "fan", "en", context=ctx).text
    assert fan == "Amber 6 won the ball from Blue."
    assert render_claim("fact.turnover", slots, "analyst", "en", context=ctx).text == (
        "Amber 6 won possession from Blue (evt-0061)."
    )


def test_status_template_renders_without_slots() -> None:
    assert render_claim("status.insufficient_tracking", {}, "fan", "en", context=None).text == (
        "Insufficient tracking for this explanation."
    )
    assert render_claim("status.insufficient_tracking", {}, "analyst", "hi", context=None).text == (
        "इस व्याख्या के लिए पर्याप्त ट्रैकिंग नहीं है।"
    )


CLAIMS: list[tuple[str, dict[str, SlotValue]]] = [
    ("interp.space_opened_by_run", INTERP_SLOTS),
    ("fact.shot", SHOT_SLOTS),
    ("fact.forward_pass", PASS_SLOTS),
]


@pytest.mark.parametrize(("template_id", "slots"), CLAIMS, ids=[c[0] for c in CLAIMS])
def test_numbers_identical_across_variants(
    context: RenderContext, template_id: str, slots: dict[str, SlotValue]
) -> None:
    numbers = {
        tuple(render_claim(template_id, slots, mode, language, context=context).numbers)
        for mode, language in VARIANTS
    }
    assert len(numbers) == 1


@pytest.mark.parametrize(
    ("template_id", "en", "hi"),
    [
        ("title.space_opened_before_shot", "Space opened before the shot", "शॉट से पहले जगह बनी"),
        ("title.space_opened_before_pass", "Space opened before the pass", "पास से पहले जगह बनी"),
        ("title.shot", "Shot", "शॉट"),
        ("title.turnover", "Ball won", "गेंद जीती"),
    ],
)
def test_titles(template_id: str, en: str, hi: str) -> None:
    for mode in ("fan", "analyst"):
        assert render_title(template_id, mode, "en").text == en
        assert render_title(template_id, mode, "hi").text == hi


def test_render_title_rejects_non_titles() -> None:
    with pytest.raises(TemplateError):
        render_title("fact.shot", "fan", "en")
