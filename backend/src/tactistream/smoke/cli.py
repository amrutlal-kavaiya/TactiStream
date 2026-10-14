"""`tactistream-smoke` commands; each prints one JSON line and exits non-zero on failure."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any

import typer

from tactistream.smoke.deployed import DeployedSmokeError, run_deployed_smoke

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def main() -> None:
    """Smoke checks for TactiStream deployments."""


def _emit(summary: dict[str, Any]) -> None:
    typer.echo(json.dumps(summary, separators=(",", ":")))


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
