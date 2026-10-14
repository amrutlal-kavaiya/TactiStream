"""OpenTelemetry wiring: Azure Monitor when a connection string is configured, otherwise nothing."""

from __future__ import annotations

from azure.monitor.opentelemetry import configure_azure_monitor

from tactistream.settings import Settings

_configured = False


def setup_telemetry(settings: Settings) -> bool:
    """Configure Azure Monitor export once per process; returns whether export is enabled."""
    global _configured
    connection_string = settings.applicationinsights_connection_string
    if not connection_string:
        return False
    if not _configured:
        configure_azure_monitor(connection_string=connection_string)
        _configured = True
    return True
