import hashlib
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from azure.core.exceptions import ResourceNotFoundError

from tactistream.media import (
    BlobMediaStore,
    LocalMediaStore,
    MediaRecord,
    MediaSlot,
    MediaState,
    MediaStore,
    MediaTooLarge,
    build_media_store,
)
from tactistream.settings import Settings


class FakeDownloader:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def readall(self) -> bytes:
        return self._data

    async def chunks(self) -> AsyncIterator[bytes]:
        for i in range(0, len(self._data), 7):
            yield self._data[i : i + 7]


class FakeProperties:
    def __init__(self, size: int) -> None:
        self.size = size


class FakeBlobClient:
    def __init__(self, container: "FakeContainerClient", name: str) -> None:
        self._c = container
        self._name = name

    async def stage_block(self, block_id: str, data: bytes, **_: Any) -> None:
        self._c.staged.setdefault(self._name, {})[block_id] = bytes(data)

    async def commit_block_list(self, block_list: list[str], **kwargs: Any) -> None:
        staged = self._c.staged.pop(self._name, {})
        self._c.blobs[self._name] = b"".join(staged[b] for b in block_list)
        self._c.content_types[self._name] = kwargs["content_settings"].content_type

    async def upload_blob(self, data: bytes, **kwargs: Any) -> None:
        assert kwargs.get("overwrite") is True
        self._c.blobs[self._name] = bytes(data)

    async def download_blob(self, offset: int | None = None, length: int | None = None) -> FakeDownloader:
        data = self._require()
        start = offset or 0
        end = len(data) if length is None else start + length
        return FakeDownloader(data[start:end])

    async def get_blob_properties(self) -> FakeProperties:
        return FakeProperties(len(self._require()))

    async def delete_blob(self) -> None:
        self._require()
        del self._c.blobs[self._name]

    def _require(self) -> bytes:
        if self._name not in self._c.blobs:
            raise ResourceNotFoundError("missing")
        return self._c.blobs[self._name]


class FakeContainerClient:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.staged: dict[str, dict[str, bytes]] = {}
        self.content_types: dict[str, str] = {}
        self.closed = False

    def get_blob_client(self, name: str) -> FakeBlobClient:
        return FakeBlobClient(self, name)

    async def close(self) -> None:
        self.closed = True


StoreFactory = Callable[[], MediaStore]


@pytest.fixture(params=["local", "blob"])
def make_store(request: pytest.FixtureRequest, tmp_path: Path) -> StoreFactory:
    if request.param == "local":
        return lambda: LocalMediaStore(tmp_path / "media")
    container = FakeContainerClient()
    return lambda: BlobMediaStore(container, block_size=10)


async def chunks_of(data: bytes, size: int = 13) -> AsyncIterator[bytes]:
    for i in range(0, len(data), size):
        yield data[i : i + size]


async def read_all(store: MediaStore, slot: MediaSlot, offset: int = 0, length: int | None = None) -> bytes:
    return b"".join([c async for c in store.read(slot, offset, length)])


PAYLOAD = bytes(range(256)) * 3


async def test_streamed_put_reports_bytes_and_sha256(make_store: StoreFactory) -> None:
    store = make_store()
    stored = await store.put(MediaSlot.MAIN, chunks_of(PAYLOAD), max_bytes=10_000, content_type="video/mp4")
    assert stored.bytes == len(PAYLOAD)
    assert stored.sha256 == hashlib.sha256(PAYLOAD).hexdigest()
    assert await store.size(MediaSlot.MAIN) == len(PAYLOAD)
    assert await read_all(store, MediaSlot.MAIN) == PAYLOAD


async def test_ranged_read(make_store: StoreFactory) -> None:
    store = make_store()
    await store.put(MediaSlot.BACKUP, chunks_of(PAYLOAD), max_bytes=10_000, content_type="video/mp4")
    assert await read_all(store, MediaSlot.BACKUP, 100, 50) == PAYLOAD[100:150]
    assert await read_all(store, MediaSlot.BACKUP, 700) == PAYLOAD[700:]


async def test_put_replaces_and_delete_clears(make_store: StoreFactory) -> None:
    store = make_store()
    await store.put(MediaSlot.CAPTIONS, chunks_of(b"old"), max_bytes=100, content_type="text/vtt")
    await store.put(MediaSlot.CAPTIONS, chunks_of(b"WEBVTT\n"), max_bytes=100, content_type="text/vtt")
    assert await read_all(store, MediaSlot.CAPTIONS) == b"WEBVTT\n"
    await store.delete(MediaSlot.CAPTIONS)
    assert await store.size(MediaSlot.CAPTIONS) is None
    await store.delete(MediaSlot.CAPTIONS)


async def test_size_cap_raises_and_keeps_previous_file(make_store: StoreFactory) -> None:
    store = make_store()
    await store.put(MediaSlot.MAIN, chunks_of(b"previous"), max_bytes=100, content_type="video/mp4")
    with pytest.raises(MediaTooLarge):
        await store.put(MediaSlot.MAIN, chunks_of(PAYLOAD), max_bytes=100, content_type="video/mp4")
    assert await read_all(store, MediaSlot.MAIN) == b"previous"


async def test_size_cap_leaves_no_partial_file(make_store: StoreFactory) -> None:
    store = make_store()
    with pytest.raises(MediaTooLarge):
        await store.put(MediaSlot.MAIN, chunks_of(PAYLOAD), max_bytes=100, content_type="video/mp4")
    assert await store.size(MediaSlot.MAIN) is None


def test_local_size_cap_leaves_no_temp_files(tmp_path: Path) -> None:
    import asyncio

    store = LocalMediaStore(tmp_path / "media")
    with pytest.raises(MediaTooLarge):
        asyncio.run(store.put(MediaSlot.MAIN, chunks_of(PAYLOAD), max_bytes=100, content_type="video/mp4"))
    assert [p.name for p in (tmp_path / "media").iterdir()] == []


async def test_state_persists_across_instances(make_store: StoreFactory) -> None:
    assert await make_store().load_state() == MediaState()
    record = MediaRecord(
        slot=MediaSlot.MAIN,
        kind="file",
        filename="demo.mp4",
        content_type="video/mp4",
        bytes=10,
        sha256="ab" * 32,
        duration_s=115.0,
        width=1920,
        height=1080,
    )
    await make_store().save_state(MediaState(slots={MediaSlot.MAIN: record}, published=True))
    loaded = await make_store().load_state()
    assert loaded.published is True
    assert loaded.slots[MediaSlot.MAIN] == record


def test_blob_store_uses_media_prefix_and_content_type() -> None:
    import asyncio

    container = FakeContainerClient()
    store = BlobMediaStore(container, block_size=10)
    asyncio.run(store.put(MediaSlot.MAIN, chunks_of(PAYLOAD), max_bytes=10_000, content_type="video/mp4"))
    asyncio.run(store.save_state(MediaState()))
    assert set(container.blobs) == {"media/main", "media/state.json"}
    assert container.content_types["media/main"] == "video/mp4"
    asyncio.run(store.aclose())
    assert container.closed


def test_slot_is_a_closed_enum() -> None:
    assert [s.value for s in MediaSlot] == ["main", "backup", "captions"]
    with pytest.raises(ValueError):
        MediaSlot("../state.json")


def test_build_media_store_local_uses_data_dir(tmp_path: Path) -> None:
    store = build_media_store(Settings(_env_file=None, data_dir=tmp_path))
    assert isinstance(store, LocalMediaStore)
    assert store.root == tmp_path / "media"


def test_build_media_store_blob_uses_injected_factory(tmp_path: Path) -> None:
    container = FakeContainerClient()
    seen: list[str] = []

    def factory(account_url: str) -> FakeContainerClient:
        seen.append(account_url)
        return container

    settings = Settings(
        _env_file=None,
        artifact_store="blob",
        azure_storage_account_url="https://acct.blob.core.windows.net",
    )
    store = build_media_store(settings, container_factory=factory)
    assert isinstance(store, BlobMediaStore)
    assert seen == ["https://acct.blob.core.windows.net"]


def test_presenter_key_setting_is_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TACTISTREAM_PRESENTER_KEY", "s3cret-value-long")
    s = Settings(_env_file=None)
    assert s.presenter_key is not None
    assert s.presenter_key.get_secret_value() == "s3cret-value-long"
    assert "s3cret-value-long" not in repr(s)
    monkeypatch.setenv("TACTISTREAM_PRESENTER_KEY", "")
    assert Settings(_env_file=None).presenter_key is None
