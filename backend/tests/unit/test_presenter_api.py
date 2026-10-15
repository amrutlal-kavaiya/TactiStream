import hashlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from tactistream.api.app import create_app
from tactistream.api.routes_presenter import MediaLimits
from tactistream.settings import Settings
from tactistream.transport.clock import FakeClock

KEY = "correct-horse-battery"
AUTH = {"X-Presenter-Key": KEY}
MP4 = {"Content-Type": "video/mp4"}
VIDEO = bytes(range(256)) * 4
SRT = (
    "1\r\n00:00:01,000 --> 00:00:02,500\r\nHello judges\r\n\r\n2\r\n00:00:03,000 --> 00:00:04,000\r\nBye\r\n"
)


async def client_for(tmp_path: Path, key: str | None) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(_env_file=None, data_dir=tmp_path, static_dir=None, presenter_key=key)
    app = create_app(
        settings, clock=FakeClock(), media_limits=MediaLimits(video_bytes=2048, captions_bytes=512)
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await app.state.registry.aclose()
    await app.state.media_store.aclose()


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    async for c in client_for(tmp_path, KEY):
        yield c


@pytest.fixture
async def disabled(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    async for c in client_for(tmp_path, None):
        yield c


PRESENTER_CALLS = [
    ("GET", "/api/presenter/state", None),
    ("PUT", "/api/presenter/media/main", b"x"),
    ("DELETE", "/api/presenter/media/main", None),
    ("PUT", "/api/presenter/publish", b'{"published": true}'),
]


@pytest.mark.parametrize(("method", "path", "body"), PRESENTER_CALLS)
async def test_key_unset_every_presenter_route_is_404(
    disabled: httpx.AsyncClient, method: str, path: str, body: bytes | None
) -> None:
    response = await disabled.request(method, path, content=body, headers=AUTH)
    assert response.status_code == 404
    assert response.json()["error"] == "presenter_disabled"


@pytest.mark.parametrize(("method", "path", "body"), PRESENTER_CALLS)
@pytest.mark.parametrize("headers", [{}, {"X-Presenter-Key": "wrong"}, {"X-Presenter-Key": ""}])
async def test_missing_or_wrong_key_is_401(
    client: httpx.AsyncClient,
    tmp_path: Path,
    method: str,
    path: str,
    body: bytes | None,
    headers: dict[str, str],
) -> None:
    response = await client.request(method, path, content=body, headers={**MP4, **headers})
    assert response.status_code == 401
    assert response.json()["error"] == "presenter_key_invalid"
    media = tmp_path / "media"
    assert not media.exists() or list(media.iterdir()) == []


async def test_upload_main_streams_and_records_metadata(client: httpx.AsyncClient, tmp_path: Path) -> None:
    async def body() -> AsyncIterator[bytes]:
        for i in range(0, len(VIDEO), 100):
            yield VIDEO[i : i + 100]

    response = await client.put(
        "/api/presenter/media/main",
        params={"filename": "demo.mp4", "duration_s": "115.2", "width": "1920", "height": "1080"},
        content=body(),
        headers={**AUTH, **MP4},
    )
    assert response.status_code == 200, response.text
    record = response.json()
    assert record["slot"] == "main"
    assert record["kind"] == "file"
    assert record["filename"] == "demo.mp4"
    assert record["bytes"] == len(VIDEO)
    assert record["sha256"] == hashlib.sha256(VIDEO).hexdigest()
    assert (record["duration_s"], record["width"], record["height"]) == (115.2, 1920, 1080)
    assert record["client_reported"] == ["duration_s", "width", "height"]
    assert record["uploaded_at"]
    assert (tmp_path / "media" / "main").read_bytes() == VIDEO
    state = (await client.get("/api/presenter/state", headers=AUTH)).json()
    assert state["published"] is False
    assert state["slots"]["main"]["sha256"] == record["sha256"]


@pytest.mark.parametrize("content_type", ["video/webm", "text/plain", "application/octet-stream"])
async def test_non_mp4_video_is_422(client: httpx.AsyncClient, content_type: str) -> None:
    response = await client.put(
        "/api/presenter/media/backup", content=VIDEO, headers={**AUTH, "Content-Type": content_type}
    )
    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_media"


async def test_video_over_cap_is_413_and_nothing_stored(client: httpx.AsyncClient, tmp_path: Path) -> None:
    response = await client.put("/api/presenter/media/main", content=VIDEO * 3, headers={**AUTH, **MP4})
    assert response.status_code == 413
    assert response.json()["error"] == "media_too_large"
    media = tmp_path / "media"
    assert not media.exists() or list(media.iterdir()) == []
    assert (await client.get("/api/presenter/state", headers=AUTH)).json()["slots"] == {}


async def test_streamed_video_over_cap_without_content_length_is_413(client: httpx.AsyncClient) -> None:
    async def body() -> AsyncIterator[bytes]:
        for _ in range(30):
            yield VIDEO[:100]

    response = await client.put("/api/presenter/media/main", content=body(), headers={**AUTH, **MP4})
    assert response.status_code == 413
    assert response.json()["error"] == "media_too_large"


async def test_captions_srt_saved_as_vtt(client: httpx.AsyncClient, tmp_path: Path) -> None:
    response = await client.put(
        "/api/presenter/media/captions",
        params={"filename": "demo.srt"},
        content=SRT.encode(),
        headers={**AUTH, "Content-Type": "application/x-subrip"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["content_type"] == "text/vtt"
    assert response.json()["filename"] == "demo.vtt"
    saved = (tmp_path / "media" / "captions").read_text(encoding="utf-8")
    assert saved.startswith("WEBVTT\n\n")
    assert "00:00:01.000 --> 00:00:02.500\nHello judges\n" in saved
    assert "," not in saved.split("\n")[3]


async def test_captions_vtt_kept_and_cap_enforced(client: httpx.AsyncClient) -> None:
    vtt = b"WEBVTT\n\n00:00.000 --> 00:01.000\nHi\n"
    ok = await client.put(
        "/api/presenter/media/captions", content=vtt, headers={**AUTH, "Content-Type": "text/vtt"}
    )
    assert ok.status_code == 200
    assert ok.json()["bytes"] == len(vtt)
    big = await client.put(
        "/api/presenter/media/captions", content=vtt * 40, headers={**AUTH, "Content-Type": "text/vtt"}
    )
    assert big.status_code == 413


async def test_captions_must_be_text_subtitles(client: httpx.AsyncClient) -> None:
    response = await client.put(
        "/api/presenter/media/captions",
        content=b"\x00\x01binary",
        headers={**AUTH, "Content-Type": "text/vtt"},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_media"


@pytest.mark.parametrize(
    "content_type", ["text/vtt", "application/x-subrip", "text/plain", "application/octet-stream", None]
)
async def test_captions_accepted_content_types(client: httpx.AsyncClient, content_type: str | None) -> None:
    headers = {**AUTH, "Content-Type": content_type} if content_type else AUTH
    response = await client.put("/api/presenter/media/captions", content=SRT.encode(), headers=headers)
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("content_type", ["text/html", "application/pdf", "video/mp4", "image/svg+xml"])
async def test_captions_other_content_types_are_422(client: httpx.AsyncClient, content_type: str) -> None:
    response = await client.put(
        "/api/presenter/media/captions", content=SRT.encode(), headers={**AUTH, "Content-Type": content_type}
    )
    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_media"


async def test_captions_link_is_422(client: httpx.AsyncClient) -> None:
    response = await client.put(
        "/api/presenter/media/captions", json={"url": "https://example.com/c.vtt"}, headers=AUTH
    )
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
    assert (await client.get("/api/presenter/state", headers=AUTH)).json()["slots"] == {}


async def test_media_responses_are_nosniff(client: httpx.AsyncClient) -> None:
    await upload_main(client)
    await client.put("/api/presenter/publish", json={"published": True}, headers=AUTH)
    for headers in ({}, {"Range": "bytes=0-1"}, {"Range": "bytes=5000-6000"}):
        response = await client.get("/media/main", headers=headers)
        assert response.headers["x-content-type-options"] == "nosniff"
    assert (await client.head("/media/main")).headers["x-content-type-options"] == "nosniff"


async def test_link_https_only(client: httpx.AsyncClient) -> None:
    for url in ["http://youtu.be/abc", "javascript:alert(1)", "https://", "not a url"]:
        response = await client.put("/api/presenter/media/main", json={"url": url}, headers=AUTH)
        assert response.status_code == 422, url
        assert response.json()["error"] == "invalid_url"
    ok = await client.put("/api/presenter/media/main", json={"url": "https://youtu.be/abc"}, headers=AUTH)
    assert ok.status_code == 200
    assert ok.json()["kind"] == "link"
    assert ok.json()["url"] == "https://youtu.be/abc"


async def test_unknown_slot_is_404(client: httpx.AsyncClient, tmp_path: Path) -> None:
    response = await client.put(
        "/api/presenter/media/..%2Fstate.json", content=VIDEO, headers={**AUTH, **MP4}
    )
    assert response.status_code in {404, 405}
    assert not (tmp_path / "media").exists()
    assert (await client.put("/api/presenter/media/extra", content=b"", headers=AUTH)).status_code == 404


async def upload_main(client: httpx.AsyncClient) -> None:
    response = await client.put("/api/presenter/media/main", content=VIDEO, headers={**AUTH, **MP4})
    assert response.status_code == 200


async def test_config_hides_media_until_published(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/config")).json() == {"demo_media": None}
    await upload_main(client)
    assert (await client.get("/api/config")).json() == {"demo_media": None}
    published = await client.put("/api/presenter/publish", json={"published": True}, headers=AUTH)
    assert published.status_code == 200
    assert published.json()["published"] is True
    media = (await client.get("/api/config")).json()["demo_media"]
    assert media["main"]["kind"] == "file"
    assert media["main"]["url"].startswith("/media/main?v=")
    assert media["backup"] is None
    assert media["captions_url"] is None
    await client.put("/api/presenter/publish", json={"published": False}, headers=AUTH)
    assert (await client.get("/api/config")).json() == {"demo_media": None}


async def test_config_lists_backup_link_and_captions(client: httpx.AsyncClient) -> None:
    await upload_main(client)
    await client.put("/api/presenter/media/backup", json={"url": "https://youtu.be/backup"}, headers=AUTH)
    await client.put(
        "/api/presenter/media/captions",
        content=b"WEBVTT\n\n00:00.000 --> 00:01.000\nHi\n",
        headers={**AUTH, "Content-Type": "text/vtt"},
    )
    await client.put("/api/presenter/publish", json={"published": True}, headers=AUTH)
    media = (await client.get("/api/config")).json()["demo_media"]
    assert media["backup"] == {"url": "https://youtu.be/backup", "kind": "link"}
    assert media["captions_url"].startswith("/media/captions?v=")


async def test_publish_requires_main(client: httpx.AsyncClient) -> None:
    response = await client.put("/api/presenter/publish", json={"published": True}, headers=AUTH)
    assert response.status_code == 409
    assert response.json()["error"] == "main_missing"


async def test_publish_body_validated(client: httpx.AsyncClient) -> None:
    response = await client.put("/api/presenter/publish", json={"published": "maybe"}, headers=AUTH)
    assert response.status_code == 422


async def test_delete_clears_slot_and_file(client: httpx.AsyncClient, tmp_path: Path) -> None:
    await upload_main(client)
    response = await client.delete("/api/presenter/media/main", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["slots"] == {}
    assert not (tmp_path / "media" / "main").exists()


async def test_deleting_main_unpublishes(client: httpx.AsyncClient) -> None:
    await upload_main(client)
    await client.put("/api/presenter/publish", json={"published": True}, headers=AUTH)
    response = await client.delete("/api/presenter/media/main", headers=AUTH)
    assert response.json()["published"] is False
    assert (await client.get("/api/presenter/state", headers=AUTH)).json()["published"] is False
    await upload_main(client)
    assert (await client.get("/api/config")).json() == {"demo_media": None}


async def test_media_range_request_is_206(client: httpx.AsyncClient) -> None:
    await upload_main(client)
    await client.put("/api/presenter/publish", json={"published": True}, headers=AUTH)
    response = await client.get("/media/main", headers={"Range": "bytes=0-99"})
    assert response.status_code == 206
    assert response.content == VIDEO[:100]
    assert response.headers["content-range"] == f"bytes 0-99/{len(VIDEO)}"
    assert response.headers["content-length"] == "100"
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["accept-ranges"] == "bytes"


@pytest.mark.parametrize(
    ("header", "start", "end"),
    [("bytes=1000-", 1000, 1023), ("bytes=-24", 1000, 1023), ("bytes=10-5000", 10, 1023)],
)
async def test_media_open_and_suffix_ranges(
    client: httpx.AsyncClient, header: str, start: int, end: int
) -> None:
    await upload_main(client)
    await client.put("/api/presenter/publish", json={"published": True}, headers=AUTH)
    response = await client.get("/media/main", headers={"Range": header})
    assert response.status_code == 206
    assert response.content == VIDEO[start : end + 1]
    assert response.headers["content-range"] == f"bytes {start}-{end}/{len(VIDEO)}"


async def test_media_full_and_unsatisfiable(client: httpx.AsyncClient) -> None:
    await upload_main(client)
    await client.put("/api/presenter/publish", json={"published": True}, headers=AUTH)
    full = await client.get("/media/main")
    assert full.status_code == 200
    assert full.content == VIDEO
    assert full.headers["accept-ranges"] == "bytes"
    bad = await client.get("/media/main", headers={"Range": "bytes=5000-6000"})
    assert bad.status_code == 416
    assert bad.headers["content-range"] == f"bytes */{len(VIDEO)}"


async def test_media_head_has_get_headers_and_no_body(client: httpx.AsyncClient) -> None:
    await upload_main(client)
    await client.put("/api/presenter/publish", json={"published": True}, headers=AUTH)
    get = await client.get("/media/main")
    head = await client.head("/media/main")
    assert head.status_code == 200
    assert head.content == b""
    for name in ("content-length", "content-type", "accept-ranges", "etag"):
        assert head.headers[name] == get.headers[name]
    ranged = await client.head("/media/main", headers={"Range": "bytes=0-9"})
    assert ranged.status_code == 206
    assert ranged.content == b""
    assert ranged.headers["content-length"] == "10"


async def test_media_hidden_until_published_except_for_presenter(client: httpx.AsyncClient) -> None:
    await upload_main(client)
    assert (await client.get("/media/main")).status_code == 404
    assert (await client.get("/media/main", headers=AUTH)).status_code == 200


async def test_media_captions_content_type(client: httpx.AsyncClient) -> None:
    await upload_main(client)
    await client.put(
        "/api/presenter/media/captions", content=SRT.encode(), headers={**AUTH, "Content-Type": "text/plain"}
    )
    await client.put("/api/presenter/publish", json={"published": True}, headers=AUTH)
    response = await client.get("/media/captions")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/vtt")


@pytest.mark.parametrize("path", ["/media/x", "/media/state.json", "/media/..%2Fstate.json", "/media/backup"])
async def test_media_unknown_or_empty_slot_is_404(client: httpx.AsyncClient, path: str) -> None:
    await upload_main(client)
    await client.put("/api/presenter/publish", json={"published": True}, headers=AUTH)
    response = await client.get(path)
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


async def test_key_never_logged(client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    await upload_main(client)
    await client.put("/api/presenter/publish", json={"published": True}, headers=AUTH)
    await client.get("/api/presenter/state", headers={"X-Presenter-Key": KEY + "x"})
    wrong = await client.get("/api/presenter/state", headers={"X-Presenter-Key": "guess"})
    assert "guess" not in wrong.text
    await client.get("/media/main", headers={**AUTH, "Range": "bytes=0-1"})
    assert KEY not in caplog.text
    assert caplog.records, "expected some log output to inspect"
