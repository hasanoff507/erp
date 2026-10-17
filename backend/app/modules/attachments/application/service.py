"""Attachments: ``POST /attachments``, ``GET /attachments/{id}`` and the signed download (17 §12).

The file is stored first (key ``tenants/{tenant}/attachments/{id}.{ext}``, same volume as import files),
then the ``attachments`` row is written in one tenant transaction with the audit row. Reads are tenant
scoped (RLS): another tenant's id is ``404``.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.modules.attachments.domain.rules import (
    BANK_STATEMENT_READ,
    CONTENT_TYPES,
    EXTENSIONS,
    MAX_BYTES,
    UPLOAD_PERMISSIONS,
    URL_TTL_S,
    matches_magic,
    normalize_type,
    signature_ok,
    url_signature,
)


@dataclass(frozen=True, slots=True)
class AttachmentRow:
    id: UUID
    s3_key: str
    content_type: str
    original_name: str | None
    kind: str
    size_bytes: int
    uploaded_by: UUID
    created_at: datetime


class AttachmentRepository(Protocol):
    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def get(self, s: AsyncSession, attachment_id: UUID) -> AttachmentRow | None: ...

    async def bank_statement_ref(self, s: AsyncSession, attachment_id: UUID) -> bool: ...


class FileStorage(Protocol):
    async def put(self, key: str, content: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...


def _unsupported(content_type: str, kind: str) -> AppError:
    return AppError(ErrorCode.UNSUPPORTED_FILE_TYPE, params={"content_type": content_type, "kind": kind})


class AttachmentService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: AttachmentRepository,
        storage: FileStorage,
        url_key: bytes,
        api_prefix: str,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._storage = storage
        self._key = url_key
        self._prefix = api_prefix

    @staticmethod
    def check_kind(kind: str) -> tuple[str, ...]:
        codes = UPLOAD_PERMISSIONS.get(kind)
        if codes is None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field="kind", message_key="validation.invalid_choice")],
            )
        return codes

    async def upload(
        self,
        actor: Principal,
        kind: str,
        filename: str | None,
        content_type: str | None,
        content: bytes,
        ip: str | None,
    ) -> dict[str, Any]:
        self.check_kind(kind)
        ctype = normalize_type(content_type)
        if ctype not in CONTENT_TYPES[kind]:
            raise _unsupported(ctype, kind)
        if len(content) > MAX_BYTES[ctype]:
            raise AppError(ErrorCode.FILE_TOO_LARGE, params={"max_bytes": MAX_BYTES[ctype]})
        if not content or not matches_magic(ctype, content):
            raise _unsupported(ctype, kind)
        attachment_id = uuid7()
        key = f"tenants/{actor.tenant_id}/attachments/{attachment_id}.{EXTENSIONS[ctype]}"
        await self._storage.put(key, content, ctype)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._repo.insert(
                s,
                {
                    "id": attachment_id,
                    "tenant_id": actor.tenant_id,
                    "s3_key": key,
                    "content_type": ctype,
                    "original_name": (filename or "")[:255] or None,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "kind": kind,
                    "size_bytes": len(content),
                    "uploaded_by": actor.user_id,
                },
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="attachment.uploaded",
                entity="attachments",
                entity_id=attachment_id,
                ip=ip,
                device_id=actor.device_id,
                after={"kind": kind, "content_type": ctype, "size_bytes": len(content)},
            )
            body = {
                "id": str(attachment_id),
                "url": self.signed_url(actor.tenant_id, attachment_id),
                "content_type": ctype,
                "size_bytes": len(content),
            }
            stage_response(body, 201)
        return body

    async def load(self, actor: Principal, attachment_id: UUID) -> AttachmentRow:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get(s, attachment_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "attachment"})
        return row

    async def read_permissions(self, actor: Principal, row: AttachmentRow) -> tuple[str, ...]:
        """Rights to read a file: its ``kind``'s upload rights; a bank statement (an ``import`` file
        referenced by ``bank_statement_imports``) only ``bank_settlements.manage`` (SEC-02, 17 §12)."""
        if row.kind == "import":
            async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
                if await self._repo.bank_statement_ref(s, row.id):
                    return BANK_STATEMENT_READ
        return UPLOAD_PERMISSIONS.get(row.kind, ())

    def describe(self, tenant_id: UUID, row: AttachmentRow) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "url": self.signed_url(tenant_id, row.id),
            "content_type": row.content_type,
            "original_name": row.original_name,
            "size_bytes": row.size_bytes,
            "kind": row.kind,
        }

    def signed_url(self, tenant_id: UUID, attachment_id: UUID, now: int | None = None) -> str:
        expires = (now if now is not None else int(time.time())) + URL_TTL_S
        sig = url_signature(self._key, str(tenant_id), str(attachment_id), expires)
        query = urlencode({"t": str(tenant_id), "exp": expires, "sig": sig})
        return f"{self._prefix}/attachments/{attachment_id}/content?{query}"

    async def content(
        self, tenant_id: UUID, attachment_id: UUID, expires: int, signature: str
    ) -> tuple[bytes, AttachmentRow]:
        if not signature_ok(
            self._key, str(tenant_id), str(attachment_id), expires, signature, int(time.time())
        ):
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "url_expired_or_invalid"})
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            row = await self._repo.get(s, attachment_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "attachment"})
        return await self._storage.get(row.s3_key), row
