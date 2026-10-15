from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from tactistream.api.app import create_app
from tactistream.settings import Settings
from tactistream.transport.clock import FakeClock

INDEX = "<!doctype html><title>TactiStream SPA</title>"
APP_JS = "console.log('tactistream')"


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text(APP_JS, encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    return tmp_path


async def client_for(static_dir: Path | None) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(Settings(_env_file=None, static_dir=static_dir), clock=FakeClock())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await app.state.registry.aclose()


@pytest.fixture
async def client(static_dir: Path) -> AsyncIterator[httpx.AsyncClient]:
    async for c in client_for(static_dir):
        yield c


@pytest.mark.parametrize("path", ["/", "/evidence", "/demo?seed=42", "/matches/demo-blue-amber-001/trace"])
async def test_client_routes_return_index_html(client: httpx.AsyncClient, path: str) -> None:
    response = await client.get(path)
    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["content-type"].startswith("text/html")


async def test_assets_are_served(client: httpx.AsyncClient) -> None:
    response = await client.get("/assets/app.js")
    assert response.status_code == 200
    assert response.text == APP_JS
    assert "javascript" in response.headers["content-type"]


async def test_root_level_static_files_are_served(client: httpx.AsyncClient) -> None:
    response = await client.get("/favicon.svg")
    assert response.status_code == 200
    assert response.text == "<svg/>"


async def test_missing_asset_is_404_not_index(client: httpx.AsyncClient) -> None:
    assert (await client.get("/assets/missing.js")).status_code == 404


@pytest.mark.parametrize("path", ["/api/unknown", "/api/matches/x/nothing", "/ws/unknown", "/healthz/extra"])
async def test_reserved_prefixes_return_not_found_envelope(client: httpx.AsyncClient, path: str) -> None:
    response = await client.get(path)
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert set(body) == {"error", "detail"}


async def test_path_traversal_does_not_escape_static_dir(client: httpx.AsyncClient, static_dir: Path) -> None:
    (static_dir.parent / "secret.txt").write_text("secret", encoding="utf-8")
    response = await client.get("/..%2Fsecret.txt")
    assert "secret" not in response.text


async def test_healthz_unaffected(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_existing_api_routes_still_win(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/matches/demo-blue-amber-001/evidence/evt-0042")
    assert response.status_code == 404
    assert response.json()["error"] == "match_not_found"


async def test_missing_static_dir_starts_and_root_is_404(tmp_path: Path) -> None:
    async for client in client_for(tmp_path / "does-not-exist"):
        assert (await client.get("/")).status_code == 404
        assert (await client.get("/healthz")).status_code == 200
        response = await client.get("/api/unknown")
        assert response.status_code == 404
        assert response.json()["error"] == "not_found"
