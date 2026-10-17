/** WEB-07: «Saqlash va yuborish» — a refused send keeps the created draft (real `saveOrderFx`, API mocked). */
import { allSettled, fork } from "effector";
import { describe, expect, it, vi } from "vitest";

import type * as ApiModule from "@shared/api";

import { ApiError } from "@shared/api";
import type { PoOut } from "@shared/models";

const { createPurchaseOrder, sendPurchaseOrder } = vi.hoisted(() => ({
  createPurchaseOrder: vi.fn<(body: unknown) => Promise<PoOut>>(),
  sendPurchaseOrder: vi.fn<(id: string, body: unknown) => Promise<PoOut>>(),
}));

vi.mock("@shared/api", async (importOriginal) => {
  const actual = await importOriginal<typeof ApiModule>();
  return {
    ...actual,
    api: {
      ...actual.api,
      purchasing: { ...actual.api.purchasing, createPurchaseOrder, sendPurchaseOrder },
    },
  };
});

const { $actionError, $detail, $orders, $selectedId, getSupplierDebtFx, listOrdersFx, saveOrderFx } =
  await import("./index.ts");

const draft: PoOut = {
  id: "o-new",
  number: null,
  status: "draft",
  doc_date: "2026-10-14",
  branch_id: "b-1",
  warehouse_id: "w-1",
  supplier_id: "s-1",
  supplier: { id: "s-1", name: "Barakali Don", stir: null },
  comment: null,
  total: null,
  line_count: 1,
  created_by: "u-1",
  created_by_name: null,
  created_at: "",
  updated_at: "",
  sent_at: null,
  cancelled_at: null,
  cancel_reason: null,
  lines: [],
  received_lines: [],
};

describe("save + send (WEB-07)", () => {
  it("create ok, send refused → the draft is selected with the error; one create call", async () => {
    createPurchaseOrder.mockResolvedValue(draft);
    sendPurchaseOrder.mockRejectedValue(
      new ApiError({ status: 409, code: "DOC_INVALID_STATE", messageKey: "errors.doc_invalid_state" }),
    );
    const s = fork({
      handlers: [
        [listOrdersFx, () => ({ items: [], next_cursor: null })],
        [getSupplierDebtFx, () => ({ payable: "0.00", receivable: "0.00" })],
      ],
    });
    const result = await allSettled(saveOrderFx, {
      scope: s,
      params: {
        id: null,
        send: true,
        body: { supplier_id: "s-1", warehouse_id: "w-1", doc_date: "2026-10-14", lines: [], comment: null },
      },
    });
    expect(result.status).toBe("done");
    expect(createPurchaseOrder).toHaveBeenCalledTimes(1);
    expect(sendPurchaseOrder).toHaveBeenCalledTimes(1);
    expect(s.getState($selectedId)).toBe("o-new");
    expect(s.getState($detail)?.status).toBe("draft");
    expect(s.getState($orders).map((o) => o.id)).toEqual(["o-new"]);
    expect(s.getState($actionError)?.code).toBe("DOC_INVALID_STATE");
  });
});
