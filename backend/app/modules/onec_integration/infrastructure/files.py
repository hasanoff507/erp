"""Diagnostics packages (A-07) on the shared file volume (``ERP_FILE_STORAGE_DIR``), the key space of the
attachments module (``tenants/{tenant}/attachments/{id}.zip``) until the S3 ``StoragePort`` (23 §7) lands."""

from __future__ import annotations

import asyncio
from pathlib import Path


class FilesystemDiagnosticsFiles:
    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir).resolve()

    async def put(self, key: str, content: bytes) -> None:
        path = (self._base / key).resolve()
        if not path.is_relative_to(self._base):
            raise ValueError(f"storage key escapes the base directory: {key!r}")

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(content)
            tmp.replace(path)

        await asyncio.to_thread(write)
