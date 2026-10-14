import hashlib
import json
import os
from pathlib import Path

import pytest

from tactistream.simulator.config import SimulationConfig
from tactistream.simulator.engine import simulate
from tactistream.simulator.io import feed_bytes, to_envelopes

GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "simulator_hashes.json"
SOURCE = {"kind": "synthetic", "generator_version": "0.1.0", "seed": 42}


def _sha(cfg: SimulationConfig) -> str:
    return hashlib.sha256(feed_bytes(to_envelopes(simulate(cfg)))).hexdigest()


def test_simulate_twice_is_byte_identical() -> None:
    cfg = SimulationConfig(42, "space_creation")
    a, b = simulate(cfg), simulate(cfg)
    assert feed_bytes(to_envelopes(a)) == feed_bytes(to_envelopes(b))
    assert a.manifest.to_canonical_json() == b.manifest.to_canonical_json()
    assert a.manifest.feed_sha256 == hashlib.sha256(feed_bytes(to_envelopes(a))).hexdigest()


def test_hero_hash_matches_golden() -> None:
    digest = _sha(SimulationConfig(42, "space_creation"))
    if os.environ.get("TACTISTREAM_UPDATE_GOLDEN") == "1":
        hashes = json.loads(GOLDEN.read_text(encoding="utf-8"))
        hashes["space_creation/42/A"] = digest
        GOLDEN.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        pytest.skip("golden hash written")
    assert digest == json.loads(GOLDEN.read_text(encoding="utf-8"))["space_creation/42/A"]


def test_other_seed_differs() -> None:
    assert _sha(SimulationConfig(43, "space_creation")) != _sha(SimulationConfig(42, "space_creation"))


def test_source_on_every_record() -> None:
    out = simulate(SimulationConfig(42, "space_creation"))
    assert out.metadata.source.model_dump(mode="json") == SOURCE
    assert all(e.source.model_dump(mode="json") == SOURCE for e in out.events)
    assert all(f.source.model_dump(mode="json") == SOURCE for f in out.frames)
