import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";

import {
  $fiscalRequeued,
  $fiscalRetryError,
  $receipts,
  $registers,
  fiscalFilterChanged,
  fiscalOpened,
  fiscalRetryRequested,
  listReceiptsFx,
  listRegistersFx,
  registersByAttention,
  retryReceiptFx,
  type CashRegister,
  type FiscalReceipt,
} from "./index.ts";

function receipt(id: string, status: FiscalReceipt["status"]): FiscalReceipt {
  return {
    id,
    sale_id: "s-1",
    debt_payment_id: null,
    return_id: null,
    kind: "sale",
    status,
    receipt_seq: 154,
    fm_terminal_id: null,
    fm_receipt_seq: null,
    fiscal_sign: null,
    qr_url: null,
    payment_form: "cash",
    delivery: "printed",
    fiscal_at: null,
    ofd_acked_at: null,
    sent_at: null,
    offline_since: "2026-10-16T08:00:00Z",
    attempts: 3,
    cash_register_id: "cr-1",
    shift_id: "sh-1",
    created_at: "2026-10-16T08:00:00Z",
  };
}

function register(id: string, patch: Partial<CashRegister> = {}): CashRegister {
  return {
    id,
    branch_id: "b-1",
    name: `Kassa ${id}`,
    kind: "web",
    fiscal_module_id: null,
    txkm_contract_ref: null,
    fiscal_agent_id: null,
    fiscal_local_device_id: null,
    ofd_status: "active",
    fm_state: "ok",
    last_unacked_receipt_at: null,
    fm_receipts_pending: null,
    tax_registered_at: null,
    archived_at: null,
    version: 1,
    ...patch,
  };
}

function scope(retry?: () => unknown) {
  const listCalls: { status: string | null; cursor: string | null }[] = [];
  const retries: string[] = [];
  const s = fork({
    handlers: [
      [
        listReceiptsFx,
        (p: { status: string | null; cursor: string | null }) => {
          listCalls.push(p);
          return { items: [receipt("f-1", "failed"), receipt("f-2", "fiscalized")], next_cursor: null };
        },
      ],
      [listRegistersFx, () => [register("cr-1"), register("cr-2", { fm_state: "locked" })]],
      [
        retryReceiptFx,
        (id: string) => {
          retries.push(id);
          if (retry) return retry();
          return { status: "requeued" };
        },
      ],
    ],
  });
  return { s, listCalls, retries };
}

describe("BO-14 fiscal receipts (18 §14)", () => {
  it("opens with the failed filter and the registers' fiscal state", async () => {
    const { s, listCalls } = scope();
    await allSettled(fiscalOpened, { scope: s });
    expect(listCalls).toEqual([{ status: "failed", cursor: null }]);
    expect(s.getState($receipts)).toHaveLength(2);
    expect(s.getState($registers)).toHaveLength(2);
    await allSettled(fiscalFilterChanged, { scope: s, params: null });
    expect(listCalls.at(-1)).toEqual({ status: null, cursor: null });
  });

  it("retry only a not-yet-fiscalized receipt, once; it shows as re-queued", async () => {
    const { s, retries } = scope();
    await allSettled(fiscalOpened, { scope: s });
    await allSettled(fiscalRetryRequested, { scope: s, params: "f-2" }); // fiscalized → no retry
    await allSettled(fiscalRetryRequested, { scope: s, params: "f-1" });
    await allSettled(fiscalRetryRequested, { scope: s, params: "f-1" }); // already re-queued
    expect(retries).toEqual(["f-1"]);
    expect(s.getState($fiscalRequeued)).toEqual(["f-1"]);
  });

  it("a refused retry (409) is kept for the banner and the list reloads", async () => {
    const { s, listCalls } = scope(() => {
      throw new ApiError({ status: 409, code: "DOC_INVALID_STATE", messageKey: "errors.doc_invalid_state" });
    });
    await allSettled(fiscalOpened, { scope: s });
    await allSettled(fiscalRetryRequested, { scope: s, params: "f-1" });
    expect(s.getState($fiscalRetryError)?.code).toBe("DOC_INVALID_STATE");
    expect(listCalls).toHaveLength(2);
  });

  it("registers needing attention come first", () => {
    const list = [
      register("a", { name: "A" }),
      register("b", { name: "B", last_unacked_receipt_at: "2026-10-16T08:00:00Z" }),
      register("c", { name: "C", fm_state: "ack_overdue" }),
    ];
    expect(registersByAttention(list).map((r) => r.id)).toEqual(["c", "b", "a"]);
  });
});
