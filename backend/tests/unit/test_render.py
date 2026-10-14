import itertools

import pytest

from tactistream.contracts import Language, MatchEvent, MatchMetadata, SlotValue, ViewerMode
from tactistream.metrics.forward_progress import compute_forward_progress
from tactistream.narrative.render import (
    RenderContext,
    TemplateError,
    load_catalog,
    render_claim,
    render_title,
)

FAN_EN = "Blue 8 played a forward pass to Blue 11 (13.1 m forward)."
FAN_HI = "ब्लू 8 ने ब्लू 11 को आगे की ओर पास दिया (13.1 मी आगे)।"

SLOTS = {
    "passer": SlotValue(kind="player", player_id="blue-08"),
    "receiver": SlotValue(kind="player", player_id="blue-11"),
    "progress": SlotValue(kind="metric", metric_id="metric-forward_progress-0042"),
}


@pytest.fixture
def context(pass_event: MatchEvent, metadata: MatchMetadata) -> RenderContext:
    metric = compute_forward_progress(pass_event, metadata, state_version=5)
    return RenderContext(metadata=metadata, metrics={metric.metric_id: metric})


def test_fan_english_sentence(context: RenderContext) -> None:
    rendered = render_claim("fact.forward_pass", SLOTS, "fan", "en", context=context)
    assert rendered.text == FAN_EN
    assert rendered.numbers == ["13.1"]
    assert rendered.player_ids == ["blue-08", "blue-11"]


def test_analyst_english_adds_axis_progress_with_event_reference(context: RenderContext) -> None:
    rendered = render_claim("fact.forward_pass", SLOTS, "analyst", "en", context=context)
    assert rendered.text == f"{FAN_EN} Progress along attack axis: 13.1 m (evt-0042)."


def test_fan_hindi_uses_hindi_names_and_western_digits(context: RenderContext) -> None:
    rendered = render_claim("fact.forward_pass", SLOTS, "fan", "hi", context=context)
    assert "ब्लू 8" in rendered.text
    assert "ब्लू 11" in rendered.text
    assert "13.1" in rendered.text
    assert rendered.text == FAN_HI


def test_all_four_variants_carry_identical_numbers_and_players(context: RenderContext) -> None:
    modes: tuple[ViewerMode, ...] = ("fan", "analyst")
    languages: tuple[Language, ...] = ("en", "hi")
    variants = [
        render_claim("fact.forward_pass", SLOTS, mode, language, context=context)
        for mode, language in itertools.product(modes, languages)
    ]
    assert {tuple(v.numbers) for v in variants} == {("13.1",)}
    assert {tuple(v.player_ids) for v in variants} == {("blue-08", "blue-11")}
    assert len({v.text for v in variants}) == 4


def test_missing_slot_raises(context: RenderContext) -> None:
    slots = {k: v for k, v in SLOTS.items() if k != "receiver"}
    with pytest.raises(TemplateError, match="receiver"):
        render_claim("fact.forward_pass", slots, "fan", "en", context=context)


def test_unknown_template_raises(context: RenderContext) -> None:
    with pytest.raises(TemplateError, match="fact.no_such_template"):
        render_claim("fact.no_such_template", SLOTS, "fan", "en", context=context)


def test_slot_of_the_wrong_kind_raises(context: RenderContext) -> None:
    slots = {**SLOTS, "passer": SlotValue(kind="team", team_id="blue")}
    with pytest.raises(TemplateError, match="passer"):
        render_claim("fact.forward_pass", slots, "fan", "en", context=context)


def test_unknown_player_or_metric_raises(context: RenderContext) -> None:
    with pytest.raises(TemplateError, match="metric-forward_progress-0099"):
        render_claim(
            "fact.forward_pass",
            {**SLOTS, "progress": SlotValue(kind="metric", metric_id="metric-forward_progress-0099")},
            "fan",
            "en",
            context=context,
        )
    with pytest.raises(TemplateError, match="amber-99"):
        render_claim(
            "fact.forward_pass",
            {**SLOTS, "receiver": SlotValue(kind="player", player_id="amber-99")},
            "fan",
            "en",
            context=context,
        )


def test_unavailable_metric_raises(context: RenderContext) -> None:
    metric = context.metrics["metric-forward_progress-0042"]
    unavailable = metric.model_copy(
        update={"status": "unavailable", "value": None, "unit": None, "unavailable_reason": "not_applicable"}
    )
    broken = RenderContext(metadata=context.metadata, metrics={metric.metric_id: unavailable})
    with pytest.raises(TemplateError, match="unavailable"):
        render_claim("fact.forward_pass", SLOTS, "fan", "en", context=broken)


def test_title_has_no_numbers() -> None:
    assert render_title("title.forward_pass", "fan", "en").text == "Forward pass"
    hindi = render_title("title.forward_pass", "analyst", "hi")
    assert hindi.text
    assert hindi.numbers == []


def test_catalogs_have_the_same_keys_and_cover_the_skeleton_entries() -> None:
    en, hi = load_catalog("en"), load_catalog("hi")
    assert en.keys() == hi.keys()
    assert {
        "title.forward_pass",
        "fact.forward_pass",
        "status.insufficient_tracking",
        "label.synthetic",
        "label.interpretation",
    } <= en.keys()
    assert "_meta" not in en
