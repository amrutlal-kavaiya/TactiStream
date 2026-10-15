"""`tactistream-sim`: generate a scenario feed + manifest, or list scenarios (contracts/cli.md)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

import typer

from tactistream.simulator.config import (
    DEV_VARIANTS,
    EVAL_VARIANTS,
    SCENARIOS,
    ConfigError,
    SimulationConfig,
)
from tactistream.simulator.engine import simulate
from tactistream.simulator.io import write_output
from tactistream.simulator.kinematics import KinematicsError
from tactistream.simulator.possession import IllegalTransition
from tactistream.simulator.validate import validate_output

EXIT_USAGE = 2
EXIT_INVALID = 3

app = typer.Typer(add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)


def _fail(code: int, lines: list[str]) -> NoReturn:
    for line in lines:
        typer.echo(line, err=True)
    raise typer.Exit(code)


@app.command()
def generate(
    scenario: Annotated[str, typer.Option(help="Scenario family (see `list`).")],
    seed: Annotated[int, typer.Option(help="Dev seeds 1-9999, eval seeds >= 10000.")],
    out: Annotated[Path, typer.Option(help="Output directory for feed.jsonl and manifest.json.")],
    variant: Annotated[str, typer.Option(help="Variant A-F.")] = "A",
    split: Annotated[str, typer.Option(help="dev or eval.")] = "dev",
    force: Annotated[bool, typer.Option("--force", help="Overwrite a non-empty --out.")] = False,
) -> None:
    """Simulate one scenario and write its feed and ground-truth manifest."""
    try:
        config = SimulationConfig(seed, scenario, variant, split)  # type: ignore[arg-type]
        if out.exists() and any(out.iterdir()) and not force:
            raise FileExistsError(f"{out} is not empty (use --force to overwrite)")
        output = simulate(config)
    except (ConfigError, FileExistsError) as exc:
        _fail(EXIT_USAGE, [f"error: {exc}"])
    except KinematicsError as exc:
        _fail(EXIT_INVALID, ["error: generation failed", f"{exc.code} {exc.player_id} {exc}"])
    except IllegalTransition as exc:
        _fail(EXIT_INVALID, ["error: generation failed", f"illegal_transition {exc.event_id} {exc.detail}"])
    report = validate_output(output)
    if not report.ok:
        _fail(EXIT_INVALID, ["error: validation failed", *(issue.line() for issue in report.issues)])
    try:
        written = write_output(output, out, force=force)
    except FileExistsError as exc:
        _fail(EXIT_USAGE, [f"error: {exc}"])
    m = output.manifest
    typer.echo(
        f"match_id={m.match_id} events={m.event_count} frames={m.frame_count} duration_ms={m.duration_ms}"
    )
    typer.echo(f"feed_sha256={written.feed_sha256}")
    typer.echo(f"wrote {written.feed_path} {written.manifest_path}")


@app.command("list")
def list_scenarios() -> None:
    """List scenario families with their variants and seed ranges."""
    typer.echo(f"{'scenario':<19}{'dev variants':<14}{'eval variants':<15}seeds (dev | eval)")
    for name in SCENARIOS:
        has_eval = name != "demo_match"
        eval_variants = " ".join(EVAL_VARIANTS) if has_eval else "-"
        seeds = "1-9999 | >=10000" if has_eval else "1-9999 | -"
        typer.echo(f"{name:<19}{' '.join(DEV_VARIANTS):<14}{eval_variants:<15}{seeds}")
