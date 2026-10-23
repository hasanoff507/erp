/** BO-04 «Men qarzdorman» (US-M08-11, QT-M08-14 web half): payable aging → whom / how much / when, the book. */
import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import type { AgingRow, DebtsAgingOut } from "@shared/models";
import { $activeBranchId } from "@shared/state/session";

import {
  $payableLedger,
  $payables,
  $payablesSummary,
  byDue,
  dueState,
  loadPayableLedgerFx,
  loadPayablesFx,
  payableLedgerOpened,
  payablesOpened,
  totalOf,
} from "./index.ts";

function row(id: string, due: string | null, balance: string): AgingRow {
  return {
    counterparty_id: id,
    name: `Supplier ${id}`,
    phone: null,
    balance,
    credit_limit: null,
    due_date: due,
    overdue_since: "2026-10-01",
    days_overdue: 0,
    bucket: "0-30",
    promise_date: null,
    open_docs: 1,
    limit_exceeded_offline: false,
    doubtful_flag: false,
    doubtful_flag_id: null,
    last_payment_amount: null,
    last_payment_date: null,
  };
}

describe("payables (QT-M08-14)", () => {
  it("orders by «qachon to'lash» (earliest due first, no date last) and marks the due state", () => {
    const rows = [row("a", null, "5.00"), row("b", "2026-10-25", "1.00"), row("c", "2026-10-10", "2.00")];
    expect(byDue(rows).map((r) => r.counterparty_id)).toEqual(["c", "b", "a"]);
    expect(totalOf(rows)).toBe("8.00");
    expect(dueState("2026-10-10", "2026-10-18")).toBe("overdue");
    expect(dueState("2026-10-18", "2026-10-18")).toBe("today");
    expect(dueState("2026-10-24", "2026-10-18")).toBe("soon");
    expect(dueState("2026-11-30", "2026-10-18")).toBe("later");
    expect(dueState(null, "2026-10-18")).toBe("none");
  });

  it("reads the payable aging of the topbar branch and the supplier's payable book", async () => {
    const asked: (string | null)[] = [];
    const answer: DebtsAgingOut = {
      as_of: "2026-10-18",
      direction: "payable",
      summary: { total: "3000000.00", count: 2, buckets: [] },
      rows: [row("s-2", null, "600000.00"), row("s-1", "2026-10-20", "2400000.00")],
    };
    const ledgers: string[] = [];
    const s = fork({
      values: [[$activeBranchId, "b-1"]],
      handlers: [
        [
          loadPayablesFx,
          (branch: string | null) => {
            asked.push(branch);
            return answer;
          },
        ],
        [
          loadPayableLedgerFx,
          (id: string) => {
            ledgers.push(id);
            return {
              counterparty: { name: "S" },
              balance: "2400000.00",
              entries: [],
              next_cursor: null,
            } as never;
          },
        ],
      ],
    });
    await allSettled(payablesOpened, { scope: s });
    expect(s.getState($payables).map((r) => r.counterparty_id)).toEqual(["s-1", "s-2"]);
    expect(s.getState($payablesSummary)?.total).toBe("3000000.00");
    await allSettled(payableLedgerOpened, { scope: s, params: "s-1" });
    expect(ledgers).toEqual(["s-1"]);
    expect(s.getState($payableLedger)?.balance).toBe("2400000.00");
    expect(asked.length).toBe(1);
  });
});
