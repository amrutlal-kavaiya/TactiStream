from typing import Any

import pytest
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from tactistream import __version__
from tactistream.settings import Settings
from tactistream.telemetry import otel


@pytest.fixture(autouse=True)
def reset(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(otel, "configure_azure_monitor", lambda **kw: calls.append(kw))
    monkeypatch.setattr(otel, "_configured", False)
    monkeypatch.setattr(otel, "_sdk_installed", False)
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    return calls


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    installed: dict[str, Any] = {}
    monkeypatch.setattr(otel.trace, "set_tracer_provider", lambda p: installed.__setitem__("trace", p))
    monkeypatch.setattr(otel.metrics, "set_meter_provider", lambda p: installed.__setitem__("metrics", p))
    monkeypatch.setattr(otel._logs, "set_logger_provider", lambda p: installed.__setitem__("logs", p))
    return installed


def test_no_connection_string_does_not_export(reset: list[dict[str, Any]], installed: dict[str, Any]) -> None:
    assert otel.setup_telemetry(Settings(_env_file=None)) is False
    assert reset == []


def test_sdk_providers_are_always_installed_once_with_resource(installed: dict[str, Any]) -> None:
    otel.setup_telemetry(Settings(_env_file=None, environment="test"))
    assert isinstance(installed["trace"], TracerProvider)
    assert isinstance(installed["metrics"], MeterProvider)
    assert isinstance(installed["logs"], LoggerProvider)
    attributes = dict(installed["trace"].resource.attributes)
    assert attributes["service.name"] == "tactistream-api"
    assert attributes["service.version"] == __version__
    assert attributes["deployment.environment"] == "test"
    first = installed["trace"]
    otel.setup_telemetry(Settings(_env_file=None))
    assert installed["trace"] is first


def test_connection_string_configures_azure_monitor_once(
    reset: list[dict[str, Any]], installed: dict[str, Any]
) -> None:
    settings = Settings(
        _env_file=None,
        applicationinsights_connection_string="InstrumentationKey=abc",
        environment="production",
    )
    assert otel.setup_telemetry(settings) is True
    assert otel.setup_telemetry(settings) is True
    assert len(reset) == 1
    assert reset[0]["connection_string"] == "InstrumentationKey=abc"
    resource = reset[0]["resource"]
    assert isinstance(resource, Resource)
    assert resource.attributes["deployment.environment"] == "production"
    assert installed == {}
