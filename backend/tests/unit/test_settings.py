from pathlib import Path

import pytest
from pydantic import ValidationError

from tactistream.settings import Settings

ENV_EXAMPLE = Path(__file__).parents[3] / ".env.example"


def example_names() -> list[str]:
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    return [line.split("=", 1)[0] for line in lines if line and not line.startswith("#")]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in example_names():
        monkeypatch.delenv(name, raising=False)


def test_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.bus == "memory"
    assert s.agents == "off"
    assert s.eventhubs_fully_qualified_namespace is None
    assert s.eventhubs_name == "tactistream-feed"
    assert s.eventhubs_consumer_group == "live-state"
    assert s.foundry_project_endpoint is None
    assert s.foundry_model_deployment is None
    assert s.applicationinsights_connection_string is None
    assert s.azure_storage_account_url is None
    assert s.fabric_kusto_query_uri is None
    assert s.fabric_kusto_database is None
    assert s.azure_location is None
    assert s.narrative_deadline_ms == 8000
    assert s.max_sessions == 8


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TACTISTREAM_BUS", "eventhubs")
    monkeypatch.setenv("TACTISTREAM_AGENTS", "scripted")
    monkeypatch.setenv("EVENTHUBS_FULLY_QUALIFIED_NAMESPACE", "ns.servicebus.windows.net")
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.services.ai.azure.com/api/projects/p")
    monkeypatch.setenv("TACTISTREAM_NARRATIVE_DEADLINE_MS", "5000")
    s = Settings(_env_file=None)
    assert s.bus == "eventhubs"
    assert s.agents == "scripted"
    assert s.eventhubs_fully_qualified_namespace == "ns.servicebus.windows.net"
    assert s.foundry_project_endpoint == "https://example.services.ai.azure.com/api/projects/p"
    assert s.narrative_deadline_ms == 5000


def test_every_env_example_name_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "TACTISTREAM_BUS": "eventhubs",
        "TACTISTREAM_AGENTS": "foundry",
        "TACTISTREAM_NARRATIVE_DEADLINE_MS": "1",
        "TACTISTREAM_ARTIFACT_STORE": "blob",
        "TACTISTREAM_ANALYTICS_PUBLISH": "True",
        "TACTISTREAM_HISTORY": "eventhouse",
        "TACTISTREAM_HISTORY_TIMEOUT_MS": "1234",
        "TACTISTREAM_MAX_SESSIONS": "3",
    }
    for name in example_names():
        monkeypatch.setenv(name, values.get(name, f"v-{name.lower()}"))
    dumped = {str(v) for v in Settings(_env_file=None).model_dump().values()}
    for name in example_names():
        assert values.get(name, f"v-{name.lower()}") in dumped, name


def test_empty_values_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENTHUBS_FULLY_QUALIFIED_NAMESPACE", "")
    monkeypatch.setenv("EVENTHUBS_NAME", "")
    s = Settings(_env_file=None)
    assert s.eventhubs_fully_qualified_namespace is None
    assert s.eventhubs_name == "tactistream-feed"


@pytest.mark.parametrize(("name", "value"), [("TACTISTREAM_BUS", "kafka"), ("TACTISTREAM_AGENTS", "gpt")])
def test_invalid_selection_rejected(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_reads_dotenv_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TACTISTREAM_BUS=eventhubs\nEVENTHUBS_NAME=other-hub\n", encoding="utf-8")
    s = Settings(_env_file=env_file)
    assert s.bus == "eventhubs"
    assert s.eventhubs_name == "other-hub"


def test_static_dir_defaults_to_frontend_dist_and_is_overridable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert Settings(_env_file=None).static_dir == ENV_EXAMPLE.parent / "frontend" / "dist"
    monkeypatch.setenv("TACTISTREAM_STATIC_DIR", str(tmp_path))
    assert Settings(_env_file=None).static_dir == tmp_path


def test_data_dir_defaults_to_repo_data_and_is_overridable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert Settings(_env_file=None).data_dir == ENV_EXAMPLE.parent / "data"
    monkeypatch.setenv("TACTISTREAM_DATA_DIR", str(tmp_path))
    assert Settings(_env_file=None).data_dir == tmp_path
