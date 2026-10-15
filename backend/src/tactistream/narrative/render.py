"""Deterministic rendering of catalog templates; every number and name comes from metadata or metrics."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from tactistream.contracts import (
    Language,
    LocalizedName,
    MatchMetadata,
    MetricResult,
    SlotValue,
    ViewerMode,
)
from tactistream.narrative.templates import CATALOG_DIR, PLACEHOLDER, TemplateError
from tactistream.narrative.templates import load_catalog as load_template_catalog

__all__ = ["RenderContext", "RenderedText", "TemplateError", "load_catalog", "render_claim", "render_title"]

CatalogEntry = str | dict[str, str]


@dataclass(frozen=True)
class RenderedText:
    text: str
    numbers: list[str] = field(default_factory=list)
    player_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RenderContext:
    """What slot references resolve against: display names from metadata, values from metrics."""

    metadata: MatchMetadata
    metrics: Mapping[str, MetricResult] = field(default_factory=dict)


@cache
def load_catalog(language: Language) -> dict[str, CatalogEntry]:
    raw: dict[str, Any] = json.loads((CATALOG_DIR / f"{language}.json").read_text(encoding="utf-8"))
    return {key: value for key, value in raw.items() if key != "_meta"}


def render_title(template_id: str, mode: ViewerMode, language: Language) -> RenderedText:
    if not template_id.startswith("title."):
        raise TemplateError(f"{template_id} is not a title template")
    return render_claim(template_id, {}, mode, language, context=None)


def render_claim(
    template_id: str,
    slots: Mapping[str, SlotValue],
    mode: ViewerMode,
    language: Language,
    *,
    context: RenderContext | None,
) -> RenderedText:
    catalog = load_template_catalog()
    spec = catalog.spec(template_id)
    template = catalog.text(template_id, mode, language)

    slot_kinds = {name: slot.type for name, slot in spec.slots.items()}
    precision = {name: slot.precision for name, slot in spec.slots.items()}
    for name, kind in slot_kinds.items():
        slot = slots.get(name)
        if slot is None:
            raise TemplateError(f"template {template_id} is missing slot {name}")
        if slot.kind != kind:
            raise TemplateError(f"slot {name} must be a {kind}, got {slot.kind}")
    numbers: list[str] = []
    player_ids: list[str] = []

    def substitute(match: re.Match[str]) -> str:
        name, attribute = match.group(1), match.group(2)
        if name not in slot_kinds:
            raise TemplateError(f"template {template_id} references undeclared slot {name}")
        if context is None:
            raise TemplateError(f"template {template_id} needs a render context")
        slot = slots[name]
        if slot.kind == "player":
            player_id = slot.player_id or ""
            _append_once(player_ids, player_id)
            return _player_name(context.metadata, player_id, language)
        if slot.kind == "team":
            return _team_name(context.metadata, slot.team_id or "", language)
        if slot.kind == "metric":
            metric, value = _metric(context, slot.metric_id or "")
            if attribute == "event_ids":
                return ", ".join(metric.inputs.event_ids)
            if attribute is not None:
                raise TemplateError(f"unknown metric attribute {name}.{attribute}")
            number = f"{value:.{precision.get(name, 1)}f}"
            _append_once(numbers, number)
            return number
        raise TemplateError(f"slot kind {slot.kind} is not supported yet")

    return RenderedText(text=PLACEHOLDER.sub(substitute, template), numbers=numbers, player_ids=player_ids)


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


def _metric(context: RenderContext, metric_id: str) -> tuple[MetricResult, float]:
    metric = context.metrics.get(metric_id)
    if metric is None:
        raise TemplateError(f"unknown metric {metric_id}")
    if metric.status != "ok" or metric.value is None:
        raise TemplateError(f"metric {metric_id} is unavailable")
    return metric, metric.value
