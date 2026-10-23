"""``POST /sync/push`` pipeline (16 §2–§3, §8; 18 §2): envelope, device, dedupe, actor, retryable,
``outbox_state``, sync exceptions + M18 events, after-commit, drain. Document handlers are test-only
(registered through the real registry); inventory handlers are covered in ``test_sync_inventory``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.access.domain.permissions import SystemRole
from app.modules.sync.application.handlers import EventContext, HandlerResult, SyncExceptionRow
from app.modules.sync.application.push import EventIn, OutboxStateIn
from tests.support.auth import ISSUER, bearer, bff_login, csrf_token
from tests.support.inventory import new_product, set_method
from tests.support.inventory_docs import stock_in, two_branches
from tests.support.sync import (
    PUSH,
    SyncEnv,
    add_actor,
    echo_handler,
    event,
    execute,
    pos_device,
    push,
    push_ok,
    register,
    rows,
    scalar,
    sent_payload,
    sync_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sync_env_fixture"]

ECHO = "test.echo"


def err(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


async def test_qt_idemp_04_same_client_event_id_twice_one_document_second_duplicate(env: SyncEnv) -> None:
    """QT-IDEMP-04: the outbox resends E1 after a lost response → ``duplicate`` with the same number."""
    shop = await env.shop("QT-IDEMP-04")
    await set_method(env, shop, "fifo")
    src, _, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    await stock_in(env, shop, src, cola, "5.000", "5000.00")
    pos = await pos_device(env, shop)
    e1 = event(pos, "transfer.sent", sent_payload(src, dst, [(cola, "1.000")]))
    [first] = await push_ok(env, pos, [e1])
    assert first["status"] == "accepted", first
    again = dict(e1, seq=pos.next_seq())  # same client_event_id, resent later
    [second] = await push_ok(env, pos, [again])
    assert second["status"] == "duplicate"
    assert second["server"] == first["server"] and second["server"]["number"] == first["server"]["number"]
    assert (second["error_code"], second["retryable"], second["warnings"]) == (None, False, [])
    assert await scalar(env.db, shop.tenant_id, "SELECT count(*) FROM app.transfers") == 1
    receipts = await rows(env.db, shop.tenant_id, "SELECT device_id, result FROM app.sync_receipts")
    assert len(receipts) == 1 and receipts[0]["device_id"] == pos.device_id
    stored = receipts[0]["result"]
    assert (
        stored["status"] == "accepted"
        and stored["server"] == first["server"]
        and stored["type"] == "transfer.sent"
    )


async def test_push_envelope_is_validated_before_anything_runs(env: SyncEnv) -> None:
    shop = await env.shop("envelope")
    pos = await pos_device(env, shop)
    register(env, ECHO, echo_handler())
    ok_event = event(pos, ECHO, {})
    body: dict[str, Any] = {"device_id": str(pos.device_id), "events": [ok_event]}
    missing = await env.client.post(PUSH, json=body, headers=pos.h())  # outbox_state is required (16 §3.1)
    assert missing.status_code == 422 and err(missing) == "VALIDATION_ERROR"
    assert any(d["field"] == "outbox_state" for d in missing.json()["error"]["details"])
    bad_state = await push(env, pos, [ok_event], pending=0, oldest=datetime.now(UTC))
    assert bad_state.status_code == 422
    too_many = await push(env, pos, [event(pos, ECHO, {}) for _ in range(101)])
    assert too_many.status_code == 422
    assert too_many.json()["error"]["details"][0] == {
        "field": "events",
        "message_key": "validation.max_items",
    }
    a, b = event(pos, ECHO, {}, seq=10), event(pos, ECHO, {}, seq=10)
    order = await push(env, pos, [a, b])
    assert order.status_code == 422
    assert order.json()["error"]["details"][0] == {
        "field": "events[1].seq",
        "message_key": "validation.seq_not_increasing",
    }
    other = event(pos, ECHO, {}, seq=1)
    other["device_id"] = str(uuid7())
    assert (await push(env, pos, [other])).status_code == 422
    dup = event(pos, ECHO, {}, seq=1)
    assert (await push(env, pos, [dup, dict(dup, seq=2)])).status_code == 422
    assert (
        await scalar(env.db, shop.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'test.echo'")
        == 0
    )
    # body.device_id must be the token's device (14 §7)
    wrong = await env.client.post(
        PUSH,
        json={
            "device_id": str(uuid7()),
            "events": [],
            "outbox_state": {"pending_count": 0, "oldest_pending_created_at": None},
        },
        headers=pos.h(),
    )
    assert wrong.status_code == 403 and wrong.json()["error"]["params"] == {"reason": "device_mismatch"}


async def test_revoked_device_and_deviceless_token_are_refused(env: SyncEnv) -> None:
    """16 §9: ``403 DEVICE_REVOKED``; a session not bound to a device cannot push (14 §7)."""
    shop = await env.shop("revoked", SystemRole.OWNER)
    pos = await pos_device(env, shop)
    plain = await push(env, pos, [], headers=bearer(shop.tokens["owner"]))
    assert plain.status_code == 403 and plain.json()["error"]["params"] == {"reason": "device_required"}
    await execute(
        env.db, shop.tenant_id, "UPDATE app.devices SET revoked_at = now() WHERE id = :d", d=pos.device_id
    )
    await env.app.state.redis.flushdb()  # the RS device cache (positive answers are cached briefly)
    refused = await push(env, pos, [])
    assert refused.status_code == 403 and err(refused) == "DEVICE_REVOKED"


async def test_cookie_push_needs_csrf_and_a_device_bound_session(env: SyncEnv) -> None:
    """15 §1.3: cookie-authenticated ``/sync/push`` needs ``X-CSRF-Token``."""
    shop = await env.shop("csrf")
    pos = await pos_device(env, shop)
    transport = httpx.ASGITransport(app=env.app, client=("127.0.0.1", 50001))
    async with httpx.AsyncClient(transport=transport, base_url=ISSUER) as browser:
        await bff_login(browser, pos.phone)
        body = {"device_id": str(pos.device_id), "events": [], "outbox_state": {"pending_count": 0,
                "oldest_pending_created_at": None}}  # fmt: skip
        no_csrf = await browser.post(PUSH, json=body)
        assert no_csrf.status_code == 403 and err(no_csrf) == "CSRF_INVALID"
        token = await csrf_token(browser)
        with_csrf = await browser.post(PUSH, json=body, headers={"X-CSRF-Token": token})
        # a web session without device registration is not a POS session (b3-device binds it)
        assert with_csrf.status_code == 403 and err(with_csrf) == "PERMISSION_DENIED"


async def test_outbox_state_and_heartbeat_update_the_device_in_one_transaction(env: SyncEnv) -> None:
    """16 §3.1 / 33 §7.3: ``outbox_pending_count`` = reported + rejected now; oldest = min of both."""
    shop = await env.shop("outbox-state")
    pos = await pos_device(env, shop)
    heartbeat = await push_ok(env, pos, [])
    assert heartbeat == []
    dev = (await rows(env.db, shop.tenant_id, "SELECT * FROM app.devices WHERE id = :d", d=pos.device_id))[0]
    assert dev["last_sync_at"] is not None and dev["outbox_reported_at"] == dev["last_sync_at"]
    assert (dev["outbox_pending_count"], dev["outbox_oldest_pending_at"]) == (0, None)

    register(env, ECHO, echo_handler())
    oldest_unsent = datetime(2026, 10, 15, 8, 0, tzinfo=UTC)
    rejected_at = datetime.now(UTC) - timedelta(days=3)
    results = await push_ok(
        env, pos,
        [event(pos, ECHO, {}), event(pos, "no.such.event", {}, created_at=rejected_at),
         event(pos, "no.such.type", {})],
        pending=7, oldest=oldest_unsent,
    )  # fmt: skip
    assert [r["status"] for r in results] == ["accepted", "rejected", "rejected"]
    later = results[1]
    assert (later["error_code"], later["retryable"]) == ("VALIDATION_ERROR", False)
    assert later["details"] == [{"field": "type", "message_key": "validation.event_type_unknown"}]
    assert results[2]["details"] == [{"field": "type", "message_key": "validation.event_type_unknown"}]
    dev = (await rows(env.db, shop.tenant_id, "SELECT * FROM app.devices WHERE id = :d", d=pos.device_id))[0]
    assert dev["outbox_pending_count"] == 9  # 7 not sent + 2 rejected in this request
    assert dev["outbox_oldest_pending_at"] == rejected_at  # min(oldest unsent, rejected created_at)
    assert dev["last_seen_at"] == dev["last_sync_at"] == dev["outbox_reported_at"]


async def test_actor_membership_permission_and_audit(env: SyncEnv) -> None:
    """14 §4.3 / 16 §2: active membership at ``created_at``, branch, permission; actor ≠ session → audit."""
    shop = await env.shop("actor")
    await set_method(env, shop, "fifo")
    src, other_branch, dst = await two_branches(env, shop)
    cola = await new_product(env, shop)
    await stock_in(env, shop, src, cola, "10.000", "10000.00")
    pos = await pos_device(env, shop)
    cashier = await add_actor(env, pos, SystemRole.CASHIER)  # no transfer.create (15 §2.2)
    keeper = await add_actor(env, pos, SystemRole.STOREKEEPER)
    stranger = await add_actor(env, pos, SystemRole.STOREKEEPER, branch_ids=(other_branch,))
    blocked_early = await add_actor(env, pos, SystemRole.STOREKEEPER)
    blocked_late = await add_actor(env, pos, SystemRole.STOREKEEPER)
    await execute(env.db, shop.tenant_id, "UPDATE app.memberships SET status = 'blocked' WHERE user_id IN (:a, :b)",
                  a=blocked_early, b=blocked_late)  # fmt: skip
    past = datetime.now(UTC) - timedelta(hours=2)
    # blocked_early's event is made after the block (2 min ahead absorbs the test VM's DB clock offset)

    def sent(actor: UUID, at: datetime | None = None) -> dict[str, Any]:
        return event(
            pos, "transfer.sent", sent_payload(src, dst, [(cola, "1.000")]), actor=actor, created_at=at
        )

    results = await push_ok(
        env, pos,
        [sent(cashier), sent(stranger), sent(blocked_early, datetime.now(UTC) + timedelta(minutes=2)), sent(blocked_late, past), sent(keeper)],
    )  # fmt: skip
    assert [(r["status"], r["error_code"], r["params"].get("reason")) for r in results] == [
        ("rejected", "PERMISSION_DENIED", "permission"),
        ("rejected", "PERMISSION_DENIED", "actor_branch"),
        ("rejected", "PERMISSION_DENIED", "actor_inactive"),
        ("accepted", None, None),  # blocked after the event was made offline — the sale stands
        ("accepted", None, None),
    ]
    audit = await rows(
        env.db, shop.tenant_id,
        "SELECT user_id, device_id, after FROM app.audit_log WHERE action = 'sync.event_by_other_actor' ORDER BY (after->>'seq')::int",
    )  # fmt: skip
    assert [(a["user_id"], a["after"]["actor_user_id"]) for a in audit] == [
        (pos.user_id, str(blocked_late)), (pos.user_id, str(keeper)),
    ]  # fmt: skip
    assert all(a["device_id"] == pos.device_id for a in audit)


async def test_clock_skew_is_clamped_and_audited(env: SyncEnv) -> None:
    """16 §8: device clock +3 days → ``effective_created_at`` = received + 300 s; raw kept in the receipt."""
    shop = await env.shop("clock")
    pos = await pos_device(env, shop)
    register(env, ECHO, echo_handler())
    future = datetime.now(UTC) + timedelta(days=3)
    ancient = datetime.now(UTC) - timedelta(days=30)
    before = datetime.now(UTC)
    results = await push_ok(
        env, pos, [event(pos, ECHO, {}, created_at=future), event(pos, ECHO, {}, created_at=ancient)]
    )
    after = datetime.now(UTC)
    assert [r["status"] for r in results] == ["accepted", "accepted"]
    receipts = {
        r["result"]["seq"]: r["result"]
        for r in await rows(env.db, shop.tenant_id, "SELECT result FROM app.sync_receipts")
    }
    fut, old = receipts[1], receipts[2]
    assert fut["client_created_at"] == future.isoformat()
    effective = datetime.fromisoformat(fut["effective_created_at"])
    assert before + timedelta(seconds=299) <= effective <= after + timedelta(seconds=300)
    old_eff = datetime.fromisoformat(old["effective_created_at"])
    assert (
        before - timedelta(days=7, seconds=1) <= old_eff <= after - timedelta(days=7) + timedelta(seconds=1)
    )
    echoed = await rows(
        env.db,
        shop.tenant_id,
        "SELECT after FROM app.audit_log WHERE action = 'test.echo' ORDER BY (after->>'seq')::int",
    )
    assert (
        datetime.fromisoformat(echoed[0]["after"]["created_at"]) == effective
    )  # handlers see the effective time
    clamps = await scalar(
        env.db, shop.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'sync.clock_skew_clamped'"
    )
    assert clamps == 2


async def test_rejections_roll_back_and_are_retryable_only_for_dependencies(env: SyncEnv) -> None:
    """16 §3.4 / QT-NFR-12 (server half): a fault leaves nothing behind and the event stays retryable."""
    shop = await env.shop("retryable")
    pos = await pos_device(env, shop)
    calls: list[str] = []

    def failing(code: ErrorCode | None, exc: Exception | None = None) -> Any:
        inner = echo_handler()

        async def handler(s: Any, ctx: EventContext, payload: Any) -> HandlerResult:
            await inner(s, ctx, payload)  # writes, then fails → must be rolled back
            calls.append(ctx.event_type)
            if exc is not None:
                raise exc
            assert code is not None
            raise AppError(code, params={"entity": "shifts"})

        return handler

    register(env, "test.dep", failing(ErrorCode.DEPENDENCY_NOT_SYNCED))
    register(env, "test.bad", failing(ErrorCode.SHIFT_NOT_OPEN))
    register(env, "test.db", failing(None, OperationalError("SELECT 1", {}, Exception("server closed"))))
    register(env, ECHO, echo_handler())
    results = await push_ok(
        env,
        pos,
        [
            event(pos, "test.dep", {}),
            event(pos, "test.bad", {}),
            event(pos, "test.db", {}),
            event(pos, ECHO, {}),
        ],
    )
    assert [(r["status"], r["error_code"], r["retryable"]) for r in results] == [
        ("rejected", "DEPENDENCY_NOT_SYNCED", True),
        ("rejected", "SHIFT_NOT_OPEN", False),
        ("rejected", "INTERNAL_ERROR", True),
        ("accepted", None, False),  # an unrelated later event is not blocked (16 §3.3)
    ]
    assert results[0]["message"] == "errors.dependency_not_synced"
    assert len(calls) == 3
    assert (
        await scalar(env.db, shop.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'test.echo'")
        == 1
    )
    assert await scalar(env.db, shop.tenant_id, "SELECT count(*) FROM app.sync_receipts") == 1


async def test_handler_sync_exceptions_and_m18_events(env: SyncEnv) -> None:
    """16 §5 + B3-T18: rows inserted with the event; debt/approval kinds record a telegram event (not sent)."""
    shop = await env.shop("exceptions")
    pos = await pos_device(env, shop)
    doc_id = uuid7()
    register(
        env,
        ECHO,
        echo_handler(
            warnings=("DEBT_LIMIT_EXCEEDED",),
            exceptions=(
                SyncExceptionRow("debt_limit_exceeded_offline", {"limit": "500000.00"}, "sales", doc_id),
                SyncExceptionRow("approval_limit_exceeded_offline", {"kind": "discount"}, "sales", doc_id),
                SyncExceptionRow("price_mismatch", {"product_id": str(doc_id)}, "sales", doc_id),
            ),
        ),
    )
    e = event(pos, ECHO, {})
    [res] = await push_ok(env, pos, [e])
    assert res["status"] == "accepted" and res["warnings"] == ["DEBT_LIMIT_EXCEEDED"]
    found = await rows(
        env.db, shop.tenant_id,
        "SELECT kind, device_id, client_event_id, doc_type, doc_id, details FROM app.sync_exceptions ORDER BY kind",
    )  # fmt: skip
    assert [
        (f["kind"], f["device_id"], str(f["client_event_id"]), f["doc_type"], f["doc_id"]) for f in found
    ] == [
        ("approval_limit_exceeded_offline", pos.device_id, e["client_event_id"], "sales", doc_id),
        ("debt_limit_exceeded_offline", pos.device_id, e["client_event_id"], "sales", doc_id),
        ("price_mismatch", pos.device_id, e["client_event_id"], "sales", doc_id),
    ]
    jobs = await rows(
        env.db,
        shop.tenant_id,
        "SELECT status, payload FROM app.outbox_jobs WHERE kind = 'telegram' ORDER BY payload->>'event'",
    )
    assert [(j["status"], j["payload"]["event"], j["payload"]["kind"]) for j in jobs] == [
        ("queued", "debt_limit_exceeded_offline", "debt_limit_exceeded_offline"),
        ("queued", "over_limit_action", "approval_limit_exceeded_offline"),
    ]


async def test_after_commit_callbacks_run_after_commit_and_never_fail_the_event(env: SyncEnv) -> None:
    shop = await env.shop("after-commit")
    pos = await pos_device(env, shop)
    seen: list[int] = []

    async def handler(s: Any, ctx: EventContext, payload: Any) -> HandlerResult:
        async def visible() -> None:
            seen.append(await scalar(env.db, ctx.tenant_id, "SELECT count(*) FROM app.sync_receipts"))

        async def broken() -> None:
            raise RuntimeError("queue down")

        return HandlerResult(server={"ok": True}, after_commit=(visible, broken))

    register(env, ECHO, handler)
    [res] = await push_ok(env, pos, [event(pos, ECHO, {})])
    assert res["status"] == "accepted" and seen == [1]


async def test_sync_drain_token_only_drains_events_before_the_lockout(env: SyncEnv) -> None:
    """14 §16.4: ``sync.drain`` — events created before ``grace_ends_at`` only; audit started/completed."""
    shop = await env.shop("drain")
    pos = await pos_device(env, shop)
    register(env, ECHO, echo_handler())
    lockout = datetime.now(UTC) - timedelta(hours=1)
    updated = await scalar(
        env.db, shop.tenant_id,
        "WITH u AS (UPDATE app.subscriptions SET status = 'restricted', grace_ends_at = :g RETURNING 1) "
        "SELECT count(*) FROM u", g=lockout,
    )  # fmt: skip
    assert updated == 1
    drain = Principal(
        user_id=pos.user_id, tenant_id=shop.tenant_id, client_id="android-pos", scopes=frozenset({"sync.drain"}),
        roles=(), branch_ids=(), sid=None, device_id=pos.device_id, jti="t", issued_at=0, expires_at=0,
        sub_status="restricted", via_cookie=False,
    )  # fmt: skip

    def ev(at: datetime, seq: int) -> EventIn:
        return EventIn(uuid7(), pos.device_id, seq, ECHO, at, pos.user_id, {})

    out = await env.module.push.push(
        drain, pos.device_id, [ev(lockout - timedelta(hours=3), 1), ev(lockout + timedelta(minutes=5), 2)],
        OutboxStateIn(0, None),
    )  # fmt: skip
    assert [(r["status"], r["error_code"]) for r in out["results"]] == [
        ("accepted", None), ("rejected", "SUBSCRIPTION_RESTRICTED"),
    ]  # fmt: skip
    actions = await rows(
        env.db, shop.tenant_id, "SELECT action FROM app.audit_log WHERE action LIKE 'sync_drain%'"
    )
    assert [a["action"] for a in actions] == [
        "sync_drain_started"
    ]  # one event is still pending on the device
    out = await env.module.push.push(drain, pos.device_id, [], OutboxStateIn(0, None))
    actions = await rows(
        env.db,
        shop.tenant_id,
        "SELECT action FROM app.audit_log WHERE action LIKE 'sync_drain%' ORDER BY action DESC",
    )
    assert [a["action"] for a in actions] == ["sync_drain_started", "sync_drain_completed"]
    # a normal (non-drain) token of a restricted tenant gets 403 at the door
    await env.app.state.redis.flushdb()  # subscription status cache (14 §16.1)
    refused = await push(env, pos, [])
    assert refused.status_code == 403 and err(refused) == "SUBSCRIPTION_RESTRICTED"


async def test_sec_02_online_event_with_an_unbound_actor_is_flagged_not_rejected(env: SyncEnv) -> None:
    """SEC-02 / 15 §2.3a (founder F-6: detect-only): an online event naming another user needs that user's
    PIN binding on this device session; without it → accepted + ``actor_unverified`` + M18."""
    from sqlalchemy import text

    from app.modules.auth.application.actor import session_key

    shop = await env.shop("sec-02")
    pos = await pos_device(env, shop, SystemRole.CASHIER)
    owner = await add_actor(env, pos, SystemRole.OWNER)
    bound_cashier = await add_actor(env, pos, SystemRole.CASHIER)
    register(env, ECHO, echo_handler())
    assert env.admin is not None
    async with env.admin.connect() as conn:
        family = (
            await conn.execute(
                text("SELECT family_id FROM auth.refresh_tokens WHERE device_id = :d LIMIT 1"),
                {"d": pos.device_id},
            )
        ).scalar_one()
    key = session_key(None, family)
    assert key is not None
    await env.app.state.auth_module.actors.bind(pos.device_id, key, bound_cashier)  # POST /auth/pin/verify

    results = await push_ok(
        env, pos,
        [
            event(pos, ECHO, {"is_offline": False}, actor=owner),  # names the owner, never PIN-verified here
            event(pos, ECHO, {"is_offline": False}, actor=bound_cashier),  # PIN-bound → trusted
            event(pos, ECHO, {"is_offline": True}, actor=owner),  # offline: binding cannot be proven
            event(pos, ECHO, {"is_offline": False}),  # the session user itself
        ],
    )  # fmt: skip
    assert [r["status"] for r in results] == ["accepted"] * 4  # never rejected (the sale already happened)
    found = await rows(
        env.db, shop.tenant_id, "SELECT kind, client_event_id, details FROM app.sync_exceptions"
    )
    assert [(f["kind"], str(f["client_event_id"])) for f in found] == [
        ("actor_unverified", results[0]["client_event_id"])
    ]
    assert found[0]["details"]["actor_user_id"] == str(owner)
    assert found[0]["details"]["session_user_id"] == str(pos.user_id)
    jobs = await rows(env.db, shop.tenant_id, "SELECT payload FROM app.outbox_jobs WHERE kind = 'telegram'")
    assert [(j["payload"]["event"], j["payload"]["kind"]) for j in jobs] == [
        ("over_limit_action", "actor_unverified")
    ]


async def test_sec_02_handlers_get_a_binding_probe(env: SyncEnv) -> None:
    """``EventContext.actor_bound`` lets approval checks (``ApprovalGate``) verify an online approver."""
    shop = await env.shop("sec-02-probe")
    pos = await pos_device(env, shop)
    seen: list[bool] = []

    async def handler(s: Any, ctx: EventContext, payload: Any) -> HandlerResult:
        assert ctx.actor_bound is not None
        seen.append(await ctx.actor_bound(ctx.actor_user_id))
        return HandlerResult(server={"ok": True})

    register(env, ECHO, handler)
    [res] = await push_ok(env, pos, [event(pos, ECHO, {})])
    assert res["status"] == "accepted" and seen == [False]
