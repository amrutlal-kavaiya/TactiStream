import json
import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from typer.testing import CliRunner

from tactistream.api import ws
from tactistream.api.app import create_app
from tactistream.settings import Settings
from tactistream.smoke.cli import app as smoke_app
from tactistream.smoke.deployed import DeployedSmokeError, run_deployed_smoke


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


@pytest.fixture
def base_url() -> Iterator[str]:
    port = free_port()
    app = create_app(Settings(_env_file=None, bus="memory", static_dir=None))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "uvicorn did not start"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


async def test_smoke_passes_against_memory_bus_when_allowed(base_url: str) -> None:
    result = await run_deployed_smoke(base_url, allow_memory=True)
    assert result.healthz_ok is True
    assert result.bus == "memory"
    assert result.match_id == "demo-blue-amber-001"
    assert 0 <= result.snapshot_ms <= 5000
    assert 0 <= result.first_event_ms <= 15000
    assert result.heartbeats == 0


async def test_smoke_requires_eventhubs_unless_allowed(base_url: str) -> None:
    with pytest.raises(DeployedSmokeError, match="bus is memory, expected eventhubs") as info:
        await run_deployed_smoke(base_url)
    assert info.value.exit_code == 1


async def test_soak_keeps_socket_open_and_counts_heartbeats(
    base_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ws, "HEARTBEAT_MS", 500)
    result = await run_deployed_smoke(base_url, allow_memory=True, soak_s=2)
    assert result.heartbeats >= 2
    assert result.soak_s == 2


async def test_unreachable_url_raises_with_exit_code_2() -> None:
    with pytest.raises(DeployedSmokeError) as info:
        await run_deployed_smoke(f"http://127.0.0.1:{free_port()}", timeout_s=2)
    assert info.value.exit_code == 2
    assert "healthz" in str(info.value)


def test_cli_unreachable_exits_2_with_one_line_and_no_traceback() -> None:
    result = CliRunner().invoke(
        smoke_app, ["deployed", "--base-url", f"http://127.0.0.1:{free_port()}", "--timeout-s", "2"]
    )
    assert result.exit_code == 2
    lines = result.output.strip().splitlines()
    assert len(lines) == 1
    summary = json.loads(lines[0])
    assert summary["ok"] is False
    assert summary["reason"]
    assert "Traceback" not in result.output


def test_cli_prints_one_line_json_summary_on_success(base_url: str) -> None:
    result = CliRunner().invoke(smoke_app, ["deployed", "--base-url", base_url, "--allow-memory"])
    assert result.exit_code == 0, result.output
    (line,) = result.output.strip().splitlines()
    summary = json.loads(line)
    assert summary["ok"] is True
    assert summary["healthz_ok"] is True
    assert {"snapshot_ms", "first_event_ms", "bus", "match_id"} <= set(summary)
