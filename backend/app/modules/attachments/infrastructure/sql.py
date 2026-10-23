"""``app.attachments`` SQL (12 §2.6, 0018) and the filesystem file store (``ERP_FILE_STORAGE_DIR``).

The store mirrors the import files' stop-gap (same base directory and ``tenants/{tenant}/…`` key space)
until the S3 ``StoragePort`` of 23 §7 lands; keys never leave the base directory.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attachments.application.service import AttachmentRow


class SqlAttachmentRepository:
    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.attachments (id, tenant_id, s3_key, content_type, original_name, sha256, "
                "kind, size_bytes, uploaded_by) VALUES (:id, :tenant_id, :s3_key, :content_type, "
                ":original_name, :sha256, :kind, :size_bytes, :uploaded_by)"
            ),
            dict(row),
        )

    async def get(self, s: AsyncSession, attachment_id: UUID) -> AttachmentRow | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, s3_key, content_type, original_name, kind, size_bytes, uploaded_by, "
                    "created_at FROM app.attachments WHERE id = :id"
                ),
                {"id": attachment_id},
            )
        ).first()
        if row is None:
            return None
        return AttachmentRow(row[0], row[1], row[2], row[3], row[4], int(row[5]), row[6], row[7])

    async def bank_statement_ref(self, s: AsyncSession, attachment_id: UUID) -> bool:
        """SEC-02: the file is a bank statement (``bank_statement_imports.attachment_id``)."""
        found = await s.execute(
            text("SELECT 1 FROM app.bank_statement_imports WHERE attachment_id = :id LIMIT 1"),
            {"id": attachment_id},
        )
        return found.first() is not None


class FilesystemFileStore:
    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir).resolve()

    def _path(self, key: str) -> Path:
        path = (self._base / key).resolve()
        if not path.is_relative_to(self._base):
            raise ValueError(f"storage key escapes the base directory: {key!r}")
        return path

    async def put(self, key: str, content: bytes, content_type: str) -> None:
        del content_type
        path = self._path(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(content)
            tmp.replace(path)

        await asyncio.to_thread(write)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path(key).read_bytes)
