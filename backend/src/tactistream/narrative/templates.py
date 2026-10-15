"""Narrative catalog: language-independent template specs (`spec.json`) plus reviewed en/hi text."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal, cast, get_args

from tactistream.contracts import Language, MetricKind, MomentPattern, ViewerMode
from tactistream.contracts.metric import MetricUnit

CATALOG_DIR = Path(__file__).parent / "catalog"
LANGUAGES: tuple[Language, ...] = ("en", "hi")
DERIVED_SLOTS = frozenset({"outcome"})
PLACEHOLDER = re.compile(r"\{([a-z_]+)(?:\.([a-z_]+))?\}")

SlotType = Literal["player", "team", "metric", "event_time"]
TemplateKind = Literal["fact", "interpretation", "status", "title", "phrase", "label"]
CLAIM_KINDS: frozenset[TemplateKind] = frozenset({"fact", "interpretation"})
_MODE_TEXT_KINDS: frozenset[TemplateKind] = frozenset({"fact", "interpretation", "status"})


class TemplateError(ValueError):
    """A template is unknown, a slot is missing or unresolvable, or the catalog is inconsistent."""


@dataclass(frozen=True)
class SlotSpec:
    type: SlotType
    metric_kinds: tuple[MetricKind, ...] = ()
    unit: MetricUnit | None = None
    precision: int = 1


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    kind: TemplateKind
    slots: Mapping[str, SlotSpec]
    required_evidence_kinds: tuple[MetricKind, ...] = ()
    requires_tracking: bool = False
    title_keys: tuple[str, ...] = ()
    patterns: tuple[MomentPattern, ...] = ()

    def event_slot(self) -> str | None:
        """The slot a derived `{outcome}` is read from (the single `event_time` slot), if any."""
        names = [name for name, slot in self.slots.items() if slot.type == "event_time"]
        return names[0] if len(names) == 1 else None


class Catalog:
    def __init__(
        self, version: str, specs: Mapping[str, TemplateSpec], texts: Mapping[Language, Mapping[str, Any]]
    ) -> None:
        self.version = version
        self._specs = dict(specs)
        self._texts = texts

    def has(self, key: str) -> bool:
        return key in self._specs

    def spec(self, key: str) -> TemplateSpec:
        spec = self._specs.get(key)
        if spec is None:
            raise TemplateError(f"unknown template {key}")
        return spec

    def keys(self, prefix: str = "") -> list[str]:
        return [key for key in self._specs if key.startswith(prefix)]

    def text(self, key: str, mode: ViewerMode, language: Language) -> str:
        spec = self.spec(key)
        entry = self._texts[language][key]
        text = entry[mode] if spec.kind in _MODE_TEXT_KINDS else entry["text"]
        return cast(str, text)

    def claim_templates(self, pattern: MomentPattern) -> list[TemplateSpec]:
        """Fact and interpretation templates an agent may use for a moment of `pattern`."""
        return [s for s in self._specs.values() if s.kind in CLAIM_KINDS and pattern in s.patterns]


@cache
def load_catalog() -> Catalog:
    """Load and cross-validate `spec.json`, `en.json` and `hi.json`; raises `TemplateError` on drift."""
    raw_spec = _read("spec.json")
    specs = {key: _template_spec(key, body) for key, body in raw_spec["templates"].items()}
    texts: dict[Language, dict[str, Any]] = {}
    for language in LANGUAGES:
        entries = {k: v for k, v in _read(f"{language}.json").items() if k != "_meta"}
        if entries.keys() != specs.keys():
            drift = sorted(entries.keys() ^ specs.keys())
            raise TemplateError(f"{language}.json keys differ from spec.json: {drift}")
        texts[language] = entries
    catalog = Catalog(str(raw_spec["catalog_version"]), specs, texts)
    for spec in specs.values():
        _validate(catalog, spec)
    return catalog


def _read(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((CATALOG_DIR / name).read_text(encoding="utf-8"))
    return data


def _template_spec(key: str, body: Mapping[str, Any]) -> TemplateSpec:
    kind = body["kind"]
    if kind not in get_args(TemplateKind):
        raise TemplateError(f"{key}: unknown kind {kind}")
    slots = {
        name: SlotSpec(
            type=slot["type"],
            metric_kinds=tuple(slot.get("metric_kinds", ())),
            unit=slot.get("unit"),
            precision=int(slot.get("precision", 1)),
        )
        for name, slot in body.get("slots", {}).items()
    }
    return TemplateSpec(
        key=key,
        kind=kind,
        slots=slots,
        required_evidence_kinds=tuple(body.get("required_evidence_kinds", ())),
        requires_tracking=bool(body.get("requires_tracking", False)),
        title_keys=tuple(body.get("title_keys", ())),
        patterns=tuple(body.get("patterns", ())),
    )


def _validate(catalog: Catalog, spec: TemplateSpec) -> None:
    for title in spec.title_keys:
        if not catalog.has(title) or catalog.spec(title).kind != "title":
            raise TemplateError(f"{spec.key}: title key {title} is not a title template")
    for name, slot in spec.slots.items():
        if slot.type == "metric" and (not slot.metric_kinds or slot.unit is None):
            raise TemplateError(f"{spec.key}: metric slot {name} needs metric_kinds and unit")
    modes: tuple[ViewerMode, ...] = ("fan", "analyst")
    for language in LANGUAGES:
        for mode in modes:
            for name, _ in PLACEHOLDER.findall(catalog.text(spec.key, mode, language)):
                if name in DERIVED_SLOTS and spec.event_slot() is not None:
                    continue
                if name not in spec.slots:
                    raise TemplateError(f"{spec.key} ({language}/{mode}) uses undeclared slot {name}")
