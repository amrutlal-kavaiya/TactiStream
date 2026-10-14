from pathlib import Path
from typing import Any

import pytest
from azure.eventhub.exceptions import AuthenticationError
from typer.testing import CliRunner

from tactistream.settings import Settings
from tactistream.smoke import cli
from tactistream.smoke.eventhubs import EventHubsSmokeResult
from tactistream.smoke.foundry import FoundrySmokeResult, SmokeError

AZURE_NAMES = (
    "FOUNDRY_PROJECT_ENDPOINT",
    "FOUNDRY_MODEL_DEPLOYMENT",
    "EVENTHUBS_FULLY_QUALIFIED_NAMESPACE",
    "EVENTHUBS_NAME",
    "EVENTHUBS_CONSUMER_GROUP",
    "AZURE_LOCATION",
)


@pytest.fixture(autouse=True)
def no_azure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in AZURE_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(cli, "load_settings", lambda: Settings(_env_file=None))


def invoke(*args: str) -> Any:
    return CliRunner().invoke(cli.app, list(args))


@pytest.mark.parametrize(
    ("command", "missing"),
    [("foundry", "FOUNDRY_PROJECT_ENDPOINT"), ("eventhubs", "EVENTHUBS_FULLY_QUALIFIED_NAMESPACE")],
)
def test_missing_env_exits_2_naming_the_variable_without_traceback(command: str, missing: str) -> None:
    result = invoke(command)
    assert result.exit_code == 2
    assert f"Missing {missing}" in result.output
    assert "Traceback" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_foundry_names_every_missing_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://x.services.ai.azure.com/api/projects/p")
    result = invoke("foundry")
    assert result.exit_code == 2
    assert "Missing FOUNDRY_MODEL_DEPLOYMENT" in result.output
    assert "FOUNDRY_PROJECT_ENDPOINT" not in result.output


def foundry_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://x.services.ai.azure.com/api/projects/p")
    monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT", "gpt-4o-mini")


def test_foundry_success_prints_measurements(monkeypatch: pytest.MonkeyPatch) -> None:
    foundry_env(monkeypatch)
    monkeypatch.setenv("AZURE_LOCATION", "swedencentral")
    seen: dict[str, Any] = {}

    async def fake_run(endpoint: str, deployment: str, *, region: str | None) -> FoundrySmokeResult:
        seen.update(endpoint=endpoint, deployment=deployment, region=region)
        return FoundrySmokeResult(
            deployment=deployment,
            model="gpt-4o-mini-2024-07-18",
            region=region or "unknown",
            latency_ms=412,
            input_tokens=31,
            output_tokens=12,
            reply={"ok": True, "echo": "abc123"},
        )

    monkeypatch.setattr(cli, "run_foundry_smoke", fake_run)
    result = invoke("foundry")
    assert result.exit_code == 0, result.output
    assert seen == {
        "endpoint": "https://x.services.ai.azure.com/api/projects/p",
        "deployment": "gpt-4o-mini",
        "region": "swedencentral",
    }
    for text in (
        "deployment: gpt-4o-mini",
        "model: gpt-4o-mini-2024-07-18",
        "region: swedencentral",
        "latency_ms: 412",
        "tokens_in: 31",
        "tokens_out: 12",
        '{"ok": true, "echo": "abc123"}',
    ):
        assert text in result.output


@pytest.mark.parametrize(
    "error", [SmokeError("echo mismatch"), RuntimeError("DefaultAzureCredential failed")]
)
def test_foundry_failure_exits_1_without_traceback(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    foundry_env(monkeypatch)

    async def fake_run(endpoint: str, deployment: str, *, region: str | None) -> FoundrySmokeResult:
        raise error

    monkeypatch.setattr(cli, "run_foundry_smoke", fake_run)
    result = invoke("foundry")
    assert result.exit_code == 1
    assert f"foundry smoke failed: {type(error).__name__}: {error}" in result.output
    assert "Traceback" not in result.output
    assert isinstance(result.exception, SystemExit)


def test_eventhubs_success_prints_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENTHUBS_FULLY_QUALIFIED_NAMESPACE", "tactistream.servicebus.windows.net")
    seen: dict[str, Any] = {}

    async def fake_run(namespace: str, hub: str, *, consumer_group: str) -> EventHubsSmokeResult:
        seen.update(namespace=namespace, hub=hub, consumer_group=consumer_group)
        return EventHubsSmokeResult(
            namespace=namespace, hub=hub, consumer_group=consumer_group, record_id="evt-123", round_trip_ms=87
        )

    monkeypatch.setattr(cli, "run_eventhubs_smoke", fake_run)
    result = invoke("eventhubs")
    assert result.exit_code == 0, result.output
    assert seen == {
        "namespace": "tactistream.servicebus.windows.net",
        "hub": "tactistream-feed",
        "consumer_group": "live-state",
    }
    for text in (
        "namespace: tactistream.servicebus.windows.net",
        "hub: tactistream-feed",
        "consumer_group: live-state",
        "record_id: evt-123 (matched)",
        "round_trip_ms: 87",
    ):
        assert text in result.output


def test_eventhubs_failure_exits_1_without_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENTHUBS_FULLY_QUALIFIED_NAMESPACE", "tactistream.servicebus.windows.net")

    async def fake_run(namespace: str, hub: str, *, consumer_group: str) -> EventHubsSmokeResult:
        raise AuthenticationError("unauthorized: no Data Receiver role")

    monkeypatch.setattr(cli, "run_eventhubs_smoke", fake_run)
    result = invoke("eventhubs")
    assert result.exit_code == 1
    assert "eventhubs smoke failed: AuthenticationError: unauthorized: no Data Receiver role" in result.output
    assert "Traceback" not in result.output


def test_eventhubs_consumer_group_comes_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENTHUBS_FULLY_QUALIFIED_NAMESPACE", "tactistream.servicebus.windows.net")
    monkeypatch.setenv("EVENTHUBS_CONSUMER_GROUP", "live-state-b")
    groups: list[str] = []

    async def fake_run(namespace: str, hub: str, *, consumer_group: str) -> EventHubsSmokeResult:
        groups.append(consumer_group)
        return EventHubsSmokeResult(namespace, hub, consumer_group, "evt-1", 1)

    monkeypatch.setattr(cli, "run_eventhubs_smoke", fake_run)
    result = invoke("eventhubs")
    assert result.exit_code == 0, result.output
    assert groups == ["live-state-b"]
    assert "consumer_group: live-state-b" in result.output


def capture_region(monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
    regions: list[str | None] = []

    async def fake_run(endpoint: str, deployment: str, *, region: str | None) -> FoundrySmokeResult:
        regions.append(region)
        return FoundrySmokeResult(deployment, None, region or "unknown", 1, None, None, {"ok": True})

    monkeypatch.setattr(cli, "run_foundry_smoke", fake_run)
    return regions


def test_region_is_read_from_a_dotenv_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FOUNDRY_PROJECT_ENDPOINT=https://x.services.ai.azure.com/api/projects/p\n"
        "FOUNDRY_MODEL_DEPLOYMENT=gpt-4o-mini\n"
        "AZURE_LOCATION=swedencentral\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "load_settings", lambda: Settings(_env_file=env_file))
    regions = capture_region(monkeypatch)
    assert invoke("foundry").exit_code == 0
    assert regions == ["swedencentral"]


def test_region_option_overrides_azure_location(monkeypatch: pytest.MonkeyPatch) -> None:
    foundry_env(monkeypatch)
    monkeypatch.setenv("AZURE_LOCATION", "swedencentral")
    regions = capture_region(monkeypatch)
    assert invoke("foundry", "--region", "westeurope").exit_code == 0
    assert regions == ["westeurope"]
