"""`GET /api/matches/{match_id}/evidence/{evidence_id}` with as-of access to the session clock."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from tactistream.api.errors import ApiError
from tactistream.api.routes_sessions import session_or_404
from tactistream.contracts import Language

router = APIRouter()


@router.get("/api/matches/{match_id}/evidence/{evidence_id}")
async def get_evidence(
    match_id: str, evidence_id: str, request: Request, language: Language = "en"
) -> dict[str, Any]:
    session = session_or_404(request, match_id)
    entry = session.evidence.resolve(evidence_id, as_of_ms=session.replayer.session_clock_ms)
    if entry is None:
        raise ApiError(404, "evidence_not_found", f"{evidence_id} is not available in match {match_id}")
    return {
        "evidence_id": entry.evidence_id,
        "kind": entry.kind,
        "record": entry.record.model_dump(mode="json", exclude_none=True),
    }
