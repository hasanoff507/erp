"""Role / permission-set rules (20 #25–#28, 15 §2.1–§2.3). Pure Python."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from app.modules.access.domain.permissions import PERMISSIONS, LimitUnit, Permission

ROLE_NAME_MIN: Final = 1
ROLE_NAME_MAX: Final = 50
LIMIT_EXP: Final = Decimal("0.0001")  # role_permissions.limit_value NUMERIC(18,4), API 4 decimals (17 §3)
PERCENT_MAX: Final = Decimal("100")

TENANT_CATALOG: Final[dict[str, Permission]] = {p.code: p for p in PERMISSIONS if not p.platform_only}


@dataclass(frozen=True, slots=True)
class PermissionEntry:
    code: str
    limit_value: Decimal | None


@dataclass(frozen=True, slots=True)
class FieldProblem:
    field: str
    message_key: str


def normalize_limit(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(LIMIT_EXP)


def validate_permission_set(entries: list[PermissionEntry]) -> list[FieldProblem]:
    """Problems of a ``PUT /roles/{id}/permissions`` body (empty = valid).

    * code must be in the tenant catalog (``platform.admin`` is not a tenant permission);
    * a code may appear once;
    * "faqat Egasi" codes (15 §2.1) never go to another role — the owner role itself is immutable;
    * ``limit_value`` only on limit codes; unit per code (percent ≤ 100, so'm ≥ 0).
    """
    problems: list[FieldProblem] = []
    seen: set[str] = set()
    for i, entry in enumerate(entries):
        perm = TENANT_CATALOG.get(entry.code)
        if perm is None:
            problems.append(FieldProblem(f"permissions[{i}].code", "validation.unknown_permission"))
            continue
        if entry.code in seen:
            problems.append(FieldProblem(f"permissions[{i}].code", "validation.duplicate"))
        seen.add(entry.code)
        if perm.owner_only:
            problems.append(FieldProblem(f"permissions[{i}].code", "validation.owner_only_permission"))
        problems.extend(_limit_problems(i, perm, entry.limit_value))
    return problems


def _limit_problems(i: int, perm: Permission, limit: Decimal | None) -> list[FieldProblem]:
    field = f"permissions[{i}].limit_value"
    if limit is None:
        return []
    if perm.limit_unit is LimitUnit.NONE:
        return [FieldProblem(field, "validation.limit_not_allowed")]
    if limit < 0:
        return [FieldProblem(field, "validation.min_value")]
    if perm.limit_unit is LimitUnit.PERCENT and limit > PERCENT_MAX:
        return [FieldProblem(field, "validation.max_value")]
    return []
