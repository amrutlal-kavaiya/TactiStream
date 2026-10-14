import json
from pathlib import Path

from typer.testing import CliRunner

from tactistream.simulator.cli import app

GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "simulator_hashes.json"
HERO = ["generate", "--scenario", "space_creation", "--seed", "42", "--variant", "A", "--split", "dev"]
runner = CliRunner()


def test_generate_writes_hero_and_refuses_non_empty_out(tmp_path: Path) -> None:
    out = tmp_path / "hero"
    first = runner.invoke(app, [*HERO, "--out", str(out)])
    assert first.exit_code == 0, first.output
    assert "match_id=demo-blue-amber-001 events=9" in first.output
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["space_creation/42/A"]
    assert f"feed_sha256={golden}" in first.output
    assert (out / "feed.jsonl").is_file()
    assert (out / "manifest.json").is_file()

    again = runner.invoke(app, [*HERO, "--out", str(out)])
    assert again.exit_code == 2
    assert "error:" in again.output

    forced = runner.invoke(app, [*HERO, "--out", str(out), "--force"])
    assert forced.exit_code == 0, forced.output
    for result in (first, again, forced):
        assert "Traceback" not in result.output


def test_unknown_scenario_lists_valid_names(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["generate", "--scenario", "nope", "--seed", "1", "--out", str(tmp_path / "x")]
    )
    assert result.exit_code == 2
    assert "error:" in result.output
    assert "space_creation" in result.output and "demo_match" in result.output
    assert "Traceback" not in result.output
    assert not (tmp_path / "x").exists()


def test_list_prints_eight_scenarios() -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines[0].startswith("scenario")
    assert len(lines[1:]) == 8
    assert lines[-1].split()[0] == "demo_match"
    assert "Traceback" not in result.output
