"""Returns — fiscal/marking side owned by b5-fiscal (13 §2.5, qaror #48; 21 §4 write-off of marked goods)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.modules.accounting.wiring import business_today
from tests.support.inventory import receive
from tests.support.sales import (
    Env,
    deliver,
    make_pos,
    new_item,
    return_line,
    return_payload,
    rows,
    sale_line,
    sale_payload,
    sales_env_fixture,
    sell,
    sold_lines,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]

CODE = "0104600000000001215expiredrtn\x1d93AbCd"


async def test_qt_m02_07_expired_marked_return_write_off_carries_code(env: Env) -> None:
    pos = await make_pos(env, account="2910")
    product = await new_item(
        env, pos, "Hayot suvi 1.5L", is_marked=True, marking_group_code="water_beverages", stock=None
    )
    await receive(env, pos.shop, pos.warehouse_id, product, "3.000", "24000.00",
                  expiry=business_today() - timedelta(days=1))  # fmt: skip
    sale = sale_payload(pos, [sale_line(product, marking_code=CODE)])
    await sell(env, pos, sale, actor="owner")
    lines = await sold_lines(env, pos, sale["id"])
    approval = {
        "mode": "local_pin",
        "approved_by": str(pos.shop.user_ids["owner"]),
        "pin_verified_locally": True,
    }
    ret = return_payload(pos, [return_line(product, sale_line_id=lines[0]["id"], marking_code=CODE)],
                         sale_id=sale["id"], approval=approval)  # fmt: skip
    res = await deliver(env, pos, "return.created", ret, actor="owner")
    assert res.error is None, (res.code, res.keys)
    wo = await rows(env.db, pos.tenant_id,
                    "SELECT l.reason, l.marking_codes FROM app.write_offs w JOIN app.write_off_lines l "
                    "ON l.write_off_id = w.id WHERE w.source_return_id = :d", d=ret["id"])  # fmt: skip
    assert wo == [{"reason": "expired_return", "marking_codes": [CODE]}]
