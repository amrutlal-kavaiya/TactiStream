from pathlib import Path

import pytest
from pydantic import ValidationError

from tactistream.settings import Settings

ENV_EXAMPLE = Path(__file__).parents[3] / ".env.example"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            monkeypatch.delenv(line.split("=", 1)[0], raising=False)


def test_agent_defaults_match_env_example() -> None:
    s = Settings(_env_file=None)
    assert s.narrative_deadline_ms == 8000
    assert s.demo_fixtures is False
    assert s.trace_dir is None
    assert s.agent_scripts == ENV_EXAMPLE.parent / "data/fixtures/agent_scripts/demo-blue-amber-001.json"
    assert s.analyst_timeout_ms == 3500
    assert s.verifier_timeout_ms == 2500
    assert s.producer_timeout_ms == 1500
    assert s.release_reserve_ms == 400
    assert s.repair_min_remaining_ms == 3000
    assert s.min_tracking_coverage == 0.8
    assert s.narrative_min_rank == 0.4
    assert s.narrative_max_concurrency == 2
    assert s.foundry_model_deployment_fast is None


def test_demo_fixtures_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TACTISTREAM_DEMO_FIXTURES", "true")
    assert Settings(_env_file=None).demo_fixtures is True


def test_relative_paths_resolve_against_the_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TACTISTREAM_TRACE_DIR", "data/traces")
    assert Settings(_env_file=None).trace_dir == ENV_EXAMPLE.parent / "data/traces"


def test_scripted_agents_need_an_existing_scripts_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TACTISTREAM_AGENTS", "scripted")
    monkeypatch.setenv("TACTISTREAM_AGENT_SCRIPTS", str(tmp_path / "missing.json"))
    with pytest.raises(ValidationError, match="TACTISTREAM_AGENT_SCRIPTS"):
        Settings(_env_file=None)
    script = tmp_path / "script.json"
    script.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("TACTISTREAM_AGENT_SCRIPTS", str(script))
    assert Settings(_env_file=None).agent_scripts == script


def test_missing_scripts_file_is_fine_when_agents_are_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TACTISTREAM_AGENT_SCRIPTS", str(tmp_path / "missing.json"))
    assert Settings(_env_file=None).agents == "off"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TACTISTREAM_ANALYST_TIMEOUT_MS", "799"),
        ("TACTISTREAM_VERIFIER_TIMEOUT_MS", "599"),
        ("TACTISTREAM_PRODUCER_TIMEOUT_MS", "599"),
        ("TACTISTREAM_MIN_TRACKING_COVERAGE", "1.5"),
        ("TACTISTREAM_NARRATIVE_MAX_CONCURRENCY", "0"),
    ],
)
def test_out_of_range_agent_settings_rejected(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_agent_budgets_carry_caps_minimums_and_reserve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TACTISTREAM_ANALYST_TIMEOUT_MS", "3000")
    budgets = Settings(_env_file=None).agent_budgets()
    assert budgets.caps_ms == {"analyst": 3000, "verifier": 2500, "producer": 1500, "single_agent": 3000}
    assert budgets.min_ms == {"analyst": 800, "verifier": 600, "producer": 600, "single_agent": 800}
    assert budgets.reserve_ms == 400
    assert budgets.repair_min_remaining_ms == 3000
    assert budgets.token_budget is None
