import ast
import json
from pathlib import Path

from tactistream.simulator.config import SimulationConfig
from tactistream.simulator.engine import simulate
from tactistream.simulator.io import feed_bytes, to_envelopes

SRC = Path(__file__).resolve().parents[3] / "src" / "tactistream"
LIVE_PACKAGES = (
    "state",
    "metrics",
    "moments",
    "agents",
    "narrative",
    "api",
    "transport",
    "recap",
    "history",
    "storage",
    "telemetry",
)
FORBIDDEN_KEYS = {
    "scenario",
    "variant",
    "segments",
    "expected_pattern",
    "intended_explanation",
    "negative_of",
}


def _violations(path: Path) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("tactistream.simulator.manifest"):
                found.append(f"{path}: from {node.module}")
            if any(alias.name == "GenerationManifest" for alias in node.names):
                found.append(f"{path}: imports GenerationManifest")
        elif isinstance(node, ast.Import):
            found += [
                f"{path}: import {a.name}"
                for a in node.names
                if a.name.startswith("tactistream.simulator.manifest")
            ]
        elif isinstance(node, ast.Name | ast.Attribute):
            name = node.id if isinstance(node, ast.Name) else node.attr
            if name == "GenerationManifest":
                found.append(f"{path}: uses GenerationManifest")
    return found


def test_live_code_never_touches_the_manifest() -> None:
    files = [f for pkg in LIVE_PACKAGES if (SRC / pkg).is_dir() for f in sorted((SRC / pkg).rglob("*.py"))]
    assert files
    assert [v for f in files for v in _violations(f)] == []


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def test_feed_carries_no_ground_truth() -> None:
    hero = simulate(SimulationConfig(42, "space_creation"))
    keys = {k for line in feed_bytes(to_envelopes(hero)).splitlines() for k in _keys(json.loads(line))}
    assert keys & FORBIDDEN_KEYS == set()


def test_hero_label() -> None:
    (label,) = simulate(SimulationConfig(42, "space_creation")).manifest.segments
    assert label.expected_pattern == "space_creation"
    assert label.positive and label.negative_of is None
    assert label.key_players["runner"] == "blue-09"
    assert label.key_players["follower"] == "amber-04"
    assert dict(label.key_event_ids) == {"forward_pass": "evt-0005", "shot": "evt-0007"}
    assert label.intended_explanation == (
        "Blue 9's diagonal run draws Amber 4; the Blue 8 → Blue 11 lane widens; forward pass, then shot."
    )
