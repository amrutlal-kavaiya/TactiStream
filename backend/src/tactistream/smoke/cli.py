"""`tactistream-smoke foundry|eventhubs|deployed`: exit 0 on success, 1 on failure, 2 on missing env."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from typing import Annotated, Any

import typer

from tactistream.settings import Settings
from tactistream.smoke.deployed import DeployedSmokeError, run_deployed_smoke
from tactistream.smoke.eventhubs import run_eventhubs_smoke
from tactistream.smoke.foundry import run_foundry_smoke

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="Prove Azure access (Foundry chat, Event Hubs round-trip) and check running deployments.",
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


def _emit(summary: dict[str, Any]) -> None:
    typer.echo(json.dumps(summary, separators=(",", ":")))


@app.command()
def foundry(
    region: str | None = typer.Option(
        None, help="Region of the Foundry resource, echoed in the report (default: AZURE_LOCATION)."
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
        run_foundry_smoke(
            env["FOUNDRY_PROJECT_ENDPOINT"],
            env["FOUNDRY_MODEL_DEPLOYMENT"],
            region=region or settings.azure_location,
        ),
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
    """Publish one envelope to Event Hubs and read it back through EVENTHUBS_CONSUMER_GROUP (`live-state`)."""
    settings = load_settings()
    env = require({"EVENTHUBS_FULLY_QUALIFIED_NAMESPACE": settings.eventhubs_fully_qualified_namespace})
    result = run_or_exit(
        "eventhubs",
        run_eventhubs_smoke(
            env["EVENTHUBS_FULLY_QUALIFIED_NAMESPACE"],
            settings.eventhubs_name,
            consumer_group=settings.eventhubs_consumer_group,
        ),
    )
    typer.echo(f"namespace: {result.namespace}")
    typer.echo(f"hub: {result.hub}")
    typer.echo(f"consumer_group: {result.consumer_group}")
    typer.echo(f"record_id: {result.record_id} (matched)")
    typer.echo(f"round_trip_ms: {result.round_trip_ms}")


@app.command()
def deployed(
    base_url: Annotated[
        str, typer.Option(help="App URL, e.g. https://tactistream.<env>.azurecontainerapps.io")
    ],
    allow_memory: Annotated[bool, typer.Option(help="Accept bus=memory (local image smoke).")] = False,
    timeout_s: Annotated[float, typer.Option(help="HTTP and WebSocket connect timeout.")] = 30,
    soak_s: Annotated[int, typer.Option(help="Keep the WebSocket open this long, counting heartbeats.")] = 0,
) -> None:
    """Healthz, session, WebSocket snapshot within 5 s, first event within 15 s after play."""
    try:
        result = asyncio.run(
            run_deployed_smoke(base_url, allow_memory=allow_memory, timeout_s=timeout_s, soak_s=soak_s)
        )
    except DeployedSmokeError as exc:
        _emit({"ok": False, "base_url": base_url, "reason": exc.reason})
        raise typer.Exit(exc.exit_code) from None
    except Exception as exc:
        _emit({"ok": False, "base_url": base_url, "reason": f"unexpected {type(exc).__name__}: {exc}"})
        raise typer.Exit(1) from None
    _emit(result.summary())
