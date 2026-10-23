"""Signed artefacts sent to the store agent (33 §9.4): task-envelope claims, task keyset, update manifest.

Pure Python — the claim/payload shapes only; signing lives in ``application/jws.py``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from app.modules.onec_integration.domain.versions import parse_version

TASK_ISSUER: Final = "urn:erp:onec"
TASK_TYP: Final = "onec-task+jwt"
KEYSET_TYP: Final = "onec-task-keyset+jwt"
ALG: Final = "EdDSA"
TASK_EXP_MARGIN_S: Final = 300  # exp = leased_at + timeout_s + 300 (33 §9.4)
KEYSET_TTL_S: Final = 180 * 86400  # keyset exp = iat + 180 days
MANIFEST_PRODUCT: Final = "erp-onec-agent"
CHANNELS: Final = ("stable", "pilot")


def task_audience(agent_id: UUID) -> str:
    return f"urn:erp:onec-agent:{agent_id}"


@dataclass(frozen=True, slots=True)
class LeaseFacts:
    task_id: UUID
    attempt: int
    lease_id: UUID
    tenant_id: UUID
    agent_id: UUID
    base_id: UUID | None
    kind: str
    payload_sha256: str
    leased_at: datetime
    timeout_s: int


def task_claims(f: LeaseFacts) -> dict[str, Any]:
    iat = int(f.leased_at.timestamp())
    return {
        "iss": TASK_ISSUER,
        "aud": task_audience(f.agent_id),
        "tid": str(f.task_id),
        "att": f.attempt,
        "lid": str(f.lease_id),
        "ten": str(f.tenant_id),
        "aid": str(f.agent_id),
        "bid": str(f.base_id) if f.base_id is not None else None,
        "knd": f.kind,
        "psh": f.payload_sha256,
        "iat": iat,
        "exp": iat + f.timeout_s + TASK_EXP_MARGIN_S,
    }


def keyset_payload(version: int, iat: int, keys: list[dict[str, Any]]) -> dict[str, Any]:
    return {"ver": version, "iat": iat, "exp": iat + KEYSET_TTL_S, "keys": keys}


class ManifestError(ValueError):
    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field


_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_OS: Final = re.compile(r"^\d{1,3}\.\d{1,3}(\.\d{1,6})?$")


def validate_manifest(data: Mapping[str, Any]) -> dict[str, Any]:
    """33 §9.3 A-09 manifest members (what the agent checks, 34 §4.4) — refused before it is signed."""
    required = (
        "product",
        "version",
        "channel",
        "url",
        "sha256",
        "size",
        "min_os",
        "min_protocol",
        "rollout_pct",
        "released_at",
    )
    for name in required:
        if name not in data:
            raise ManifestError(name)
    if data["product"] != MANIFEST_PRODUCT:
        raise ManifestError("product")
    if parse_version(str(data["version"])) is None:
        raise ManifestError("version")
    if data["channel"] not in CHANNELS:
        raise ManifestError("channel")
    url = data["url"]
    if not isinstance(url, str) or not url.startswith("https://") or "@" in url.split("/", 3)[2]:
        raise ManifestError("url")
    if not isinstance(data["sha256"], str) or not _SHA256.fullmatch(data["sha256"]):
        raise ManifestError("sha256")
    for name, low, high in (("size", 1, 2**31), ("min_protocol", 1, 100), ("rollout_pct", 0, 100)):
        value = data[name]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ManifestError(name)
    if not isinstance(data["min_os"], str) or not _OS.fullmatch(data["min_os"]):
        raise ManifestError("min_os")
    if not isinstance(data["released_at"], str):
        raise ManifestError("released_at")
    return dict(data)
