"""Presenter media API (key-protected), public `GET /api/config`, seekable `GET /media/{slot}` (009 US6)."""

from __future__ import annotations

import asyncio
import hmac
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, ValidationError

from tactistream.api.errors import ApiError
from tactistream.media import MediaRecord, MediaSlot, MediaState, MediaStore, MediaTooLarge
from tactistream.settings import Settings

logger = logging.getLogger(__name__)

KEY_HEADER = "X-Presenter-Key"
VIDEO_TYPE = "video/mp4"
VTT_TYPE = "text/vtt"
_JSON_BODY_LIMIT = 8 * 1024
_SRT_TIME = re.compile(r"(\d{2}:\d{2}:\d{2}),(\d{3})")
_RANGE = re.compile(r"bytes=(\d*)-(\d*)")


@dataclass(frozen=True)
class MediaLimits:
    video_bytes: int = 500 * 1024 * 1024
    captions_bytes: int = 1024 * 1024


class MediaContext:
    """Per-app media store plus locks serialising uploads per slot and `state.json` read-modify-write."""

    def __init__(self, store: MediaStore, limits: MediaLimits) -> None:
        self.store = store
        self.limits = limits
        self.state_lock = asyncio.Lock()
        self.slot_locks = {slot: asyncio.Lock() for slot in MediaSlot}


class _Link(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str


class _Publish(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    published: bool


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _media(request: Request) -> MediaContext:
    ctx: MediaContext = request.app.state.media
    return ctx


def _key_matches(request: Request) -> bool:
    key = _settings(request).presenter_key
    if key is None:
        return False
    supplied = request.headers.get(KEY_HEADER, "").encode("utf-8")
    return hmac.compare_digest(supplied, key.get_secret_value().encode("utf-8"))


def require_presenter(request: Request) -> None:
    if _settings(request).presenter_key is None:
        raise ApiError(404, "presenter_disabled", "presenter mode is disabled on this server")
    if not _key_matches(request):
        raise ApiError(401, "presenter_key_invalid", f"missing or wrong {KEY_HEADER} header")


def _slot_or_404(slot: str) -> MediaSlot:
    try:
        return MediaSlot(slot)
    except ValueError:
        raise ApiError(404, "not_found", "unknown media slot") from None


def _mime(request: Request) -> str:
    return request.headers.get("content-type", "").split(";", 1)[0].strip().lower()


def _content_length(request: Request) -> int | None:
    raw = request.headers.get("content-length")
    return int(raw) if raw is not None and raw.isdigit() else None


def _too_large(limit: int) -> ApiError:
    return ApiError(413, "media_too_large", f"upload exceeds {limit} bytes")


def _clean_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    name = PurePosixPath(filename.replace("\\", "/")).name
    name = "".join(ch for ch in name if ch.isprintable())[:200]
    return name or None


async def _read_capped(request: Request, limit: int) -> bytes:
    length = _content_length(request)
    if length is not None and length > limit:
        raise _too_large(limit)
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > limit:
            raise _too_large(limit)
    return bytes(data)


def _validated_https(url: str) -> str:
    parts = urlsplit(url.strip())
    if (
        parts.scheme != "https"
        or not parts.hostname
        or len(url) > 2048
        or any(c.isspace() for c in url.strip())
    ):
        raise ApiError(422, "invalid_url", "link must be an absolute https:// URL")
    return url.strip()


def srt_to_vtt(text: str) -> str:
    lines = [_SRT_TIME.sub(r"\1.\2", line) if "-->" in line else line for line in text.strip().split("\n")]
    return "WEBVTT\n\n" + "\n".join(lines) + "\n"


def _captions_as_vtt(data: bytes) -> bytes:
    try:
        text = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError:
        raise ApiError(422, "unsupported_media", "captions must be UTF-8 .vtt or .srt text") from None
    if "\x00" in text:
        raise ApiError(422, "unsupported_media", "captions must be UTF-8 .vtt or .srt text")
    if text.lstrip().startswith("WEBVTT"):
        return text.encode("utf-8")
    if "-->" not in text:
        raise ApiError(422, "unsupported_media", "captions must be WebVTT or SRT cues")
    return srt_to_vtt(text).encode("utf-8")


async def _single(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def _store_file(
    ctx: MediaContext,
    slot: MediaSlot,
    request: Request,
    filename: str | None,
) -> tuple[str, str | None, int, str]:
    """Returns (content_type, filename, bytes, sha256) after streaming the body into the store."""
    mime = _mime(request)
    if slot is MediaSlot.CAPTIONS:
        if mime.split("/", 1)[0] in {"video", "audio", "image"}:
            raise ApiError(422, "unsupported_media", "captions must be .vtt or .srt text")
        limit = ctx.limits.captions_bytes
        vtt = _captions_as_vtt(await _read_capped(request, limit))
        stored = await ctx.store.put(slot, _single(vtt), max_bytes=len(vtt), content_type=VTT_TYPE)
        name = _clean_filename(filename)
        if name is not None:
            name = str(PurePosixPath(name).with_suffix(".vtt"))
        return VTT_TYPE, name, stored.bytes, stored.sha256
    if mime != VIDEO_TYPE:
        raise ApiError(422, "unsupported_media", f"{slot.value} must be {VIDEO_TYPE}")
    limit = ctx.limits.video_bytes
    length = _content_length(request)
    if length is not None and length > limit:
        raise _too_large(limit)
    try:
        stored = await ctx.store.put(slot, request.stream(), max_bytes=limit, content_type=VIDEO_TYPE)
    except MediaTooLarge:
        raise _too_large(limit) from None
    return VIDEO_TYPE, _clean_filename(filename), stored.bytes, stored.sha256


async def _update_state(ctx: MediaContext, **changes: Any) -> MediaState:
    async with ctx.state_lock:
        state = await ctx.store.load_state()
        slots = dict(state.slots)
        for slot, record in changes.pop("slots", {}).items():
            if record is None:
                slots.pop(slot, None)
            else:
                slots[slot] = record
        if changes.get("published") and MediaSlot.MAIN not in slots:
            raise ApiError(409, "main_missing", "upload or link the main video before publishing")
        new = MediaState(slots=slots, published=changes.get("published", state.published))
        await ctx.store.save_state(new)
        return new


def _state_json(state: MediaState) -> dict[str, Any]:
    return state.model_dump(mode="json")


presenter = APIRouter(prefix="/api/presenter", dependencies=[Depends(require_presenter)])


@presenter.get("/state")
async def get_state(request: Request) -> dict[str, Any]:
    return _state_json(await _media(request).store.load_state())


@presenter.put("/media/{slot}")
async def put_media(
    slot: str,
    request: Request,
    filename: str | None = Query(default=None, max_length=512),
    duration_s: float | None = Query(default=None, ge=0, le=86_400),
    width: int | None = Query(default=None, gt=0, le=16_384),
    height: int | None = Query(default=None, gt=0, le=16_384),
) -> dict[str, Any]:
    media_slot = _slot_or_404(slot)
    ctx = _media(request)
    async with ctx.slot_locks[media_slot]:
        if _mime(request) == "application/json":
            try:
                link = _Link.model_validate_json(await _read_capped(request, _JSON_BODY_LIMIT))
            except ValidationError:
                raise ApiError(422, "invalid_url", 'body must be {"url": "https://…"}') from None
            record = MediaRecord(slot=media_slot, kind="link", url=_validated_https(link.url))
            await ctx.store.delete(media_slot)
        else:
            content_type, name, size, sha256 = await _store_file(ctx, media_slot, request, filename)
            is_video = media_slot is not MediaSlot.CAPTIONS
            record = MediaRecord(
                slot=media_slot,
                kind="file",
                filename=name,
                content_type=content_type,
                bytes=size,
                sha256=sha256,
                duration_s=duration_s if is_video else None,
                width=width if is_video else None,
                height=height if is_video else None,
            )
        await _update_state(ctx, slots={media_slot: record})
    logger.info("presenter media slot=%s kind=%s bytes=%s", media_slot.value, record.kind, record.bytes)
    return record.model_dump(mode="json")


@presenter.delete("/media/{slot}")
async def delete_media(slot: str, request: Request) -> dict[str, Any]:
    media_slot = _slot_or_404(slot)
    ctx = _media(request)
    async with ctx.slot_locks[media_slot]:
        await ctx.store.delete(media_slot)
        state = await _update_state(ctx, slots={media_slot: None})
    return _state_json(state)


@presenter.put("/publish")
async def publish(request: Request) -> dict[str, Any]:
    try:
        body = _Publish.model_validate_json(await _read_capped(request, _JSON_BODY_LIMIT))
    except ValidationError:
        raise ApiError(422, "invalid_request", 'body must be {"published": true|false}') from None
    return _state_json(await _update_state(_media(request), published=body.published))


public = APIRouter()


def _public_url(record: MediaRecord) -> str:
    if record.kind == "link":
        return record.url or ""
    return f"/media/{record.slot.value}?v={(record.sha256 or '')[:12]}"


@public.get("/api/config")
async def get_config(request: Request) -> dict[str, Any]:
    state = await _media(request).store.load_state()
    main = state.slots.get(MediaSlot.MAIN)
    if not state.published or main is None:
        return {"demo_media": None}
    backup = state.slots.get(MediaSlot.BACKUP)
    captions = state.slots.get(MediaSlot.CAPTIONS)
    return {
        "demo_media": {
            "main": {"url": _public_url(main), "kind": main.kind},
            "backup": {"url": _public_url(backup), "kind": backup.kind} if backup else None,
            "captions_url": _public_url(captions) if captions else None,
        }
    }


class _RangeNotSatisfiableError(Exception):
    pass


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Single `bytes=` range → inclusive (start, end); None means serve the whole file."""
    if not header:
        return None
    match = _RANGE.fullmatch(header.strip())
    if match is None or match.group(1) == match.group(2) == "":
        return None
    first, last = match.groups()
    if first == "":
        suffix = int(last)
        if suffix == 0 or size == 0:
            raise _RangeNotSatisfiableError
        return max(size - suffix, 0), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start >= size or start > end:
        raise _RangeNotSatisfiableError
    return start, end


@public.api_route("/media/{slot}", methods=["GET", "HEAD"])
async def get_media(slot: str, request: Request) -> Response:
    media_slot = _slot_or_404(slot)
    ctx = _media(request)
    state = await ctx.store.load_state()
    if not state.published and not _key_matches(request):
        raise ApiError(404, "media_not_published", "the demo media is not published yet")
    record = state.slots.get(media_slot)
    size = await ctx.store.size(media_slot) if record is not None and record.kind == "file" else None
    if record is None or size is None:
        raise ApiError(404, "not_found", f"no file in media slot {media_slot.value}")
    content_type = record.content_type or "application/octet-stream"
    etag = f'"{record.sha256}"'
    headers = {"Accept-Ranges": "bytes", "ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    try:
        byte_range = parse_range(request.headers.get("range"), size)
    except _RangeNotSatisfiableError:
        return JSONResponse(
            {"error": "range_not_satisfiable", "detail": f"file has {size} bytes"},
            status_code=416,
            headers={**headers, "Content-Range": f"bytes */{size}"},
        )
    if byte_range is None:
        status, start, length = 200, 0, size
    else:
        start, end = byte_range
        status, length = 206, end - start + 1
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(length)
    if request.method == "HEAD":
        return Response(status_code=status, media_type=content_type, headers=headers)
    return StreamingResponse(
        ctx.store.read(media_slot, start, length), status_code=status, media_type=content_type, headers=headers
    )
