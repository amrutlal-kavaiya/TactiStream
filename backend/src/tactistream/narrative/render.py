"""Deterministic rendering of catalog templates; every number and name comes from metadata or metrics."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from tactistream.contracts import (
    Language,
    LocalizedName,
    MatchEvent,
    MatchMetadata,
    MetricResult,
    SlotValue,
    ViewerMode,
)
from tactistream.narrative.templates import (
    CATALOG_DIR,
    DERIVED_SLOTS,
    PLACEHOLDER,
    SlotSpec,
    TemplateError,
    TemplateSpec,
)
from tactistream.narrative.templates import load_catalog as load_template_catalog

__all__ = [
    "MetricLookup",
    "RenderContext",
    "RenderedText",
    "TemplateError",
    "load_catalog",
    "render_claim",
    "render_title",
]

CatalogEntry = str | dict[str, str]
MetricLookup = Callable[[str], MetricResult]


@dataclass(frozen=True)
class RenderedText:
    """`numbers` lists every metric slot value of the template (slot order, catalog precision), whether or not
    this variant's text shows it, so all four variants of one claim carry the same numbers."""

    text: str
    numbers: list[str] = field(default_factory=list)
    player_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RenderContext:
    """What slots resolve against: names from metadata, values from metrics, outcomes from events."""

    metadata: MatchMetadata
    metrics: Mapping[str, MetricResult] = field(default_factory=dict)
    events: Mapping[str, MatchEvent] = field(default_factory=dict)


@cache
def load_catalog(language: Language) -> dict[str, CatalogEntry]:
    raw: dict[str, Any] = json.loads((CATALOG_DIR / f"{language}.json").read_text(encoding="utf-8"))
    return {key: value for key, value in raw.items() if key != "_meta"}


def render_title(template_id: str, mode: ViewerMode, language: Language) -> RenderedText:
    if load_template_catalog().spec(template_id).kind != "title":
        raise TemplateError(f"{template_id} is not a title template")
    return render_claim(template_id, {}, mode, language, context=None)


def render_claim(
    template_id: str,
    slots: Mapping[str, SlotValue],
    mode: ViewerMode,
    language: Language,
    *,
    context: RenderContext | None,
    metric_lookup: MetricLookup | None = None,
) -> RenderedText:
    """Render one variant. Metric values come from `metric_lookup` (else `context.metrics`); an agent's
    `SlotValue.value` is never rendered."""
    catalog = load_template_catalog()
    spec = catalog.spec(template_id)
    template = catalog.text(template_id, mode, language)
    for name, slot_spec in spec.slots.items():
        slot = slots.get(name)
        if slot is None:
            raise TemplateError(f"template {template_id} is missing slot {name}")
        if slot.kind != slot_spec.type:
            raise TemplateError(f"slot {name} must be a {slot_spec.type}, got {slot.kind}")
    if spec.slots and context is None:
        raise TemplateError(f"template {template_id} needs a render context")

    values: dict[str, tuple[MetricResult, str]] = {}
    for name, slot_spec in spec.slots.items():
        if slot_spec.type == "metric":
            assert context is not None
            values[name] = _metric_value(context, metric_lookup, name, slots[name], slot_spec)
    player_ids: list[str] = []

    def substitute(match: re.Match[str]) -> str:
        name, attribute = match.group(1), match.group(2)
        assert context is not None
        if name in DERIVED_SLOTS and name not in spec.slots:
            return _derived(spec, name, slots, context, mode, language)
        slot = slots[name]
        if slot.kind == "player":
            player_id = slot.player_id or ""
            _append_once(player_ids, player_id)
            return _player_name(context.metadata, player_id, language)
        if slot.kind == "team":
            return _team_name(context.metadata, slot.team_id or "", language)
        if slot.kind == "event_time":
            return _event(context, slot.event_id or "").event_id
        metric, number = values[name]
        if attribute == "event_ids":
            return ", ".join(metric.inputs.event_ids)
        if attribute is not None:
            raise TemplateError(f"unknown metric attribute {name}.{attribute}")
        return number

    text = PLACEHOLDER.sub(substitute, template)
    numbers: list[str] = []
    for _, number in values.values():
        _append_once(numbers, number)
    return RenderedText(text=text, numbers=numbers, player_ids=player_ids)


def _metric_value(
    context: RenderContext,
    lookup: MetricLookup | None,
    name: str,
    slot: SlotValue,
    slot_spec: SlotSpec,
) -> tuple[MetricResult, str]:
    metric_id = slot.metric_id or ""
    try:
        metric = lookup(metric_id) if lookup is not None else context.metrics[metric_id]
    except KeyError as exc:
        raise TemplateError(f"unknown metric {metric_id}") from exc
    if metric.kind not in slot_spec.metric_kinds:
        raise TemplateError(f"slot {name} does not accept {metric.kind} metric {metric_id}")
    if metric.status != "ok" or metric.value is None:
        raise TemplateError(f"metric {metric_id} is unavailable")
    return metric, f"{metric.value:.{slot_spec.precision}f}"


def _derived(
    spec: TemplateSpec,
    name: str,
    slots: Mapping[str, SlotValue],
    context: RenderContext,
    mode: ViewerMode,
    language: Language,
) -> str:
    event_slot = spec.event_slot()
    if event_slot is None:
        raise TemplateError(f"template {spec.key} derives {name} without an event_time slot")
    event = _event(context, slots[event_slot].event_id or "")
    phrase = f"{name}.{event.outcome}"
    catalog = load_template_catalog()
    if event.outcome is None or not catalog.has(phrase):
        raise TemplateError(f"no {name} phrase for {event.event_id} outcome {event.outcome}")
    return catalog.text(phrase, mode, language)


def _event(context: RenderContext, event_id: str) -> MatchEvent:
    event = context.events.get(event_id)
    if event is None:
        raise TemplateError(f"unknown event {event_id}")
    return event


def _append_once(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def _player_name(metadata: MatchMetadata, player_id: str, language: Language) -> str:
    for team in metadata.teams:
        for player in team.players:
            if player.player_id == player_id:
                return _localized(player.display_name, language)
    raise TemplateError(f"unknown player {player_id}")


def _team_name(metadata: MatchMetadata, team_id: str, language: Language) -> str:
    for team in metadata.teams:
        if team.team_id == team_id:
            return _localized(team.display_name, language)
    raise TemplateError(f"unknown team {team_id}")


def _localized(name: LocalizedName, language: Language) -> str:
    return name.en if language == "en" else name.hi
