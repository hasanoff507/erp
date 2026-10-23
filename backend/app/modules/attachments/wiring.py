"""Composition of the attachments module (17 §12 ``/attachments``)."""

from __future__ import annotations

import hashlib

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.attachments.application.service import AttachmentService
from app.modules.attachments.domain.rules import UPLOAD_LIMIT
from app.modules.attachments.infrastructure.sql import FilesystemFileStore, SqlAttachmentRepository

__all__ = ["UPLOAD_LIMIT", "AttachmentService", "build_attachments"]


def build_attachments(settings: Settings, db: Database) -> AttachmentService:
    # domain-separated key derived from the server secret (signed download URLs, 15 min)
    secret = settings.auth_secret.get_secret_value().encode()
    url_key = hashlib.sha256(b"erp-attachment-url:" + secret).digest()
    return AttachmentService(
        db.session_factory,
        SqlAttachmentRepository(),
        FilesystemFileStore(settings.file_storage_dir),
        url_key,
        settings.api_prefix,
    )
