from typing import Any

import pytest

from tactistream.settings import Settings
from tactistream.telemetry import otel


@pytest.fixture(autouse=True)
def reset(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(otel, "configure_azure_monitor", lambda **kw: calls.append(kw))
    monkeypatch.setattr(otel, "_configured", False)
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    return calls


def test_no_connection_string_is_a_no_op(reset: list[dict[str, Any]]) -> None:
    assert otel.setup_telemetry(Settings(_env_file=None)) is False
    assert reset == []


def test_connection_string_configures_azure_monitor_once(reset: list[dict[str, Any]]) -> None:
    settings = Settings(_env_file=None, applicationinsights_connection_string="InstrumentationKey=abc")
    assert otel.setup_telemetry(settings) is True
    assert otel.setup_telemetry(settings) is True
    assert reset == [{"connection_string": "InstrumentationKey=abc"}]
