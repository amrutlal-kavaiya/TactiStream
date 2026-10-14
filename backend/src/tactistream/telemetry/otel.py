"""OpenTelemetry: SDK providers always (valid trace ids); Azure Monitor export with a connection string."""

from __future__ import annotations

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import _logs, metrics, trace
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from tactistream import __version__
from tactistream.settings import Settings

SERVICE_NAME = "tactistream-api"

_configured = False
_sdk_installed = False


def telemetry_resource(settings: Settings) -> Resource:
    return Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": __version__,
            "deployment.environment": settings.environment,
        }
    )


def setup_telemetry(settings: Settings) -> bool:
    """Install providers once per process; returns whether Azure Monitor export is enabled."""
    global _configured, _sdk_installed
    resource = telemetry_resource(settings)
    connection_string = settings.applicationinsights_connection_string
    if connection_string:
        if not _configured:
            configure_azure_monitor(connection_string=connection_string, resource=resource)
            _configured = True
        return True
    if not _sdk_installed and not _configured:
        trace.set_tracer_provider(TracerProvider(resource=resource))
        metrics.set_meter_provider(MeterProvider(resource=resource))
        _logs.set_logger_provider(LoggerProvider(resource=resource))
        _sdk_installed = True
    return False
