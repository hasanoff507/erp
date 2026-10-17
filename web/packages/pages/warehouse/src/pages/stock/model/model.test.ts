import { allSettled, createEvent, fork, sample, scopeBind } from "effector";
import { describe, expect, it } from "vitest";

import type { TransferOut } from "@shared/models";
import { $activeBranchId, $session } from "@shared/state/session";

import { $warehouses, loadProductsFx, loadWarehousesFx } from "#/entities/refs/index.ts";
import { listCountsFx } from "#/features/stock-counts/model/index.ts";
import { listTransfersFx } from "#/features/transfers/model/index.ts";

import {
  $balances,
  $digest,
  $expiring,
  $expiryDays,
  $filters,
  $lots,
  $pageTotal,
  $reviewCount,
  $summary,
  $summaryError,
  $tab,
  $transit,
  $warehouseId,
  digestFrom,
  digestOf,
  expiryByProduct,
  listBalancesFx,
  listExpiringLotsFx,
  loadDigestFx,
  loadExpiringFx,
  loadReviewCountFx,
  loadSummaryFx,
  loadTransitFx,
  lowOnlyToggled,
  moreRequested,
  ofBranch,
  pageMounted,
  searchChanged,
  summarize,
  summaryRefreshRequested,
  tabChanged,
  toBalancesQuery,
  viewChanged,
  type Balance,
  type BalancesRequest,
  type Lot,
  type StockSummary,
} from "./index.ts";

const TODAY = "2026-10-16";

function balance(id: string, patch: Partial<Balance> = {}): Balance {
  return {
    product_id: id,
    product_name: `Tovar ${id}`,
    warehouse_id: "w-1",
    qty: "10.000",
    value: "100000.00",
    avg_cost: "10000.0000",
    min_stock: "5.000",
    is_low: false,
    is_negative: false,
    updated_at: "2026-10-16T09:32:00Z",
    ...patch,
  };
}

function lot(id: string, productId: string, expiry: string | null): Lot {
  return {
    id,
    product_id: productId,
    product_name: `Tovar ${productId}`,
    warehouse_id: "w-1",
    received_at: "2026-10-01T05:00:00Z",
    qty_in: "10.000",
    qty_left: "4.000",
    blocked_qty: "0.000",
    unit_cost: "1000.0000",
    expiry_date: expiry,
    receipt_line_id: null,
    source_doc_type: "goods_receipts",
    source_doc_id: "gr-1",
  };
}

const session = {
  user: { id: "u-1", full_name: "Akmal", phone_masked: "" },
  tenant: { id: "t-1", name: "Baraka" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["owner"],
  permissions: ["stock.view"],
  scope: ["stock"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

function scope() {
  const calls: BalancesRequest[] = [];
  const s = fork({
    values: [
      [$session, session],
      [$activeBranchId, "b-1"],
    ],
    handlers: [
      [
        loadWarehousesFx,
        () => [
          {
            id: "w-1",
            branch_id: "b-1",
            name: "Asosiy",
            type: "store",
            inventory_account: "2920",
            version: 1,
          },
          {
            id: "w-2",
            branch_id: "b-2",
            name: "Yunusobod",
            type: "store",
            inventory_account: "2920",
            version: 1,
          },
        ],
      ],
      [
        listBalancesFx,
        (req: BalancesRequest) => {
          calls.push(req);
          if (req.cursor === "c2") return { items: [balance("p-3", { value: "0.50" })], next_cursor: null };
          return {
            items: [balance("p-1"), balance("p-2", { is_low: true, value: "250.25" })],
            next_cursor: "c2",
          };
        },
      ],
      [listExpiringLotsFx, () => ({ items: [lot("l-1", "p-1", "2026-10-19")], next_cursor: null })],
      [loadSummaryFx, () => summarize([balance("p-1"), balance("p-2", { is_low: true })], false)],
      [
        loadExpiringFx,
        () => ({ lots: [lot("l-1", "p-1", "2026-10-19"), lot("l-2", "p-1", "2026-10-21")], capped: false }),
      ],
      [loadTransitFx, () => ({ inTransit: 2, overdue: 1, waitingEttn: 1 })],
      [loadReviewCountFx, () => 3],
      [loadDigestFx, () => []],
      [loadProductsFx, () => ({})],
    ],
  });
  return { s, calls };
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

function transfer(id: string, patch: Partial<TransferOut> = {}): TransferOut {
  return {
    id,
    number: `KO-${id}`,
    status: "sent",
    doc_date: "2026-10-15",
    branch_id: "b-1",
    from_branch_id: "b-1",
    to_branch_id: "b-2",
    from_warehouse_id: "w-1",
    to_warehouse_id: "w-2",
    transport_mode: "vehicle",
    vehicle_plate: null,
    driver_name: null,
    ettn_ref: null,
    ettn: null,
    is_overdue: false,
    comment: null,
    created_by: "u-1",
    created_at: "2026-10-15T05:00:00Z",
    posted_at: null,
    sent_at: null,
    sent_by: null,
    received_at: null,
    received_by: null,
    cancelled_at: null,
    cancel_reason: null,
    lines: [],
    warnings: [],
    ...patch,
  };
}

const W1 = {
  id: "w-1",
  branch_id: "b-1",
  name: "Asosiy",
  type: "store",
  inventory_account: "2920",
  version: 1,
};
const W2 = {
  id: "w-2",
  branch_id: "b-2",
  name: "Yunusobod",
  type: "store",
  inventory_account: "2920",
  version: 1,
};
const flush = () => new Promise((r) => setTimeout(r, 0));
/** Topbar branch switch (the session's own event also persists it). */
const branchSwitched = createEvent<string>();
sample({ clock: branchSwitched, target: $activeBranchId });

describe("BO-03 stock page model (19 §7, US-M04-01…03, US-M04-06)", () => {
  it("mount → refs → the branch warehouse's balances, KPI, expiry days and tab badges", async () => {
    const { s, calls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canListStaff: false } });
    expect(s.getState($warehouses)).toHaveLength(2);
    expect(s.getState($warehouseId)).toBe("w-1");
    expect(calls[0]).toEqual({ warehouseId: "w-1", filters: { search: "", lowOnly: false }, cursor: null });
    expect(s.getState($balances).map((b) => b.product_id)).toEqual(["p-1", "p-2"]);
    expect(s.getState($pageTotal)).toBe("100250.25");
    expect(s.getState($summary)).toMatchObject({ positions: 2, low: 1, value: "200000.00" });
    expect(s.getState($expiryDays)).toEqual({ "p-1": 3 });
    expect(s.getState($transit)).toEqual({ inTransit: 2, overdue: 1, waitingEttn: 1 });
    expect(s.getState($reviewCount)).toBe(3);

    await allSettled(moreRequested, { scope: s });
    expect(s.getState($balances)).toHaveLength(3);
    expect(s.getState($pageTotal)).toBe("100250.75");
  });

  it("search / lowOnly reload from the first page; the expiring view reads lots", async () => {
    const { s, calls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canListStaff: false } });
    await allSettled(searchChanged, { scope: s, params: "Sut" });
    await allSettled(lowOnlyToggled, { scope: s, params: true });
    expect(s.getState($filters)).toEqual({ search: "Sut", lowOnly: true });
    expect(calls.at(-1)).toEqual({
      warehouseId: "w-1",
      filters: { search: "Sut", lowOnly: true },
      cursor: null,
    });

    await allSettled(viewChanged, { scope: s, params: "expiring" });
    expect(s.getState($lots).map((l) => l.id)).toEqual(["l-1"]);
  });

  it("tabs: opening «Ko'chirishlar» / «Inventarizatsiyalar» loads their lists", async () => {
    const opened: string[] = [];
    const s = fork({
      handlers: [
        [listTransfersFx, () => (opened.push("transfers"), { items: [], next_cursor: null })],
        [listCountsFx, () => (opened.push("counts"), { items: [], next_cursor: null })],
      ],
    });
    await allSettled(tabChanged, { scope: s, params: "transfers" });
    await allSettled(tabChanged, { scope: s, params: "counts" });
    expect(s.getState($tab)).toBe("counts");
    expect(opened).toEqual(["transfers", "counts"]);
  });
});

describe("KPI / badges: scope, stale answers, errors, coalescing (WEB-04/05/06/10/13)", () => {
  it("badges and the digest are read for the current warehouse / branch (WEB-04, WEB-13)", async () => {
    const review: string[] = [];
    const transit: string[] = [];
    const digest: unknown[] = [];
    const s = fork({
      values: [
        [$session, session],
        [$activeBranchId, "b-1"],
      ],
      handlers: [
        [loadWarehousesFx, () => [W1, W2]],
        [listBalancesFx, () => ({ items: [], next_cursor: null })],
        [loadSummaryFx, () => summarize([], false)],
        [loadExpiringFx, () => ({ lots: [], capped: false })],
        [
          loadTransitFx,
          (b: string) => {
            transit.push(b);
            return { inTransit: 0, overdue: 0, waitingEttn: 0 };
          },
        ],
        [
          loadReviewCountFx,
          (w: string) => {
            review.push(w);
            return 0;
          },
        ],
        [
          loadDigestFx,
          (r: unknown) => {
            digest.push(r);
            return [transfer("t-1")];
          },
        ],
        [loadProductsFx, () => ({})],
      ],
    });
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canListStaff: false } });
    expect(review).toEqual(["w-1"]);
    expect(transit).toEqual(["b-1"]);
    expect(digest).toEqual([{ branchId: "b-1", from: "2026-10-10" }]);
    expect(s.getState($digest)?.map((t) => t.id)).toEqual(["t-1"]);
  });

  it("start A, switch to B, A answers → the KPI / badge / lot stores stay empty (WEB-05)", async () => {
    type Set = {
      summary: ReturnType<typeof deferred<StockSummary>>;
      review: ReturnType<typeof deferred<number>>;
      expiring: ReturnType<typeof deferred<{ lots: Lot[]; capped: boolean }>>;
      transit: ReturnType<typeof deferred<{ inTransit: number; overdue: number; waitingEttn: number }>>;
      lots: ReturnType<typeof deferred<{ items: Lot[]; next_cursor: string | null }>>;
    };
    const make = (): Set => ({
      summary: deferred(),
      review: deferred(),
      expiring: deferred(),
      transit: deferred(),
      lots: deferred(),
    });
    const a = make();
    const b = make();
    const pick = (w: string) => (w === "w-1" || w === "b-1" ? a : b);
    const s = fork({
      values: [
        [$session, { ...session, branches: [...session.branches, { id: "b-2", name: "Yunusobod" }] }],
        [$activeBranchId, "b-1"],
        [$warehouses, [W1, W2]],
      ],
      handlers: [
        [listBalancesFx, () => ({ items: [], next_cursor: null })],
        [loadSummaryFx, (w: string) => pick(w).summary.promise],
        [loadExpiringFx, (w: string) => pick(w).expiring.promise],
        [loadReviewCountFx, (w: string) => pick(w).review.promise],
        [loadTransitFx, (br: string) => pick(br).transit.promise],
        [loadDigestFx, () => []],
        [listExpiringLotsFx, (r: { warehouseId: string }) => pick(r.warehouseId).lots.promise],
        [loadProductsFx, () => ({})],
      ],
    });
    scopeBind(pageMounted, { scope: s })({ today: TODAY, canListStaff: false });
    scopeBind(viewChanged, { scope: s })("expiring");
    expect(s.getState($warehouseId)).toBe("w-1");
    scopeBind(branchSwitched, { scope: s })("b-2");
    expect(s.getState($warehouseId)).toBe("w-2");

    a.summary.resolve(summarize([balance("p-1")], false));
    a.review.resolve(9);
    a.expiring.resolve({ lots: [lot("l-1", "p-1", "2026-10-19")], capped: false });
    a.transit.resolve({ inTransit: 5, overdue: 0, waitingEttn: 0 });
    a.lots.resolve({ items: [lot("l-1", "p-1", "2026-10-19")], next_cursor: null });
    await flush();
    expect(s.getState($summary)).toBeNull();
    expect(s.getState($reviewCount)).toBeNull();
    expect(s.getState($expiring)).toBeNull();
    expect(s.getState($transit)).toBeNull();
    expect(s.getState($lots)).toEqual([]);

    b.summary.resolve(summarize([], false));
    b.review.resolve(1);
    b.expiring.resolve({ lots: [], capped: false });
    b.transit.resolve({ inTransit: 1, overdue: 0, waitingEttn: 0 });
    b.lots.resolve({ items: [], next_cursor: null });
    await allSettled(s);
    expect(s.getState($reviewCount)).toBe(1);
    expect(s.getState($transit)?.inTransit).toBe(1);
  });

  it("a failed summary is an error state; «Qayta urinish» reads it again (WEB-06)", async () => {
    let fail = true;
    const s = fork({
      values: [
        [$session, session],
        [$activeBranchId, "b-1"],
        [$warehouses, [W1]],
      ],
      handlers: [
        [listBalancesFx, () => ({ items: [], next_cursor: null })],
        [
          loadSummaryFx,
          () => {
            if (fail) throw new Error("boom");
            return summarize([balance("p-1")], false);
          },
        ],
        [loadExpiringFx, () => ({ lots: [], capped: false })],
        [loadTransitFx, () => ({ inTransit: 0, overdue: 0, waitingEttn: 0 })],
        [loadReviewCountFx, () => 0],
        [loadDigestFx, () => []],
        [loadProductsFx, () => ({})],
      ],
    });
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canListStaff: false } });
    expect(s.getState($summary)).toBeNull();
    expect(s.getState($summaryError)).not.toBeNull();
    fail = false;
    await allSettled(summaryRefreshRequested, { scope: s });
    expect(s.getState($summaryError)).toBeNull();
    expect(s.getState($summary)?.positions).toBe(1);
  });

  it("three writes during a running summary queue exactly one more run (WEB-10)", async () => {
    const runs: ReturnType<typeof deferred<StockSummary>>[] = [];
    const s = fork({
      values: [
        [$session, session],
        [$activeBranchId, "b-1"],
        [$warehouses, [W1]],
      ],
      handlers: [
        [
          loadSummaryFx,
          () => {
            const d = deferred<StockSummary>();
            runs.push(d);
            return d.promise;
          },
        ],
        [loadExpiringFx, () => ({ lots: [], capped: false })],
        [loadTransitFx, () => ({ inTransit: 0, overdue: 0, waitingEttn: 0 })],
        [loadReviewCountFx, () => 0],
        [loadDigestFx, () => []],
      ],
    });
    const refresh = scopeBind(summaryRefreshRequested, { scope: s });
    refresh();
    expect(runs).toHaveLength(1);
    refresh();
    refresh();
    refresh();
    expect(runs).toHaveLength(1);
    runs[0]?.resolve(summarize([], false));
    await flush();
    expect(runs).toHaveLength(2);
    runs[1]?.resolve(summarize([], false));
    await allSettled(s);
    expect(runs).toHaveLength(2);
  });
});

describe("stock lib", () => {
  it("branch scope and the digest window / order (WEB-04, WEB-13)", () => {
    const list = [
      transfer("a", { doc_date: "2026-10-12" }),
      transfer("b", { from_branch_id: "b-3", to_branch_id: "b-4" }),
      transfer("c", { from_branch_id: "b-2", to_branch_id: "b-1", doc_date: "2026-10-16" }),
      ...["d", "e", "f", "g"].map((id) => transfer(id, { doc_date: "2026-10-14" })),
    ];
    expect(ofBranch(list, "b-1").map((t) => t.id)).toEqual(["a", "c", "d", "e", "f", "g"]);
    expect(digestOf(list, "b-1").map((t) => t.id)).toEqual(["c", "d", "e", "f", "g"]);
    expect(digestFrom(TODAY)).toBe("2026-10-10");
  });

  it("query, summary and expiry are decimal-exact", () => {
    expect(toBalancesQuery("w-1", { search: " sut ", lowOnly: true }, "c")).toEqual({
      warehouse_id: "w-1",
      search: "sut",
      low_stock: true,
      cursor: "c",
      limit: 50,
    });
    expect(
      summarize(
        [
          balance("a", { qty: "0.000", value: "0.00" }),
          balance("b", { qty: "-1.000", is_negative: true, value: "-0.10" }),
        ],
        true,
      ),
    ).toEqual({ value: "-0.10", positions: 1, low: 0, lowNames: [], negative: 1, capped: true });
    expect(expiryByProduct([lot("x", "p", "2026-10-15"), lot("y", "q", null)], TODAY)).toEqual({ p: -1 });
  });
});
