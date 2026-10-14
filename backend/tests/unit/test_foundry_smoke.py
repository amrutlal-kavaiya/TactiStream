import json
from collections.abc import Iterator, Sequence
from typing import Any

import pytest
from agent_framework import ChatResponse, Message

from tactistream.smoke.foundry import SmokeError, run_foundry_smoke

ENDPOINT = "https://x.services.ai.azure.com/api/projects/p"
TOKEN = "f00dfeed"


class FakeChatClient:
    def __init__(self, text: str, usage: dict[str, int] | None = None) -> None:
        self.text = text
        self.usage = usage
        self.calls: list[Sequence[Message]] = []

    async def get_response(self, messages: Sequence[Message]) -> ChatResponse[Any]:
        self.calls.append(messages)
        return ChatResponse(
            messages=[Message(role="assistant", contents=[self.text])],
            model="gpt-4o-mini-2024-07-18",
            usage_details=self.usage,  # type: ignore[arg-type]
        )


class Factory:
    def __init__(self, client: FakeChatClient) -> None:
        self.client = client
        self.args: tuple[str, str, object] | None = None

    def __call__(self, endpoint: str, deployment: str, credential: object) -> FakeChatClient:
        self.args = (endpoint, deployment, credential)
        return self.client


def ticks(*seconds: float) -> Iterator[float]:
    return iter(seconds)


async def run(text: str, usage: dict[str, int] | None = None, **kw: Any) -> tuple[Any, Factory]:
    factory = Factory(FakeChatClient(text, usage))
    clock = ticks(10.0, 10.4125)
    result = await run_foundry_smoke(
        ENDPOINT,
        "gpt-4o-mini",
        region=kw.pop("region", "swedencentral"),
        credential="cred",
        client_factory=factory,
        clock=lambda: next(clock),
        token=TOKEN,
        **kw,
    )
    return result, factory


async def test_round_trip_reports_deployment_region_latency_tokens_and_reply() -> None:
    reply = json.dumps({"ok": True, "echo": TOKEN})
    result, factory = await run(reply, {"input_token_count": 31, "output_token_count": 12})
    assert factory.args == (ENDPOINT, "gpt-4o-mini", "cred")
    assert result.deployment == "gpt-4o-mini"
    assert result.model == "gpt-4o-mini-2024-07-18"
    assert result.region == "swedencentral"
    assert result.latency_ms == 412
    assert (result.input_tokens, result.output_tokens) == (31, 12)
    assert result.reply == {"ok": True, "echo": TOKEN}


async def test_prompt_carries_the_token_and_asks_for_json() -> None:
    _, factory = await run(json.dumps({"ok": True, "echo": TOKEN}))
    (messages,) = factory.client.calls
    prompt = " ".join(m.text for m in messages)
    assert TOKEN in prompt
    assert "JSON" in prompt


async def test_code_fenced_json_is_accepted() -> None:
    result, _ = await run(f'```json\n{{"ok": true, "echo": "{TOKEN}"}}\n```')
    assert result.reply == {"ok": True, "echo": TOKEN}


async def test_missing_usage_and_region_are_reported_as_unknown() -> None:
    result, _ = await run(json.dumps({"ok": True, "echo": TOKEN}), region=None)
    assert result.region == "unknown"
    assert (result.input_tokens, result.output_tokens) == (None, None)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("sure, here it is", "not JSON"),
        (json.dumps({"ok": True, "echo": "other"}), "echo mismatch"),
        (json.dumps({"ok": False, "echo": TOKEN}), "schema"),
        (json.dumps({"ok": True, "echo": TOKEN, "extra": 1}), "schema"),
        (json.dumps(["ok", TOKEN]), "schema"),
    ],
)
async def test_invalid_replies_raise_smoke_error(text: str, reason: str) -> None:
    with pytest.raises(SmokeError, match=reason):
        await run(text)
