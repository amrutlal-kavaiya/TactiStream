"""Presenter media metadata persisted as `media/state.json` (spec 009 FR-027, FR-029)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MediaSlot(StrEnum):
    MAIN = "main"
    BACKUP = "backup"
    CAPTIONS = "captions"


def _now() -> datetime:
    return datetime.now(UTC)


class MediaRecord(BaseModel):
    """One filled slot. Duration and resolution come from the browser, hence `client_reported`."""

    model_config = ConfigDict(frozen=True)

    slot: MediaSlot
    kind: Literal["file", "link"]
    url: str | None = None
    filename: str | None = None
    content_type: str | None = None
    bytes: int | None = None
    sha256: str | None = None
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    client_reported: tuple[str, ...] = ("duration_s", "width", "height")
    uploaded_at: datetime = Field(default_factory=_now)


class MediaState(BaseModel):
    model_config = ConfigDict(frozen=True)

    slots: dict[MediaSlot, MediaRecord] = Field(default_factory=dict)
    published: bool = False


class StoredObject(BaseModel):
    model_config = ConfigDict(frozen=True)

    bytes: int
    sha256: str
