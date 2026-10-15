"""Model access for the agents: one JSON-in/JSON-out call per step, validated against the role's schema."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, NamedTuple, Protocol, get_args

from pydantic import BaseModel, ValidationError

from tactistream.contracts import AnalystOutput, ContractModel, ProducerOutput, VerifierOutput
from tactistream.contracts.schema_registry import ContractError, validate
from tactistream.transport.clock import Clock

Role = Literal["analyst", "verifier", "producer", "single_agent"]
SchemaRef = Literal["AnalystOutput", "VerifierOutput", "ProducerOutput", "SingleAgentOutput"]
ModelErrorKind = Literal["invalid_json", "schema_invalid", "transport", "throttled", "script_missing"]
ScriptedErrorKind = Literal["invalid_json", "schema_invalid", "transport", "throttled", "timeout"]

_FOREVER_MS = 10**12


class SingleAgentOutput(ContractModel):
    """Internal output of the 008 single-agent baseline; both halves are canonical claim schemas."""

    analyst: AnalystOutput
    producer: ProducerOutput


_MODELS: dict[SchemaRef, type[BaseModel]] = {
    "AnalystOutput": AnalystOutput,
    "VerifierOutput": VerifierOutput,
    "ProducerOutput": ProducerOutput,
    "SingleAgentOutput": SingleAgentOutput,
}


@dataclass(frozen=True)
class ModelResponse:
    data: dict[str, Any]
    usage_in: int | None
    usage_out: int | None
    latency_ms: int


class ModelError(Exception):
    def __init__(self, kind: ModelErrorKind, detail: str = "") -> None:
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind: ModelErrorKind = kind
        self.detail = detail


class ModelTimeout(Exception):  # noqa: N818
    """The step's budget elapsed before the model replied."""


class ModelClient(Protocol):
    deployment: str

    async def complete_json(
        self, role: Role, system: str, user: str, schema_ref: SchemaRef, timeout_s: float
    ) -> ModelResponse: ...


def validate_role_output(schema_ref: SchemaRef, data: object) -> BaseModel:
    """Check `data` against the canonical schema and its model; else `ModelError("schema_invalid")`."""
    try:
        if schema_ref == "SingleAgentOutput":
            if not isinstance(data, dict):
                raise ContractError(schema_ref, "$", "expected an object")
            validate("claim.schema.json#/$defs/AnalystOutput", data.get("analyst"))
            validate("claim.schema.json#/$defs/ProducerOutput", data.get("producer"))
        else:
            validate(f"claim.schema.json#/$defs/{schema_ref}", data)
        return _MODELS[schema_ref].model_validate(data)
    except (ContractError, ValidationError) as exc:
        raise ModelError("schema_invalid", str(exc)[:200]) from exc


@dataclass(frozen=True)
class ScriptedReply:
    """Recorded decision for one `(role, moment_id, attempt)`; `error="timeout"` sleeps past any budget."""

    role: Role
    moment_id: str
    attempt: int
    data: dict[str, Any] | None = None
    error: ScriptedErrorKind | None = None
    delay_ms: int = 0
    usage_in: int | None = None
    usage_out: int | None = None


class ScriptedCall(NamedTuple):
    role: Role
    moment_id: str
    attempt: int
    timeout_s: float


ScriptKey = tuple[Role, str, int]


def load_script(path: Path) -> dict[ScriptKey, ScriptedReply]:
    """Read a `data/fixtures/agent_scripts/*.json` file (contracts/agent-io.md "Scripted replies")."""
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    replies: dict[ScriptKey, ScriptedReply] = {}
    for entry in raw.get("replies", []):
        role = entry["role"]
        if role not in get_args(Role):
            raise ValueError(f"{path}: unknown role {role!r}")
        usage = entry.get("usage") or {}
        reply = ScriptedReply(
            role=role,
            moment_id=entry["moment_id"],
            attempt=int(entry.get("attempt", 1)),
            data=entry.get("data"),
            error=entry.get("error"),
            delay_ms=int(entry.get("delay_ms", 0)),
            usage_in=usage.get("in"),
            usage_out=usage.get("out"),
        )
        replies[(reply.role, reply.moment_id, reply.attempt)] = reply
    return replies


class ScriptedModelClient:
    """Offline client replaying recorded replies keyed by role and the `moment`/`attempt` of the user JSON."""

    def __init__(
        self, replies: Mapping[ScriptKey, ScriptedReply], clock: Clock, *, deployment: str = "scripted"
    ) -> None:
        self._replies = dict(replies)
        self._clock = clock
        self.deployment = deployment
        self.calls: list[ScriptedCall] = []

    async def complete_json(
        self, role: Role, system: str, user: str, schema_ref: SchemaRef, timeout_s: float
    ) -> ModelResponse:
        moment_id, attempt = _script_key(user)
        self.calls.append(ScriptedCall(role, moment_id, attempt, timeout_s))
        reply = self._replies.get((role, moment_id, attempt))
        if reply is None:
            raise ModelError("script_missing", f"no reply for ({role}, {moment_id}, {attempt})")
        started = self._clock.now_ms()
        if reply.error == "timeout":
            await self._clock.sleep_ms(_FOREVER_MS)
        await self._clock.sleep_ms(reply.delay_ms)
        if reply.error is not None and reply.error != "timeout":
            raise ModelError(reply.error, f"scripted {reply.error}")
        if reply.data is None:
            raise ModelError("invalid_json", f"no data for ({role}, {moment_id}, {attempt})")
        validate_role_output(schema_ref, reply.data)
        return ModelResponse(
            data=reply.data,
            usage_in=reply.usage_in,
            usage_out=reply.usage_out,
            latency_ms=self._clock.now_ms() - started,
        )


def _script_key(user: str) -> tuple[str, int]:
    try:
        body = json.loads(user)
        moment_id = body["moment"]["moment_id"]
        attempt = int(body.get("attempt", 1))
    except (ValueError, KeyError, TypeError) as exc:
        raise ModelError("script_missing", "user JSON has no moment.moment_id") from exc
    if not isinstance(moment_id, str):
        raise ModelError("script_missing", "moment.moment_id is not a string")
    return moment_id, attempt


class TimeoutModelClient:
    """Enforces `timeout_s` on the injected clock and cancels the inner call when it elapses."""

    def __init__(self, inner: ModelClient, clock: Clock) -> None:
        self._inner = inner
        self._clock = clock
        self.deployment = inner.deployment

    async def complete_json(
        self, role: Role, system: str, user: str, schema_ref: SchemaRef, timeout_s: float
    ) -> ModelResponse:
        call = asyncio.ensure_future(self._inner.complete_json(role, system, user, schema_ref, timeout_s))
        timer = asyncio.ensure_future(self._clock.sleep_ms(round(timeout_s * 1000)))
        try:
            await asyncio.wait({call, timer}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (call, timer):
                if not task.done():
                    task.cancel()
            for task in (call, timer):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        if not call.cancelled() and call.done():
            return call.result()
        raise ModelTimeout(f"{role} exceeded {timeout_s:.3f} s")
