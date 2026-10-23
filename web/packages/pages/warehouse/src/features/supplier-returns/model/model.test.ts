import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";

import {
  $actionError,
  $createOpen,
  $detail,
  $detailError,
  $receipt,
  $returns,
  createReturnFx,
  getReturnFx,
  listReturnsFx,
  loadReceiptFx,
  postReturnFx,
  receiptChosen,
  receiptSearch,
  returnLineError,
  returnSelected,
  returnableLines,
  returnsOpened,
  searchPostedReceiptsFx,
  toReturnBody,
  type Receipt,
  type SupplierReturn,
} from "./index.ts";

const line = (id: string, lotLeft: string | null) => ({
  id,
  line_no: 1,
  product_id: `p-${id}`,
  product_name: `Tovar ${id}`,
  unit_code: "pcs",
  qty: "10.000",
  cost: "1000.0000",
  vat_rate: "12.00",
  vat_exemption_code: null,
  vat_amount: "1200.00",
  net_amount: "10000.00",
  total_amount: "11200.00",
  expiry_date: null,
  discrepancy_reason: null,
  is_marked: false,
  marking_codes: [],
  lot_id: lotLeft === null ? null : `lot-${id}`,
  lot_qty_left: lotLeft,
  returned_qty: "0.000",
});

const receipt = {
  id: "r-1",
  lines: [line("1", "4.000"), line("2", "0.000"), line("3", null)],
} as unknown as Receipt;

const ret = (patch: Partial<SupplierReturn> = {}): SupplierReturn =>
  ({ id: "sr-1", status: "draft", number: null, lines: [], ...patch }) as SupplierReturn;

describe("Qaytarish model (19 §12, US-M07-05)", () => {
  it("«Qaytarish» from a receipt opens the sheet with its lots; a 12-month refusal is kept", async () => {
    const s = fork({
      handlers: [
        [listReturnsFx, () => ({ items: [], next_cursor: null })],
        [loadReceiptFx, () => receipt],
        [createReturnFx, () => ret()],
        [getReturnFx, () => ret()],
        [
          postReturnFx,
          () => {
            throw new ApiError({
              status: 409,
              code: "DOC_INVALID_STATE",
              messageKey: "errors.doc_invalid_state",
              params: { reason: "reverse_sale_required", receipt_doc_date: "2025-09-01" },
            });
          },
        ],
      ],
    });
    await allSettled(returnsOpened, { scope: s });
    expect(s.getState($returns)).toEqual([]);
    await allSettled(receiptChosen, { scope: s, params: "r-1" });
    expect(s.getState($createOpen)).toBe(true);
    expect(s.getState($receipt)?.id).toBe("r-1");
    await allSettled(createReturnFx, {
      scope: s,
      params: toReturnBody(receipt, { "1": "2" }, "damaged", "2026-10-16", ""),
    });
    expect(s.getState($createOpen)).toBe(false);
    await allSettled(returnSelected, { scope: s, params: "sr-1" });
    await allSettled(postReturnFx, { scope: s, params: "sr-1" });
    expect(s.getState($actionError)?.params.reason).toBe("reverse_sale_required");
  });
});

describe("Qaytarish — detail error and receipt picker (WEB-09, WEB-19)", () => {
  it("an unreadable return shows an error; selecting again clears it (WEB-09)", async () => {
    let fail = true;
    const s = fork({
      handlers: [
        [
          getReturnFx,
          () => {
            if (fail) throw new ApiError({ status: 404, code: "NOT_FOUND", messageKey: "errors.not_found" });
            return { id: "sr-1" } as SupplierReturn;
          },
        ],
      ],
    });
    await allSettled(returnSelected, { scope: s, params: "sr-1" });
    expect(s.getState($detail)).toBeNull();
    expect(s.getState($detailError)?.code).toBe("NOT_FOUND");
    fail = false;
    await allSettled(returnSelected, { scope: s, params: "sr-1" });
    expect(s.getState($detailError)).toBeNull();
    expect(s.getState($detail)?.id).toBe("sr-1");
  });

  it("typing in the receipt picker searches posted receipts with the query (WEB-19)", async () => {
    const queries: string[] = [];
    const s = fork({
      handlers: [
        [
          searchPostedReceiptsFx,
          (q: string) => {
            queries.push(q);
            return [];
          },
        ],
      ],
    });
    await allSettled(receiptSearch.queryChanged, { scope: s, params: "M-01" });
    expect(queries).toEqual(["M-01"]);
    expect(s.getState(receiptSearch.$query)).toBe("M-01");
  });
});

describe("returns lib", () => {
  it("only lots with something left; qty ≤ lot qty_left", () => {
    expect(returnableLines(receipt).map((l) => l.id)).toEqual(["1"]);
    expect(returnLineError("4", "4.000")).toBeNull();
    expect(returnLineError("4.001", "4.000")).toBe("range");
    expect(returnLineError("", "4.000")).toBeNull();
    expect(toReturnBody(receipt, { "1": "2", "2": "1" }, "expired", "2026-10-16", " x ")).toEqual({
      receipt_id: "r-1",
      doc_date: "2026-10-16",
      reason: "expired",
      comment: "x",
      lines: [{ receipt_line_id: "1", lot_id: "lot-1", qty: "2.000" }],
    });
  });
});
