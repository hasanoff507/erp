"""Filesystem ``FileStoragePort`` — ``attachments.s3_key`` relative to ``ERP_FILE_STORAGE_DIR``.

Stop-gap until the S3 (``aioboto3``) StoragePort of 23 §7 lands: API and worker
must share the directory (a volume). Keys never leave the base directory.
"""

from __future__ import annotations

import asyncio
from pathlib import Path


class FilesystemStorage:
    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir).resolve()

    def _path(self, key: str) -> Path:
        path = (self._base / key).resolve()
        if not path.is_relative_to(self._base):
            raise ValueError(f"storage key escapes the base directory: {key!r}")
        return path

    async def put(self, key: str, content: bytes, content_type: str) -> None:
        path = self._path(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(content)
            tmp.replace(path)

        await asyncio.to_thread(write)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path(key).read_bytes)
