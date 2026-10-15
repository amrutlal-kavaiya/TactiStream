"""Media files + `state.json`: local `{data_dir}/media/` or blob container `artifacts` under `media/`."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import tempfile
from collections.abc import AsyncIterable, AsyncIterator, Callable
from pathlib import Path
from typing import Any, BinaryIO, Protocol

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import ContentSettings

from tactistream.media.models import MediaSlot, MediaState, StoredObject
from tactistream.settings import Settings

ARTIFACTS_CONTAINER = "artifacts"
_READ_CHUNK = 256 * 1024


class MediaTooLarge(Exception):  # noqa: N818
    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"media exceeds {max_bytes} bytes")
        self.max_bytes = max_bytes


class MediaStore(Protocol):
    async def put(
        self, slot: MediaSlot, chunks: AsyncIterable[bytes], *, max_bytes: int, content_type: str
    ) -> StoredObject:
        """Stream `chunks` into `slot`; on `MediaTooLarge` the previous content is untouched."""
        ...

    def read(self, slot: MediaSlot, offset: int = 0, length: int | None = None) -> AsyncIterator[bytes]: ...

    async def size(self, slot: MediaSlot) -> int | None: ...

    async def delete(self, slot: MediaSlot) -> None: ...

    async def load_state(self) -> MediaState: ...

    async def save_state(self, state: MediaState) -> None: ...

    async def aclose(self) -> None: ...


class LocalMediaStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, slot: MediaSlot) -> Path:
        return self.root / MediaSlot(slot).value

    async def put(
        self, slot: MediaSlot, chunks: AsyncIterable[bytes], *, max_bytes: int, content_type: str
    ) -> StoredObject:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=self.root, prefix=".upload-")
        tmp = Path(tmp_name)
        digest = hashlib.sha256()
        total = 0
        try:
            with os.fdopen(fd, "wb") as fh:
                async for chunk in chunks:
                    total += len(chunk)
                    if total > max_bytes:
                        raise MediaTooLarge(max_bytes)
                    digest.update(chunk)
                    await asyncio.to_thread(fh.write, chunk)
            await asyncio.to_thread(os.replace, tmp, self._path(slot))
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return StoredObject(bytes=total, sha256=digest.hexdigest())

    async def read(self, slot: MediaSlot, offset: int = 0, length: int | None = None) -> AsyncIterator[bytes]:
        fh: BinaryIO = await asyncio.to_thread(self._path(slot).open, "rb")
        try:
            await asyncio.to_thread(fh.seek, offset)
            remaining = length
            while remaining is None or remaining > 0:
                want = _READ_CHUNK if remaining is None else min(_READ_CHUNK, remaining)
                chunk = await asyncio.to_thread(fh.read, want)
                if not chunk:
                    break
                if remaining is not None:
                    remaining -= len(chunk)
                yield chunk
        finally:
            await asyncio.to_thread(fh.close)

    async def size(self, slot: MediaSlot) -> int | None:
        path = self._path(slot)
        return path.stat().st_size if path.is_file() else None

    async def delete(self, slot: MediaSlot) -> None:
        self._path(slot).unlink(missing_ok=True)

    async def load_state(self) -> MediaState:
        path = self.root / "state.json"
        if not path.is_file():
            return MediaState()
        return MediaState.model_validate_json(path.read_bytes())

    async def save_state(self, state: MediaState) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / ".state.json.tmp"
        tmp.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, self.root / "state.json")

    async def aclose(self) -> None:
        return None


class BlobMediaStore:
    """Uploads are staged as blocks and only committed once complete, so a rejected upload leaves no blob."""

    def __init__(self, container: Any, *, block_size: int = 4 * 1024 * 1024, credential: Any = None) -> None:
        self._container = container
        self._block_size = block_size
        self._credential = credential

    def _blob(self, name: str) -> Any:
        return self._container.get_blob_client(f"media/{name}")

    async def put(
        self, slot: MediaSlot, chunks: AsyncIterable[bytes], *, max_bytes: int, content_type: str
    ) -> StoredObject:
        blob = self._blob(MediaSlot(slot).value)
        digest = hashlib.sha256()
        total = 0
        block_ids: list[str] = []
        buffer = bytearray()

        async def stage(data: bytes) -> None:
            block_id = f"{len(block_ids):08d}"
            await blob.stage_block(block_id, data)
            block_ids.append(block_id)

        async for chunk in chunks:
            total += len(chunk)
            if total > max_bytes:
                raise MediaTooLarge(max_bytes)
            digest.update(chunk)
            buffer += chunk
            while len(buffer) >= self._block_size:
                await stage(bytes(buffer[: self._block_size]))
                del buffer[: self._block_size]
        if buffer:
            await stage(bytes(buffer))
        await blob.commit_block_list(block_ids, content_settings=ContentSettings(content_type=content_type))
        return StoredObject(bytes=total, sha256=digest.hexdigest())

    async def read(self, slot: MediaSlot, offset: int = 0, length: int | None = None) -> AsyncIterator[bytes]:
        downloader = await self._blob(MediaSlot(slot).value).download_blob(offset=offset, length=length)
        async for chunk in downloader.chunks():
            yield chunk

    async def size(self, slot: MediaSlot) -> int | None:
        try:
            props = await self._blob(MediaSlot(slot).value).get_blob_properties()
        except ResourceNotFoundError:
            return None
        return int(props.size)

    async def delete(self, slot: MediaSlot) -> None:
        with contextlib.suppress(ResourceNotFoundError):
            await self._blob(MediaSlot(slot).value).delete_blob()

    async def load_state(self) -> MediaState:
        try:
            downloader = await self._blob("state.json").download_blob()
        except ResourceNotFoundError:
            return MediaState()
        return MediaState.model_validate_json(await downloader.readall())

    async def save_state(self, state: MediaState) -> None:
        await self._blob("state.json").upload_blob(
            state.model_dump_json(indent=2).encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json"),
        )

    async def aclose(self) -> None:
        await self._container.close()
        if self._credential is not None:
            await self._credential.close()


ContainerFactory = Callable[[str], Any]


def build_media_store(settings: Settings, *, container_factory: ContainerFactory | None = None) -> MediaStore:
    if settings.artifact_store == "local":
        return LocalMediaStore(settings.data_dir / "media")
    account_url = settings.azure_storage_account_url
    if not account_url:
        raise ValueError("AZURE_STORAGE_ACCOUNT_URL is required when TACTISTREAM_ARTIFACT_STORE=blob")
    if container_factory is not None:
        return BlobMediaStore(container_factory(account_url))
    from azure.identity.aio import DefaultAzureCredential
    from azure.storage.blob.aio import ContainerClient

    credential = DefaultAzureCredential()
    return BlobMediaStore(
        ContainerClient(account_url, ARTIFACTS_CONTAINER, credential=credential), credential=credential
    )
