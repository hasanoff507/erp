"""RS dependencies on real tokens: require_permission + limit, branch scope (15 §2.4, QT-PERM-08/09 shape)."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

import pytest
from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.auth.dependencies import TenantSession
from app.core.db.base import uuid7
from app.core.db.session import Database
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.main import create_app
from app.modules.access.domain.permissions import SystemRole
from scripts.seed import seed_demo_tenant, seed_demo_user
from tests.conftest import MigratedDb
from tests.support.auth import PASSWORD, android_tokens, auth_settings, bearer, new_phone

pytestmark = [pytest.mark.db, pytest.mark.redis]

probe = APIRouter(prefix="/probe")


@probe.get("/withdraw")
async def withdraw(
    grant: Annotated[PermissionGrant, Depends(require_permission("cash.withdraw"))],
) -> dict[str, str]:
    return {"limit": str(grant.limit_value)}


@probe.get("/stock")
async def stock(
    _: Annotated[PermissionGrant, Depends(require_permission("stock.view"))],
    scope: Annotated[BranchScope, Depends(current_branch_scope)],
    session: TenantSession,
) -> dict[str, object]:
    tenant = (await session.execute(text("SELECT app.current_tenant_id()"))).scalar()
    return {"all": scope.unrestricted, "current": str(scope.current), "db_tenant": str(tenant)}


async def test_permission_limit_and_branch_scope(
    oauth_platform: None, app_db: Database, clean_redis: Redis, migrated_db: MigratedDb, redis_url: str
) -> None:
    import httpx

    tenant_id = uuid7()
    await seed_demo_tenant(app_db, tenant_id=tenant_id, name="Filialli", phone=new_phone())
    async with app_db.session_factory() as s, s.begin():
        await s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
        branch: UUID = (
            await s.execute(text("SELECT id FROM app.branches WHERE tenant_id = :t"), {"t": tenant_id})
        ).scalar_one()
    owner_phone, cashier_phone = new_phone(), new_phone()
    await seed_demo_user(app_db, tenant_id=tenant_id, phone=owner_phone, name="Egasi", password=PASSWORD)
    await seed_demo_user(
        app_db, tenant_id=tenant_id, phone=cashier_phone, name="Kassir", password=PASSWORD,
        role=SystemRole.CASHIER, branch_ids=(branch,),
    )  # fmt: skip

    app = create_app(auth_settings(migrated_db, redis_url))
    app.include_router(probe, prefix="/api/v1")
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            owner = (await android_tokens(client, owner_phone))["access_token"]
            cashier = (await android_tokens(client, cashier_phone))["access_token"]
            # limit_value from role_permissions (qaror #23): cashier 50 000, owner unlimited
            r = await client.get("/api/v1/probe/withdraw", headers=bearer(cashier))
            assert Decimal(r.json()["limit"]) == Decimal("50000")
            assert (await client.get("/api/v1/probe/withdraw", headers=bearer(owner))).json()[
                "limit"
            ] == "None"
            other_branch = str(uuid7())
            denied = await client.get(
                "/api/v1/probe/stock", headers={**bearer(cashier), "X-Branch-Id": other_branch}
            )
            assert denied.status_code == 403 and denied.json()["error"]["code"] == "BRANCH_SCOPE_DENIED"
            own = await client.get(
                "/api/v1/probe/stock", headers={**bearer(cashier), "X-Branch-Id": str(branch)}
            )
            assert own.status_code == 200 and own.json()["all"] is False
            # tenant_transaction gets the tenant from the token, not from the request
            assert own.json()["db_tenant"] == str(tenant_id)
            anywhere = await client.get(
                "/api/v1/probe/stock", headers={**bearer(owner), "X-Branch-Id": other_branch}
            )
            assert anywhere.status_code == 200 and anywhere.json()["all"] is True
