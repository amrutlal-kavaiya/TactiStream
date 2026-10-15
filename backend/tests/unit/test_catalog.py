import json
import re
from pathlib import Path
from typing import Any

import pytest

from tactistream.agents.checks import CAUSAL_LEXICON, find_causal_terms
from tactistream.narrative.templates import DERIVED_SLOTS, Catalog, TemplateError, load_catalog

CATALOG_DIR = Path(__file__).parents[2] / "src" / "tactistream" / "narrative" / "catalog"
PLACEHOLDER = re.compile(r"\{([a-z_]+)(?:\.[a-z_]+)?\}")
CLAIM_KINDS = {"fact", "interpretation", "status"}
SINGLE_TEXT_KINDS = {"title", "phrase", "label"}


def raw(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((CATALOG_DIR / name).read_text(encoding="utf-8"))
    data.pop("_meta", None)
    return data


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog()


def test_load_catalog_is_cached(catalog: Catalog) -> None:
    assert load_catalog() is catalog
    assert catalog.version == "1.1"


def test_spec_and_language_files_have_identical_keys() -> None:
    spec_keys = set(raw("spec.json")["templates"])
    assert set(raw("en.json")) == spec_keys
    assert set(raw("hi.json")) == spec_keys


def test_001_keys_are_kept(catalog: Catalog) -> None:
    for key in (
        "fact.forward_pass",
        "title.forward_pass",
        "fact.pass_attempted",
        "title.pass_attempted",
        "label.synthetic",
        "label.interpretation",
        "status.insufficient_tracking",
    ):
        assert catalog.has(key), key


def test_every_data_model_template_is_present(catalog: Catalog) -> None:
    expected = {
        "fact.shot": "fact",
        "fact.turnover": "fact",
        "fact.switch": "fact",
        "interp.space_opened_by_run": "interpretation",
        "interp.defender_followed_runner": "interpretation",
        "interp.pressure_preceded_turnover": "interpretation",
        "interp.switch_escaped_pressure": "interpretation",
        "title.shot": "title",
        "title.turnover": "title",
        "title.switch": "title",
        "title.space_opened_before_shot": "title",
        "title.space_opened_before_pass": "title",
        "title.runner_tracked": "title",
        "title.pressure_before_turnover": "title",
        "title.switch_escape": "title",
        "outcome.on_target": "phrase",
        "outcome.off_target": "phrase",
        "outcome.blocked": "phrase",
        "outcome.goal": "phrase",
    }
    assert {key: catalog.spec(key).kind for key in expected} == expected


@pytest.mark.parametrize("language", ["en", "hi"])
def test_claim_and_status_templates_have_fan_and_analyst_text(language: str) -> None:
    texts = raw(f"{language}.json")
    kinds = {key: spec["kind"] for key, spec in raw("spec.json")["templates"].items()}
    for key, kind in kinds.items():
        if kind in CLAIM_KINDS:
            assert set(texts[key]) == {"fan", "analyst"}, key
            assert texts[key]["fan"] and texts[key]["analyst"], key
        else:
            assert kind in SINGLE_TEXT_KINDS, key
            assert set(texts[key]) == {"text"}, key
            assert texts[key]["text"], key


@pytest.mark.parametrize("language", ["en", "hi"])
def test_placeholders_match_declared_slots(catalog: Catalog, language: str) -> None:
    texts = raw(f"{language}.json")
    for key in catalog.keys(""):
        spec = catalog.spec(key)
        used = {name for text in texts[key].values() for name in PLACEHOLDER.findall(text)}
        assert used <= set(spec.slots) | set(DERIVED_SLOTS), key
        assert set(spec.slots) <= used, key
        for name in used & set(DERIVED_SLOTS):
            assert [s for s in spec.slots.values() if s.type == "event_time"], f"{key} derives {name}"


@pytest.mark.parametrize("language", ["en", "hi"])
def test_event_time_slots_appear_only_in_analyst_text(catalog: Catalog, language: str) -> None:
    for key in catalog.keys(""):
        spec = catalog.spec(key)
        if spec.kind not in CLAIM_KINDS:
            continue
        fan = set(PLACEHOLDER.findall(catalog.text(key, "fan", language)))
        assert not {name for name, slot in spec.slots.items() if slot.type == "event_time"} & fan, key


def test_metric_slots_declare_kinds_unit_and_precision(catalog: Catalog) -> None:
    for key in catalog.keys(""):
        for name, slot in catalog.spec(key).slots.items():
            if slot.type == "metric":
                assert slot.metric_kinds, (key, name)
                assert slot.unit is not None, (key, name)
                assert slot.precision >= 0, (key, name)


def test_data_model_slot_specs(catalog: Catalog) -> None:
    channel = catalog.spec("interp.space_opened_by_run").slots["channel_gain"]
    assert (channel.metric_kinds, channel.unit, channel.precision) == (("channel",), "m", 1)
    follow = catalog.spec("interp.defender_followed_runner").slots["follow"]
    assert (follow.metric_kinds, follow.unit, follow.precision) == (("defender_follow",), "cosine", 2)
    pressure = catalog.spec("interp.pressure_preceded_turnover").slots["pressure"]
    assert (pressure.metric_kinds, pressure.unit, pressure.precision) == (("pressure",), "score_0_100", 0)
    assert catalog.spec("fact.shot").slots["shot"].type == "event_time"
    assert catalog.spec("fact.turnover").slots["loser_team"].type == "team"
    assert catalog.spec("interp.space_opened_by_run").required_evidence_kinds == (
        "off_ball_run",
        "defender_follow",
        "channel",
    )


def test_title_keys_exist_with_kind_title(catalog: Catalog) -> None:
    for key in catalog.keys(""):
        for title in catalog.spec(key).title_keys:
            assert catalog.spec(title).kind == "title", (key, title)
    assert catalog.spec("interp.space_opened_by_run").title_keys == (
        "title.space_opened_before_shot",
        "title.space_opened_before_pass",
    )


def test_interpretations_require_tracking_and_evidence(catalog: Catalog) -> None:
    interpretations = catalog.keys("interp.")
    assert len(interpretations) == 4
    for key in interpretations:
        spec = catalog.spec(key)
        assert spec.kind == "interpretation"
        assert spec.requires_tracking is True, key
        assert spec.required_evidence_kinds, key


@pytest.mark.parametrize("pattern", ["space_creation", "press_turnover", "switch_escape", "shot"])
def test_every_explained_pattern_has_templates(catalog: Catalog, pattern: str) -> None:
    eligible = catalog.claim_templates(pattern)
    assert [s for s in eligible if s.kind == "fact"], pattern
    if pattern != "shot":
        assert [s for s in eligible if s.kind == "interpretation"], pattern


def test_claim_templates_for_space_creation(catalog: Catalog) -> None:
    keys = {spec.key for spec in catalog.claim_templates("space_creation")}
    assert keys == {
        "fact.forward_pass",
        "fact.shot",
        "interp.space_opened_by_run",
        "interp.defender_followed_runner",
    }


@pytest.mark.parametrize("language", ["en", "hi"])
def test_no_template_contains_causal_overreach(catalog: Catalog, language: str) -> None:
    for key in catalog.keys(""):
        for mode in ("fan", "analyst"):
            text = catalog.text(key, mode, language)
            assert find_causal_terms(text) == [], (key, mode, text)


def test_hindi_text_uses_western_digits() -> None:
    for key, entry in raw("hi.json").items():
        for text in entry.values():
            assert not re.search(r"[\u0966-\u096F]", text), key


def test_lexicon_covers_fr_012() -> None:
    assert {"caused", "forced", "because", "because of", "deliberately", "so that", "made him"} <= set(
        CAUSAL_LEXICON
    )
    assert {"के कारण", "की वजह से", "मजबूर", "जानबूझकर", "इरादा"} <= set(CAUSAL_LEXICON)


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("Blue 9 forced the defender out.", ["forced"]),
        ("Because of the run, space opened.", ["because of"]),
        ("BECAUSE it widened", ["because"]),
        ("becausewise and forcedly", []),
        ("Space opened, so that the pass was on.", ["so that"]),
        ("ब्लू 9 की दौड़ के कारण जगह बनी।", ["के कारण"]),
        ("उसने जानबूझकर पास दिया", ["जानबूझकर"]),
        ("इरादतन", ["इरादतन"]),
        ("Blue 9's run helped create room for the pass.", []),
    ],
)
def test_find_causal_terms(text: str, found: list[str]) -> None:
    assert find_causal_terms(text) == found


def test_text_for_titles_ignores_mode(catalog: Catalog) -> None:
    assert catalog.text("title.shot", "fan", "en") == catalog.text("title.shot", "analyst", "en") == "Shot"


def test_unknown_key_raises(catalog: Catalog) -> None:
    with pytest.raises(TemplateError, match=r"interp\.run_forced_defender"):
        catalog.spec("interp.run_forced_defender")
    with pytest.raises(TemplateError, match=r"interp\.run_forced_defender"):
        catalog.text("interp.run_forced_defender", "fan", "en")
