import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from tactistream.agents.model_client import (
    ModelError,
    ModelResponse,
    ModelTimeout,
    Role,
    SchemaRef,
    ScriptedModelClient,
    ScriptedReply,
    TimeoutModelClient,
    load_script,
    validate_role_output,
)
from tactistream.transport.clock import FakeClock

EXAMPLES = Path(__file__).parents[3] / "contracts" / "examples"


def analyst_output() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXAMPLES / "analyst_output.json").read_text(encoding="utf-8"))
    return data


def user(moment_id: str = "mom-0045", attempt: int | None = 1) -> str:
    body: dict[str, Any] = {"input_version": 1, "moment": {"moment_id": moment_id}}
    if attempt is not None:
        body["attempt"] = attempt
    return json.dumps(body)


def reply(**overrides: Any) -> ScriptedReply:
    fields: dict[str, Any] = {
        "role": "analyst",
        "moment_id": "mom-0045",
        "attempt": 1,
        "data": analyst_output(),
        "usage_in": 1900,
        "usage_out": 260,
    }
    fields.update(overrides)
    return ScriptedReply(**fields)


def client_for(*replies: ScriptedReply, clock: FakeClock | None = None) -> ScriptedModelClient:
    return ScriptedModelClient({(r.role, r.moment_id, r.attempt): r for r in replies}, clock or FakeClock())


async def complete(
    client: ScriptedModelClient | TimeoutModelClient,
    role: Role = "analyst",
    schema_ref: SchemaRef = "AnalystOutput",
    user_json: str | None = None,
    timeout_s: float = 3.5,
) -> ModelResponse:
    return await client.complete_json(role, "system", user_json or user(), schema_ref, timeout_s)


async def test_returns_the_scripted_reply_with_usage() -> None:
    client = client_for(reply())
    response = await complete(client)
    assert response.data == analyst_output()
    assert response.usage_in == 1900
    assert response.usage_out == 260
    assert response.latency_ms == 0
    assert client.deployment == "scripted"


async def test_unknown_key_is_script_missing() -> None:
    client = client_for(reply())
    with pytest.raises(ModelError) as excinfo:
        await complete(client, user_json=user("mom-0061"))
    assert excinfo.value.kind == "script_missing"
    with pytest.raises(ModelError) as excinfo:
        await complete(client, role="verifier", schema_ref="VerifierOutput")
    assert excinfo.value.kind == "script_missing"


async def test_delay_is_slept_on_the_injected_clock() -> None:
    clock = FakeClock(start_ms=1000)
    client = client_for(reply(delay_ms=1400), clock=clock)
    task = asyncio.create_task(complete(client))
    await clock.advance(1399)
    assert not task.done()
    await clock.advance(1)
    response = await task
    assert response.latency_ms == 1400


async def test_scripted_error_kinds_raise_model_error() -> None:
    client = client_for(reply(data=None, error="invalid_json"))
    with pytest.raises(ModelError) as excinfo:
        await complete(client)
    assert excinfo.value.kind == "invalid_json"


async def test_reply_violating_the_role_schema_is_schema_invalid() -> None:
    data = analyst_output()
    data["claims"] = [*data["claims"], data["claims"][0]]
    client = client_for(reply(data=data))
    with pytest.raises(ModelError) as excinfo:
        await complete(client)
    assert excinfo.value.kind == "schema_invalid"


async def test_omitted_usage_is_none() -> None:
    client = client_for(reply(usage_in=None, usage_out=None))
    response = await complete(client)
    assert response.usage_in is None
    assert response.usage_out is None


async def test_calls_are_recorded() -> None:
    producer = {
        "moment_id": "mom-0045",
        "fan": {
            "title_template_id": "title.forward_pass",
            "claim_ids": ["clm-0045-1"],
            "annotations": [],
            "priority": 3,
            "panel": "lower_third",
        },
        "analyst": {
            "title_template_id": "title.forward_pass",
            "claim_ids": ["clm-0045-1"],
            "annotations": [],
            "priority": 3,
            "panel": "side_panel",
        },
    }
    client = client_for(reply(), reply(role="producer", data=producer))
    await complete(client, timeout_s=3.5)
    producer_user = user(attempt=None)
    await complete(
        client, role="producer", schema_ref="ProducerOutput", user_json=producer_user, timeout_s=1.5
    )
    assert client.calls == [("analyst", "mom-0045", 1, 3.5), ("producer", "mom-0045", 1, 1.5)]


async def test_lookup_reads_moment_and_attempt_from_the_user_json() -> None:
    second = analyst_output()
    second["claims"] = second["claims"][:1]
    client = client_for(reply(), reply(attempt=2, data=second))
    response = await complete(client, user_json=user(attempt=2))
    assert len(response.data["claims"]) == 1
    assert client.calls[-1].attempt == 2


class HangingClient:
    deployment = "hanging"

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.cancelled = False

    async def complete_json(
        self, role: Role, system: str, user: str, schema_ref: SchemaRef, timeout_s: float
    ) -> ModelResponse:
        try:
            await self.clock.sleep_ms(5000)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return ModelResponse(data={}, usage_in=None, usage_out=None, latency_ms=5000)


async def test_timeout_client_raises_at_the_budget_and_cancels_the_inner_call() -> None:
    clock = FakeClock(start_ms=10_000)
    inner = HangingClient(clock)
    client = TimeoutModelClient(inner, clock)
    assert client.deployment == "hanging"
    task = asyncio.create_task(complete(client, timeout_s=1.0))
    await clock.advance(999)
    assert not task.done()
    await clock.advance(1)
    assert task.done()
    with pytest.raises(ModelTimeout):
        await task
    assert clock.now_ms() == 11_000
    assert inner.cancelled


async def test_timeout_client_passes_through_fast_replies_and_errors() -> None:
    clock = FakeClock()
    inner = client_for(reply(delay_ms=400), clock=clock)
    client = TimeoutModelClient(inner, clock)
    task = asyncio.create_task(complete(client, timeout_s=1.0))
    await clock.advance(400)
    assert (await task).latency_ms == 400
    with pytest.raises(ModelError):
        await complete(client, user_json=user("mom-0099"))


async def test_scripted_timeout_error_sleeps_past_any_budget() -> None:
    clock = FakeClock()
    client = TimeoutModelClient(client_for(reply(data=None, error="timeout"), clock=clock), clock)
    task = asyncio.create_task(complete(client, timeout_s=3.5))
    await clock.advance(3500)
    with pytest.raises(ModelTimeout):
        await task


def test_load_script_reads_the_scripts_file_format(tmp_path: Path) -> None:
    path = tmp_path / "script.json"
    path.write_text(
        json.dumps(
            {
                "script_version": 1,
                "deployment": "scripted",
                "replies": [
                    {
                        "role": "analyst",
                        "moment_id": "mom-0045",
                        "attempt": 1,
                        "delay_ms": 1400,
                        "usage": {"in": 1900, "out": 260},
                        "data": analyst_output(),
                    },
                    {"role": "analyst", "moment_id": "mom-0061", "attempt": 1, "error": "invalid_json"},
                ],
            }
        ),
        encoding="utf-8",
    )
    replies = load_script(path)
    hero = replies[("analyst", "mom-0045", 1)]
    assert (hero.delay_ms, hero.usage_in, hero.usage_out) == (1400, 1900, 260)
    broken = replies[("analyst", "mom-0061", 1)]
    assert (broken.error, broken.data, broken.usage_in) == ("invalid_json", None, None)


def test_validate_role_output_covers_every_schema_ref() -> None:
    assert validate_role_output("AnalystOutput", analyst_output()).moment_id == "mom-0045"
    verdict = {"claim_id": "clm-0045-1", "decision": "approve", "reason_codes": ["ok"]}
    verdicts = {"moment_id": "mom-0045", "verdicts": [verdict]}
    assert validate_role_output("VerifierOutput", verdicts).moment_id == "mom-0045"
    with pytest.raises(ModelError) as excinfo:
        validate_role_output("SingleAgentOutput", {"analyst": analyst_output()})
    assert excinfo.value.kind == "schema_invalid"
