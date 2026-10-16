"""Declarative base and shared mixins (23 §1).

``TenantMixin`` models get an automatic ``tenant_id`` filter on every ORM
select (application layer of the two-layer isolation, 32 §4.2). PostgreSQL RLS
is the second, independent layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import uuid_utils
from sqlalchemy import MetaData, event, false, func
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    ORMExecuteState,
    Session,
    declared_attr,
    mapped_column,
    with_loader_criteria,
)
from sqlalchemy.types import TIMESTAMP

from app.core.db.session import TENANT_KEY

SKIP_TENANT_FILTER = "skip_tenant_filter"


def uuid7() -> UUID:
    """Application-side UUIDv7 (12 §1.2): ids are generated before INSERT."""
    return UUID(str(uuid_utils.uuid7()))


class Base(DeclarativeBase):
    metadata = MetaData(schema="app")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class TenantMixin:
    @declared_attr
    def tenant_id(cls) -> Mapped[UUID]:  # noqa: N805
        return mapped_column(nullable=False, index=False)


@event.listens_for(Session, "do_orm_execute")
def _add_tenant_criteria(state: ORMExecuteState) -> None:
    if not state.is_select or state.execution_options.get(SKIP_TENANT_FILTER, False):
        return
    tenant_id: Any = state.session.info.get(TENANT_KEY)
    if isinstance(tenant_id, UUID):
        criteria = with_loader_criteria(
            TenantMixin,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    else:
        # no tenant context: same answer RLS gives — nothing
        criteria = with_loader_criteria(TenantMixin, lambda cls: false(), include_aliases=True)
    state.statement = state.statement.options(criteria)
