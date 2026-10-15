from pathlib import Path

import pytest
from simulator.intent import LIBRARY

from tactistream.simulator.config import SimulationConfig
from tactistream.simulator.engine import simulate
from tactistream.simulator.io import to_envelopes, write_output
from tactistream.simulator.validate import validate_envelopes
from tactistream.transport.fixtures import load_fixture


@pytest.mark.parametrize(("scenario", "seed"), [("space_creation", 42), *((name, 1) for name in LIBRARY)])
def test_written_feed_loads_with_full_schema_validation(tmp_path: Path, scenario: str, seed: int) -> None:
    output = simulate(SimulationConfig(seed, scenario))  # type: ignore[arg-type]
    written = write_output(output, tmp_path / "out")
    envelopes = load_fixture(written.feed_path)
    assert envelopes == to_envelopes(output)
    assert envelopes[0].kind == "metadata"
    report = validate_envelopes(envelopes)
    assert report.ok, [i.line() for i in report.issues[:5]]
