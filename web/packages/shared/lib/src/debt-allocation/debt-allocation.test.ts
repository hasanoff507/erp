import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { addMoney, type Money } from "#/money/index.ts";

import {
  allocateDebtPayment,
  allocationOrder,
  type DebtAllocationResult,
  type OpenDebtDoc,
} from "./index.ts";

/**
 * ONE shared vector file for backend (pytest tests/unit/test_debt_allocation.py) and web — 32 §6.3,
 * QT-M08-16: <repo>/shared/debt-allocation-vectors.json.
 */
interface VectorCase {
  name: string;
  amount: string;
  fiscal: boolean;
  open_docs: OpenDebtDoc[];
  expected: DebtAllocationResult;
}

const VECTORS_URL = new URL("../../../../../../shared/debt-allocation-vectors.json", import.meta.url);
const vectors = JSON.parse(readFileSync(VECTORS_URL, "utf-8")) as { cases: VectorCase[] };

describe("debt allocation — shared vectors (18 §12.2, qaror #67)", () => {
  it("has the vectors", () => {
    expect(vectors.cases.length).toBeGreaterThanOrEqual(10);
  });

  it.each(vectors.cases)("$name", (c) => {
    const got = allocateDebtPayment(c.amount, c.open_docs, { fiscal: c.fiscal });
    expect(got).toEqual(c.expected);
    const received = addMoney(got.unallocated_amount, ...got.allocations.map((a) => a.amount));
    expect(received).toBe(c.amount);
    if (c.fiscal) expect(addMoney(...got.fiscal_lines.map((l) => l.amount))).toBe(c.amount);
  });

  it("puts write-offs after every open debt", () => {
    const docs: OpenDebtDoc[] = [
      {
        doc_type: "debt_writeoffs",
        doc_id: "w",
        doc_date: "2020-01-01",
        due_date: null,
        open_amount: "10.00",
      },
      { doc_type: "debt_openings", doc_id: "o", doc_date: "2026-01-01", due_date: null, open_amount: "5.00" },
    ];
    expect(allocationOrder(docs).map((d) => d.doc_id)).toEqual(["o", "w"]);
  });

  it("ACC-10: three partial receipts of one line sum to exactly its qty", () => {
    let settled = "0.00" as Money;
    const qtys: string[] = [];
    for (let i = 0; i < 3; i += 1) {
      const line = {
        sale_line_id: "l1",
        product_id: null,
        qty: "1.000",
        line_total: "300.00",
        vat_rate: "12.00",
        settled_amount: settled,
        marking_code: null,
      };
      const open = ["300.00", "200.00", "100.00"][i] ?? "0.00";
      const doc: OpenDebtDoc = {
        doc_type: "sales",
        doc_id: "s",
        doc_date: "2026-10-01",
        due_date: null,
        open_amount: open,
        lines: [line],
      };
      const got = allocateDebtPayment("100.00", [doc]);
      const fl = got.fiscal_lines[0];
      qtys.push(fl?.qty ?? "");
      settled = addMoney(settled, fl?.amount ?? settled);
    }
    expect(qtys).toEqual(["0.333", "0.334", "0.333"]);
  });

  it("rejects a non-positive amount", () => {
    expect(() => allocateDebtPayment("0.00", [])).toThrow(RangeError);
  });
});
