"""`POST /api/sessions` and `POST /api/matches/{match_id}/control`."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from tactistream.api.errors import ApiError
from tactistream.api.session import MatchSession, SessionRegistry, SessionStartError, UnknownScenarioError

router = APIRouter()


class CreateSessionRequest(BaseModel):
    scenario: str


class ControlRequest(BaseModel):
    action: str


def registry_of(request: Request) -> SessionRegistry:
    registry: SessionRegistry = request.app.state.registry
    return registry


def session_or_404(request: Request, match_id: str) -> MatchSession:
    session = registry_of(request).get(match_id)
    if session is None:
        raise ApiError(404, "match_not_found", f"no session for match {match_id}")
    return session


@router.post("/api/sessions")
async def create_session(body: CreateSessionRequest, request: Request) -> dict[str, str]:
    try:
        session = await registry_of(request).create(body.scenario)
    except UnknownScenarioError as exc:
        raise ApiError(422, "invalid_scenario", str(exc)) from exc
    except SessionStartError as exc:
        raise ApiError(503, "session_start_timeout", str(exc)) from exc
    return {
        "session_id": session.session_id,
        "match_id": session.match_id,
        "ws_path": f"/ws/matches/{session.match_id}",
    }


@router.post("/api/matches/{match_id}/control")
async def control(match_id: str, body: ControlRequest, request: Request) -> dict[str, Any]:
    session = session_or_404(request, match_id)
    if body.action == "play":
        await session.play()
    elif body.action == "pause":
        session.pause()
    elif body.action == "reset":
        await session.reset()
    else:
        raise ApiError(422, "invalid_action", f"unsupported action {body.action!r}")
    return {
        "playback": session.playback.model_dump(mode="json"),
        "session_clock_ms": session.replayer.session_clock_ms,
    }
