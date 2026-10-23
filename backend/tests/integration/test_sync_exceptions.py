"""BO-14 «Sinxron istisnolari» — ``GET /sync-exceptions``, ``POST /sync-exceptions/{id}/review``
(20 #40f/#40g, 16 §5, qaror #56): permission ``settings.tenant`` or ``accounting.post``, branch scope,
filters, cursor, review once (``409 DOC_INVALID_STATE``), audit; ``Idempotency-Key`` on review."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.modules.access.domain.permissions import SystemRole
from app.modules.sync.application.handlers import SyncExceptionRow
from tests.support.catalog import Shop
from tests.support.inventory import add_branch, add_user
from tests.support.sync import (
    EXCEPTIONS,
    Pos,
    SyncEnv,
    echo_handler,
    event,
    pos_device,
    push_ok,
    register,
    rows,
    sync_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sync_env_fixture"]


async def _seed(env: SyncEnv, shop_name: str) -> tuple[Shop, Pos, tuple[Pos, UUID]]:
    shop = await env.shop(shop_name, SystemRole.OWNER, SystemRole.ACCOUNTANT, SystemRole.CASHIER)
    branch2, _ = await add_branch(env, shop, "02", "Ikkinchi")
    here = await pos_device(env, shop)
    there = await pos_device(env, shop, branch_id=branch2)
    register(
        env, "test.flagged",
        echo_handler(exceptions=(SyncExceptionRow("price_mismatch", {"expected": "1.00", "got": "2.00"}, "sales", uuid7()),)),
    )  # fmt: skip
    for pos in (here, there, here):
        [res] = await push_ok(env, pos, [event(pos, "test.flagged", {})])
        assert res["status"] == "accepted", res
    return shop, here, (there, branch2)


async def test_list_review_and_permissions(env: SyncEnv) -> None:
    shop, here, (there, branch2) = await _seed(env, "sync-exc")
    listed = await env.client.get(EXCEPTIONS, headers=shop.h("accountant", key=None))
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert len(items) == 3 and listed.json()["next_cursor"] is None
    first = items[0]
    assert first["kind"] == "price_mismatch" and first["doc_type"] == "sales" and first["reviewed_at"] is None
    assert {i["branch_id"] for i in items} == {str(here.branch_id), str(branch2)}
    assert items[0]["created_at"] >= items[-1]["created_at"]  # newest first

    # cashier has neither settings.tenant nor accounting.post
    denied = await env.client.get(EXCEPTIONS, headers=shop.h("cashier", key=None))
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "PERMISSION_DENIED"

    # cursor paging + filters
    page1 = (await env.client.get(EXCEPTIONS, params={"limit": 2}, headers=shop.h(key=None))).json()
    page2 = (
        await env.client.get(
            EXCEPTIONS, params={"limit": 2, "cursor": page1["next_cursor"]}, headers=shop.h(key=None)
        )
    ).json()
    assert len(page1["items"]) == 2 and len(page2["items"]) == 1 and page2["next_cursor"] is None
    assert {i["id"] for i in page1["items"] + page2["items"]} == {i["id"] for i in items}
    only_there = (
        await env.client.get(EXCEPTIONS, params={"device_id": str(there.device_id)}, headers=shop.h(key=None))
    ).json()["items"]
    assert [i["device_id"] for i in only_there] == [str(there.device_id)]
    by_branch = (
        await env.client.get(EXCEPTIONS, params={"branch_id": str(branch2)}, headers=shop.h(key=None))
    ).json()["items"]
    assert len(by_branch) == 1

    # review: note required, once only, audited
    url = f"{EXCEPTIONS}/{first['id']}/review"
    empty = await env.client.post(url, json={"review_note": "  "}, headers=shop.h("accountant"))
    assert empty.status_code == 422
    no_key = await env.client.post(url, json={"review_note": "Ok"}, headers=shop.h("accountant", key=None))
    assert no_key.status_code == 422  # Idempotency-Key is mandatory (20 #40g)
    done = await env.client.post(url, json={"review_note": "Narx tekshirildi"}, headers=shop.h("accountant"))
    assert done.status_code == 200, done.text
    body = done.json()
    accountant = shop.user_ids["accountant"]
    assert (body["id"], body["reviewed_by"], body["review_note"]) == (
        first["id"],
        str(accountant),
        "Narx tekshirildi",
    )
    again = await env.client.post(url, json={"review_note": "Yana"}, headers=shop.h("accountant"))
    assert again.status_code == 409 and again.json()["error"]["code"] == "DOC_INVALID_STATE"
    reviewed = (
        await env.client.get(EXCEPTIONS, params={"reviewed": "true"}, headers=shop.h(key=None))
    ).json()["items"]
    assert [i["id"] for i in reviewed] == [first["id"]]
    open_ = (await env.client.get(EXCEPTIONS, params={"reviewed": "false"}, headers=shop.h(key=None))).json()[
        "items"
    ]
    assert len(open_) == 2
    audit = await rows(
        env.db, shop.tenant_id,
        "SELECT user_id, after FROM app.audit_log WHERE action = 'sync_exception.reviewed' AND entity_id = :i",
        i=UUID(first["id"]),
    )  # fmt: skip
    assert [(a["user_id"], a["after"]["review_note"]) for a in audit] == [(accountant, "Narx tekshirildi")]
    missing = await env.client.post(
        f"{EXCEPTIONS}/{uuid7()}/review", json={"review_note": "x"}, headers=shop.h("accountant")
    )
    assert missing.status_code == 404


async def test_branch_restricted_user_sees_only_own_branch(env: SyncEnv) -> None:
    shop, here, (_, branch2) = await _seed(env, "sync-exc-branch")
    await add_user(env, shop, "branch_acc", SystemRole.ACCOUNTANT, branch_ids=(branch2,))
    items = (await env.client.get(EXCEPTIONS, headers=shop.h("branch_acc", key=None))).json()["items"]
    assert [i["branch_id"] for i in items] == [str(branch2)]
    foreign = await env.client.get(
        EXCEPTIONS, params={"branch_id": str(here.branch_id)}, headers=shop.h("branch_acc", key=None)
    )
    assert foreign.status_code == 403
    mine_hidden = [i for i in (await env.client.get(EXCEPTIONS, headers=shop.h(key=None))).json()["items"]
                   if i["branch_id"] == str(here.branch_id)]  # fmt: skip
    review = await env.client.post(
        f"{EXCEPTIONS}/{mine_hidden[0]['id']}/review", json={"review_note": "x"}, headers=shop.h("branch_acc")
    )
    assert review.status_code == 404  # not visible outside the user's branches
