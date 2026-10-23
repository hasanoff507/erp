import { allSettled, fork, scopeBind } from "effector";
import { describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";

import {
  $actionError,
  $notice,
  $selected,
  $status,
  $transfers,
  actionsOf,
  cancelTransferFx,
  ettnViewOf,
  filterChanged,
  getTransferFx,
  isSendReady,
  listTransfersFx,
  moreRequested,
  postRequested,
  postTransferFx,
  receiveLineError,
  sendTransferFx,
  shortageOf,
  transferSelected,
  transferValue,
  transfersOpened,
  transitCounts,
  type ListRequest,
  type Transfer,
} from "./index.ts";

function transfer(id: string, patch: Partial<Transfer> = {}): Transfer {
  return {
    id,
    number: null,
    status: "draft",
    doc_date: "2026-10-16",
    branch_id: "b-1",
    from_branch_id: "b-1",
    to_branch_id: "b-2",
    from_warehouse_id: "w-1",
    to_warehouse_id: "w-2",
    transport_mode: "vehicle",
    vehicle_plate: "01A245BC",
    driver_name: null,
    ettn_ref: null,
    ettn: null,
    is_overdue: false,
    comment: null,
    created_by: "u-1",
    created_at: "2026-10-16T05:00:00Z",
    posted_at: null,
    sent_at: null,
    sent_by: null,
    received_at: null,
    received_by: null,
    cancelled_at: null,
    cancel_reason: null,
    lines: [
      {
        id: "l-1",
        line_no: 1,
        product_id: "p-1",
        product_name: "Shakar",
        qty_sent: "10.000",
        qty_received: null,
        unit_cost: null,
        lot_allocations: [],
      },
    ],
    warnings: [],
    ...patch,
  };
}

function scope(handlers: { send?: (id: string) => Transfer; get?: (id: string) => Transfer } = {}) {
  const calls: ListRequest[] = [];
  const s = fork({
    handlers: [
      [
        listTransfersFx,
        (req: ListRequest) => {
          calls.push(req);
          if (req.cursor === "c2") return { items: [transfer("t-3")], next_cursor: null };
          if (req.status === "sent")
            return { items: [transfer("t-2", { status: "sent" })], next_cursor: null };
          return { items: [transfer("t-1"), transfer("t-2", { status: "sent" })], next_cursor: "c2" };
        },
      ],
      [sendTransferFx, handlers.send ?? ((id: string) => transfer(id, { status: "sent" }))],
      [getTransferFx, handlers.get ?? ((id: string) => transfer(id))],
      [
        cancelTransferFx,
        ({ id }: { id: string }) =>
          transfer(id, { status: "cancelled", warnings: ["ETTN_CANCEL_IN_OPERATOR"] }),
      ],
    ],
  });
  return { s, calls };
}

describe("Ko'chirishlar model (US-M06-03, 19 §13)", () => {
  it("opens with all statuses, «Yana yuklash» appends, a status filter reloads from the first page", async () => {
    const { s, calls } = scope();
    await allSettled(transfersOpened, { scope: s });
    expect(calls).toEqual([{ status: null, cursor: null }]);
    expect(s.getState($transfers).map((t) => t.id)).toEqual(["t-1", "t-2"]);

    await allSettled(moreRequested, { scope: s });
    expect(s.getState($transfers).map((t) => t.id)).toEqual(["t-1", "t-2", "t-3"]);

    await allSettled(filterChanged, { scope: s, params: "sent" });
    expect(calls.at(-1)).toEqual({ status: "sent", cursor: null });
    expect(s.getState($transfers).map((t) => t.id)).toEqual(["t-2"]);
    expect(s.getState($status)).toBe("idle");
  });

  it("send refused with 409 ETTN_REQUIRED → error kept and the transfer re-read", async () => {
    const reads: string[] = [];
    const { s } = scope({
      send: () => {
        throw new ApiError({
          status: 409,
          code: "ETTN_REQUIRED",
          messageKey: "errors.ettn_required",
          params: { ettn_status: "sending" },
        });
      },
      get: (id) => {
        reads.push(id);
        return transfer(id, {
          status: "posted",
          ettn: { id: "e-1", status: "sending", operator_doc_id: null },
        });
      },
    });
    await allSettled(transfersOpened, { scope: s });
    await allSettled(transferSelected, { scope: s, params: "t-1" });
    await expect(allSettled(sendTransferFx, { scope: s, params: "t-1" })).resolves.toBeDefined();
    expect(s.getState($actionError)?.code).toBe("ETTN_REQUIRED");
    expect(reads).toEqual(["t-1"]);
    expect(s.getState($selected)?.ettn?.status).toBe("sending");
  });

  it("cancel with ETTN_CANCEL_IN_OPERATOR shows the operator notice", async () => {
    const { s } = scope();
    await allSettled(transfersOpened, { scope: s });
    await allSettled(cancelTransferFx, { scope: s, params: { id: "t-1", reason: "Xato" } });
    expect(s.getState($notice)).toBe("ettn_cancel_in_operator");
    expect(s.getState($transfers).find((t) => t.id === "t-1")?.status).toBe("cancelled");
  });
});

describe("one write at a time (WEB-16)", () => {
  it("a second «O'tkazish» while one is running is ignored", async () => {
    const posted: string[] = [];
    let finish!: (t: Transfer) => void;
    const s = fork({
      handlers: [
        [
          postTransferFx,
          (id: string) => {
            posted.push(id);
            if (posted.length > 1) return transfer(id, { status: "posted" });
            return new Promise<Transfer>((res) => (finish = res));
          },
        ],
      ],
    });
    const post = scopeBind(postRequested, { scope: s });
    post("t-1");
    post("t-1");
    post("t-2");
    expect(posted).toEqual(["t-1"]);
    finish(transfer("t-1", { status: "posted" }));
    await allSettled(s);
    await allSettled(postRequested, { scope: s, params: "t-2" });
    expect(posted).toEqual(["t-1", "t-2"]);
  });
});

describe("transfers lib", () => {
  const registered = { id: "e", status: "registered" as const, operator_doc_id: "OP-1" };

  it("send needs a registered e-TTN or on-foot transport; e-TTN column", () => {
    expect(isSendReady(transfer("a", { status: "posted" }))).toBe(false);
    expect(isSendReady(transfer("a", { status: "posted", ettn: registered }))).toBe(true);
    expect(isSendReady(transfer("a", { status: "posted", transport_mode: "on_foot_or_public" }))).toBe(true);
    expect(ettnViewOf(transfer("a", { transport_mode: "on_foot_or_public" }))).toBe("not_required");
    expect(ettnViewOf(transfer("a"))).toBe("none");
    expect(ettnViewOf(transfer("a", { ettn: registered }))).toBe("registered");
  });

  it("actions follow status, rights and the receiving branch", () => {
    const all = { create: true, receive: true, branchIds: ["b-2"] };
    expect(actionsOf(transfer("a"), all)).toEqual(["post", "cancel"]);
    expect(actionsOf(transfer("a", { status: "posted" }), all)).toEqual(["cancel"]);
    expect(actionsOf(transfer("a", { status: "posted", ettn: registered }), all)).toEqual(["send", "cancel"]);
    expect(actionsOf(transfer("a", { status: "sent" }), all)).toEqual(["receive", "cancel"]);
    expect(actionsOf(transfer("a", { status: "sent" }), { ...all, branchIds: ["b-1"] })).toEqual(["cancel"]);
    expect(actionsOf(transfer("a", { status: "received" }), all)).toEqual([]);
    expect(actionsOf(transfer("a"), { create: false, receive: true, branchIds: [] })).toEqual([]);
  });

  it("value, shortage and receive validation are exact decimals", () => {
    const sent = transfer("a", {
      lines: [
        { ...transfer("x").lines[0]!, qty_sent: "3.000", qty_received: "2.500", unit_cost: "1000.3333" },
        {
          ...transfer("x").lines[0]!,
          id: "l-2",
          qty_sent: "1.000",
          qty_received: "1.000",
          unit_cost: "0.1000",
        },
      ],
    });
    expect(transferValue(sent)).toBe("3001.10");
    expect(transferValue(transfer("a"))).toBeNull();
    expect(shortageOf(sent.lines)).toBe("0.500");
    expect(receiveLineError("10.000", "10.000")).toBeNull();
    expect(receiveLineError("10.000", "10.001")).toBe("range");
    expect(receiveLineError("10.000", "")).toBe("required");
    expect(
      transitCounts([
        { status: "sent", is_overdue: true },
        { status: "sent", is_overdue: false },
        { status: "posted", is_overdue: false },
      ]),
    ).toEqual({ inTransit: 2, overdue: 1 });
  });
});
