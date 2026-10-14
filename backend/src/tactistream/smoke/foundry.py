"""Foundry chat round-trip through Microsoft Agent Framework: ask for a JSON echo token and validate it."""

from __future__ import annotations

import json
import re
import secrets
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from agent_framework import ChatResponse, Message
from jsonschema import Draft202012Validator

REPLY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"ok": {"const": True}, "echo": {"type": "string"}},
    "required": ["ok", "echo"],
    "additionalProperties": False,
}
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class SmokeError(Exception):
    """The service answered but the answer failed validation."""


class SmokeChatClient(Protocol):
    def get_response(self, messages: Sequence[Message]) -> Awaitable[ChatResponse[Any]]: ...


ChatClientFactory = Callable[[str, str, Any], SmokeChatClient]


@dataclass(frozen=True)
class FoundrySmokeResult:
    deployment: str
    model: str | None
    region: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    reply: dict[str, Any]


def foundry_chat_client(endpoint: str, deployment: str, credential: Any) -> SmokeChatClient:
    from agent_framework.foundry import FoundryChatClient

    client: SmokeChatClient = FoundryChatClient(
        project_endpoint=endpoint, model=deployment, credential=credential
    )
    return client


def prompt(token: str) -> list[Message]:
    return [
        Message(role="system", contents=["You are a connectivity probe. Reply with one JSON object only."]),
        Message(
            role="user",
            contents=[f'Return exactly this JSON and nothing else: {{"ok": true, "echo": "{token}"}}'],
        ),
    ]


def parse_reply(text: str, token: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = _FENCE.match(stripped)
    try:
        reply = json.loads(fenced.group(1) if fenced else stripped)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"reply is not JSON: {text[:200]!r}") from exc
    errors = sorted(Draft202012Validator(REPLY_SCHEMA).iter_errors(reply), key=str)
    if errors:
        raise SmokeError(f"reply fails the schema: {errors[0].message}")
    if reply["echo"] != token:
        raise SmokeError(f"echo mismatch: sent {token!r}, got {reply['echo']!r}")
    result: dict[str, Any] = reply
    return result


async def run_foundry_smoke(
    endpoint: str,
    deployment: str,
    *,
    region: str | None = None,
    credential: Any = None,
    client_factory: ChatClientFactory = foundry_chat_client,
    clock: Callable[[], float] = time.perf_counter,
    token: str | None = None,
) -> FoundrySmokeResult:
    """One chat call. Without an injected `credential`, an async `DefaultAzureCredential` is used."""
    token = token or secrets.token_hex(8)
    if credential is None:
        from azure.identity.aio import DefaultAzureCredential

        async with DefaultAzureCredential() as owned:
            return await _round_trip(endpoint, deployment, region, owned, client_factory, clock, token)
    return await _round_trip(endpoint, deployment, region, credential, client_factory, clock, token)


async def _round_trip(
    endpoint: str,
    deployment: str,
    region: str | None,
    credential: Any,
    client_factory: ChatClientFactory,
    clock: Callable[[], float],
    token: str,
) -> FoundrySmokeResult:
    client = client_factory(endpoint, deployment, credential)
    started = clock()
    response = await client.get_response(prompt(token))
    latency_ms = round((clock() - started) * 1000)
    usage = response.usage_details or {}
    return FoundrySmokeResult(
        deployment=deployment,
        model=response.model,
        region=region or "unknown",
        latency_ms=latency_ms,
        input_tokens=usage.get("input_token_count"),
        output_tokens=usage.get("output_token_count"),
        reply=parse_reply(response.text, token),
    )
