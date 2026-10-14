"""`tactistream-smoke foundry|eventhubs`: exit 0 on a verified round-trip, 1 on failure, 2 on missing env."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from typing import Any

import typer

from tactistream.settings import Settings
from tactistream.smoke.eventhubs import run_eventhubs_smoke
from tactistream.smoke.foundry import run_foundry_smoke

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="Prove Azure access: Foundry chat and Event Hubs round-trips.",
)


def load_settings() -> Settings:
    return Settings()


def require(values: dict[str, str | None]) -> dict[str, str]:
    missing = [name for name, value in values.items() if not value]
    if missing:
        typer.echo(f"Missing {', '.join(missing)} (set in the environment or .env)", err=True)
        raise typer.Exit(2)
    return {name: value for name, value in values.items() if value}


def run_or_exit[T](name: str, coroutine: Coroutine[Any, Any, T]) -> T:
    try:
        return asyncio.run(coroutine)
    except Exception as exc:
        typer.echo(f"{name} smoke failed: {type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(1) from None


@app.command()
def foundry(
    region: str | None = typer.Option(
        None, envvar="AZURE_LOCATION", help="Region of the Foundry resource, echoed in the report."
    ),
) -> None:
    """Ask the Foundry deployment for a JSON echo via Agent Framework and validate it."""
    settings = load_settings()
    env = require(
        {
            "FOUNDRY_PROJECT_ENDPOINT": settings.foundry_project_endpoint,
            "FOUNDRY_MODEL_DEPLOYMENT": settings.foundry_model_deployment,
        }
    )
    result = run_or_exit(
        "foundry",
        run_foundry_smoke(env["FOUNDRY_PROJECT_ENDPOINT"], env["FOUNDRY_MODEL_DEPLOYMENT"], region=region),
    )
    typer.echo(f"deployment: {result.deployment}")
    typer.echo(f"model: {result.model or 'unknown'}")
    typer.echo(f"region: {result.region}")
    typer.echo(f"latency_ms: {result.latency_ms}")
    typer.echo(f"tokens_in: {result.input_tokens}")
    typer.echo(f"tokens_out: {result.output_tokens}")
    typer.echo(f"reply: {json.dumps(result.reply)}")


@app.command()
def eventhubs() -> None:
    """Publish one envelope to Event Hubs and read it back through consumer group `live-state`."""
    settings = load_settings()
    env = require({"EVENTHUBS_FULLY_QUALIFIED_NAMESPACE": settings.eventhubs_fully_qualified_namespace})
    result = run_or_exit(
        "eventhubs",
        run_eventhubs_smoke(env["EVENTHUBS_FULLY_QUALIFIED_NAMESPACE"], settings.eventhubs_name),
    )
    typer.echo(f"namespace: {result.namespace}")
    typer.echo(f"hub: {result.hub}")
    typer.echo(f"consumer_group: {result.consumer_group}")
    typer.echo(f"record_id: {result.record_id} (matched)")
    typer.echo(f"round_trip_ms: {result.round_trip_ms}")
