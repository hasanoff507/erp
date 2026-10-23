"""CRPT notices of the marked goods flow (21 §4, 19 §8; qaror #62/#63; B5-T07, B5-DoD-08): M07 goods receipt
acceptance with the group deadline (QT-NFR-07 on an explicit clock), supplier return and write-off notices,
cancellations. Internal transfers send nothing — ``test_transfers.py::test_qt_m06_06_*``."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.errors import AppError
from app.modules.integrations.marking.domain.deadline import TASHKENT
from app.modules.integrations.marking.wiring import MarkedLine, marking_hooks
from tests.support.marking import (
    Clock,
    code,
    events,
    fake_crpt_fixture,
    jobs,
    marking_env_fixture,
    receive_marked,
    run_monitor,
    run_outbox,
)
from tests.support.sales import Env, Pos, make_pos, new_item, one, rows

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["fake_crpt_fixture", "marking_env_fixture"]


def t(day: str, hh: int = 0, mm: int = 0) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hh, minute=mm, tzinfo=TASHKENT)


async def _product(env: Env, pos: Pos, group: str, name: str) -> UUID:
    return await new_item(env, pos, name, is_marked=True, marking_group_code=group, stock=None)


async def _posted(env: Env, pos: Pos, receipt: dict[str, Any], doc_date: date, **kw: Any) -> UUID | None:
    """The hook b5-edocs calls in ``post`` (idempotent — a second call returns the same job)."""
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        return await marking_hooks().on_goods_receipt_posted(
            s,
            pos.tenant_id,
            UUID(receipt["id"]),
            doc_date=doc_date,
            actor_user_id=pos.shop.user_ids["owner"],
            **kw,
        )


async def _acceptance(env: Env, pos: Pos, receipt: dict[str, Any], now: datetime) -> Any:
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        return await marking_hooks().acceptance(s, UUID(receipt["id"]), now=now)


async def _call(env: Env, pos: Pos, method: str, doc_id: UUID, lines: list[MarkedLine]) -> Any:
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        hook = getattr(marking_hooks(), method)
        return await hook(s, pos.tenant_id, doc_id, lines=lines, actor_user_id=pos.shop.user_ids["owner"])


async def _posted_codes(env: Env, pos: Pos) -> None:
    """Acceptance of every posted receipt of the tenant (the purchasing ``post`` may have queued it already)."""
    for r in await rows(
        env.db, pos.tenant_id, "SELECT id, doc_date FROM app.goods_receipts WHERE status = 'posted'"
    ):
        await _posted(env, pos, {"id": str(r["id"])}, r["doc_date"])


async def _statuses(env: Env, pos: Pos, codes: list[str]) -> list[str]:
    found = await rows(env.db, pos.tenant_id, "SELECT code, status FROM app.marking_codes WHERE code = ANY(:c)",
                       c=codes)  # fmt: skip
    by = {r["code"]: r["status"] for r in found}
    return [by[c] for c in codes]


async def test_qt_nfr_07_acceptance_deadline_72h_fake_clock(env: Env, crpt: Any) -> None:
    """Water (72 h, VM 631): warning before the deadline, acceptance recorded inside it (B5-DoD-08)."""
    pos = await make_pos(env)
    water = await _product(env, pos, "water_beverages", "Hayot suvi 1.5L")
    codes = [code(), code()]
    day = date(2026, 3, 2)  # this test's own business day (Monday)
    receipt = await receive_marked(env, pos, water, codes, doc_date=day)
    job_id = await _posted(env, pos, receipt, day)
    assert job_id is not None and await _posted(env, pos, receipt, day) == job_id  # one job per receipt
    [job] = await jobs(env, pos.tenant_id, "marking_accept")
    assert job["payload"]["deadline_kind"] == "72_hours" and job["payload"]["codes"] == codes
    assert job["payload"]["due_at"] == "2026-03-04T19:00:00Z"  # 2026-03-05 00:00 Tashkent = 72 h
    crpt.fail = "transient"  # CRPT down on the receipt day
    out = await run_outbox(env, pos.tenant_id, Clock(t("2026-03-02", 10)))
    assert [o.status for o in out] == ["retry"]
    assert (await run_monitor(env, pos.tenant_id, t("2026-03-03", 12))).events == []  # 36 h left
    assert (await _acceptance(env, pos, receipt, t("2026-03-03", 12)))["status"] == "pending"
    soon = await run_monitor(env, pos.tenant_id, t("2026-03-04", 2))  # 22 h left → warning
    assert soon.events == [(receipt["id"], "due_soon")]
    assert (await run_monitor(env, pos.tenant_id, t("2026-03-04", 3))).events == []  # once per stage
    [alert] = await events(env, pos.tenant_id, "marking_acceptance_due")
    assert alert["stage"] == "due_soon" and alert["number"] == receipt["number"]
    assert alert["branch_id"] == str(pos.branch_id) and alert["deadline_kind"] == "72_hours"
    crpt.fail = None
    done = await run_outbox(env, pos.tenant_id, Clock(t("2026-03-04", 9)))
    assert [o.status for o in done] == ["done"] and ("accept", receipt["id"]) in crpt.calls
    [job] = await jobs(env, pos.tenant_id, "marking_accept")
    accepted = datetime.fromisoformat(job["payload"]["accepted_at"])
    assert accepted < datetime.fromisoformat(job["payload"]["due_at"])  # inside the 72 h window
    assert job["payload"]["crpt_doc_id"].startswith("FAKE-ACC-")
    verified = await rows(env.db, pos.tenant_id, "SELECT verified_at FROM app.marking_codes WHERE code = ANY(:c)",
                          c=codes)  # fmt: skip
    assert all(r["verified_at"] == accepted for r in verified)
    assert await _acceptance(env, pos, receipt, t("2026-03-06")) == {
        "status": "accepted", "due_at": "2026-03-04T19:00:00Z", "deadline_kind": "72_hours",
    }  # fmt: skip
    assert (await run_monitor(env, pos.tenant_id, t("2026-03-06"))).events == []  # accepted — no overdue


async def test_qt_nfr_07_acceptance_3_business_days_overdue_then_dead_letter(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)
    tv = await _product(env, pos, "general", "Televizor")
    day = date(2026, 3, 5)  # this test's own business day (Thursday); a weekend falls inside the window
    receipt = await receive_marked(env, pos, tv, [code()], doc_date=day, cost="3000000.0000")
    await _posted(env, pos, receipt, day)  # the purchasing post already queued it — idempotent
    [job] = await jobs(env, pos.tenant_id, "marking_accept")
    assert job["payload"]["deadline_kind"] == "3_business_days"
    assert job["payload"]["ownership_at"] == "2026-03-04T19:00:00Z"  # Thu 00:00 Tashkent
    assert job["payload"]["due_at"] == "2026-03-10T19:00:00Z"  # Thu → Fri, Mon, Tue → Wed 00:00
    crpt.fail = "transient"
    await run_outbox(env, pos.tenant_id, Clock(t("2026-03-06", 10)))
    assert (await run_monitor(env, pos.tenant_id, t("2026-03-09", 23))).events == []  # 25 h left
    late = await run_monitor(env, pos.tenant_id, t("2026-03-11", 1))
    assert late.events == [(receipt["id"], "overdue")]
    assert (await _acceptance(env, pos, receipt, t("2026-03-11", 1)))["status"] == "overdue"
    # still retried a day past the deadline, then a dead letter: failed + audit + M18 (21 §0)
    out = await run_outbox(env, pos.tenant_id, Clock(t("2026-03-12", 1)))
    assert [o.status for o in out] == ["failed"]
    assert (await jobs(env, pos.tenant_id, "marking_accept"))[0]["status"] == "failed"
    [alert] = await events(env, pos.tenant_id, "marking_alert")
    assert alert["reason"] == "crpt_rejected" and alert["job_kind"] == "marking_accept"
    assert (
        await one(
            env.db, pos.tenant_id, "SELECT count(*) FROM app.audit_log WHERE action = 'marking.accept_failed'"
        )
        == 1
    )


async def test_dod_08_rejected_codes_and_receipt_cancel_after_acceptance(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)
    water = await _product(env, pos, "water_beverages", "Hayot suvi 0.5L")
    bad = code()
    crpt.reject.add(bad)
    day = date(2026, 4, 1)
    first = await receive_marked(env, pos, water, [code(), bad], doc_date=day)
    await _posted(env, pos, first, day)
    out = await run_outbox(env, pos.tenant_id, Clock(t("2026-04-01", 12)))
    assert [o.status for o in out] == ["failed"]
    [alert] = await events(env, pos.tenant_id, "marking_alert")
    assert alert["codes"] == [bad]
    second = await receive_marked(env, pos, water, [code()], doc_date=day)
    await _posted(env, pos, second, day)
    assert [o.status for o in await run_outbox(env, pos.tenant_id, Clock(t("2026-04-01", 13)))] == ["done"]
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        await marking_hooks().on_goods_receipt_cancelled(s, pos.tenant_id, UUID(second["id"]))
    reasons = [a["reason"] for a in await events(env, pos.tenant_id, "marking_alert")]
    assert reasons == ["crpt_rejected", "accepted_receipt_cancelled"]
    third = await receive_marked(env, pos, water, [code()], doc_date=day)
    await _posted(env, pos, third, day)
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        await marking_hooks().on_goods_receipt_cancelled(s, pos.tenant_id, UUID(third["id"]))
    assert await _acceptance(env, pos, third, t("2026-04-02")) is None  # closed before CRPT saw it
    assert await run_outbox(env, pos.tenant_id) == []


async def test_marking_supplier_return_and_write_off_notices(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)
    water = await _product(env, pos, "water_beverages", "Hayot suvi 1L")
    other = await _product(env, pos, "general", "Sigaret")
    codes = [code() for _ in range(4)]
    day = date(2026, 5, 4)
    await receive_marked(env, pos, water, codes, doc_date=day)
    await _posted_codes(env, pos)
    await run_outbox(env, pos.tenant_id, Clock(t("2026-05-04", 11)))  # the receipt is accepted first
    ret_id, wo_id = uuid7(), uuid7()
    with pytest.raises(AppError) as err:  # qty ≠ number of codes
        await _call(
            env, pos, "on_supplier_return_posted", ret_id, [MarkedLine(0, water, Decimal("2"), (codes[0],))]
        )
    assert err.value.details[0].message_key == "validation.marking_count_mismatch"
    with pytest.raises(AppError) as err:  # another product's code
        await _call(
            env, pos, "on_supplier_return_posted", ret_id, [MarkedLine(1, other, Decimal("1"), (codes[0],))]
        )
    assert err.value.details[0].field == "lines[1].marking_codes"
    assert err.value.details[0].message_key == "validation.marking_code_not_in_stock"
    with pytest.raises(AppError) as err:
        await _call(env, pos, "on_supplier_return_posted", ret_id,
                    [MarkedLine(0, water, Decimal("2"), (codes[0], codes[0]))])  # fmt: skip
    assert err.value.details[0].message_key == "validation.marking_code_duplicate"
    job = await _call(
        env, pos, "on_supplier_return_posted", ret_id, [MarkedLine(0, water, Decimal("1"), (codes[0],))]
    )
    assert job is not None and await _statuses(env, pos, codes[:1]) == ["returned_to_supplier"]
    with pytest.raises(AppError):  # the code already left the stock
        await _call(env, pos, "on_write_off_posted", wo_id, [MarkedLine(0, water, Decimal("1"), (codes[0],))])
    crpt.reject.add(codes[2])
    await _call(
        env, pos, "on_write_off_posted", wo_id, [MarkedLine(0, water, Decimal("2"), (codes[1], codes[2]))]
    )
    assert await _statuses(env, pos, codes) == [
        "returned_to_supplier",
        "written_off",
        "written_off",
        "in_stock",
    ]
    out = {o.kind: o.status for o in await run_outbox(env, pos.tenant_id, Clock(t("2026-05-04", 12)))}
    assert out == {"marking_supplier_return": "done", "marking_writeoff": "failed"}
    assert ("supplier_return", str(ret_id)) in crpt.calls and ("write_off", str(wo_id)) in crpt.calls
    [alert] = await events(env, pos.tenant_id, "marking_alert")
    assert alert["job_kind"] == "marking_writeoff" and alert["codes"] == [codes[2]]
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.audit_log "
                     "WHERE action = 'marking.writeoff_failed'") == 1  # fmt: skip
    # cancelling a posted document: codes back in stock; an already confirmed notice → M18
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        await marking_hooks().on_codes_document_cancelled(s, pos.tenant_id, ret_id)
        await marking_hooks().on_codes_document_cancelled(s, pos.tenant_id, wo_id)
    assert await _statuses(env, pos, codes) == ["in_stock"] * 4
    reasons = [a["reason"] for a in await events(env, pos.tenant_id, "marking_alert")]
    assert reasons == ["crpt_rejected", "crpt_notice_cancelled"]
    assert await _call(env, pos, "on_write_off_posted", uuid7(), []) is None  # no marked lines → no job


async def test_contract_hooks_no_marked_codes_and_m18_kinds(env: Env, crpt: Any) -> None:
    from app.modules.notifications.domain.events import EVENT_KINDS
    from app.modules.notifications.domain.policy import AUDIENCE

    pos = await make_pos(env)
    assert await _posted(env, pos, {"id": str(uuid7())}, date(2026, 6, 1)) is None
    assert AUDIENCE["marking_alert"] == "reports.finance.view" and "marking_acceptance_due" in EVENT_KINDS
    assert AUDIENCE["marking_acceptance_due"] == "purchases.return"
