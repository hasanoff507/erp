import { allSettled, createEvent, fork, sample, scopeBind } from "effector";
import { describe, expect, it } from "vitest";

import type { TransferOut } from "@shared/models";
import { $activeBranchId, $session, ALL_BRANCHES } from "@shared/state/session";

import { $warehouses, loadProductsFx, loadWarehousesFx } from "#/entities/refs/index.ts";
import { listCountsFx } from "#/features/stock-counts/model/index.ts";
import { listTransfersFx } from "#/features/transfers/model/index.ts";

import {
  $balances,
  $consolidated,
  $hasMore,
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
  filterItems,
  listExpiringLotsFx,
  loadDigestFx,
  loadExpiringFx,
  loadReviewCountFx,
  loadStockFx,
  loadTransitFx,
  lowOnlyToggled,
  moreRequested,
  ofBranch,
  pageMounted,
  searchChanged,
  summarize,
  summaryRefreshRequested,
  tabChanged,
  viewChanged,
  type Balance,
  type Lot,
  type StockReport,
} from "./index.ts";

const TODAY = "2026-10-16";

function balance(id: string, patch: Partial<Balance> = {}): Balance {
  return {
    product_id: id,
    name: `Tovar ${id}`,
    name_ru: null,
    unit_code: "pcs",
    category_id: null,
    category_name: "Ichimliklar",
    barcode: `478000${id}`,
    is_marked: false,
    is_weighed: false,
    min_stock: "5.000",
    qty: "10.000",
    value: "100000.00",
    avg_cost: "10000.0000",
    below_min: false,
    by_branch: [
      { branch_id: "b-1", branch_name: "Chilonzor-3", qty: "10.000", value: "100000.00", below_min: false },
    ],
    ...patch,
  };
}

function report(items: Balance[], patch: Partial<StockReport> = {}): StockReport {
  return {
    branch_id: null,
    consolidated: false,
    items,
    branches: [],
    total: {
      value: "200000.00",
      positions: items.length,
      below_min_count: items.filter((i) => i.below_min).length,
    },
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

function scope(branch: string = "b-1", branches = session.branches) {
  const calls: string[] = [];
  const productCalls: unknown[] = [];
  const s = fork({
    values: [
      [$session, { ...session, branches }],
      [$activeBranchId, branch],
    ],
    handlers: [
      [loadWarehousesFx, () => [W1, W2]],
      [
        loadStockFx,
        (scopeKey: string) => {
          calls.push(scopeKey);
          if (scopeKey === "*") {
            return report(
              [
                balance("p-1", {
                  qty: "15.000",
                  value: "150000.00",
                  by_branch: [
                    {
                      branch_id: "b-1",
                      branch_name: "Chilonzor-3",
                      qty: "10.000",
                      value: "100000.00",
                      below_min: false,
                    },
                    {
                      branch_id: "b-2",
                      branch_name: "Yunusobod-1",
                      qty: "5.000",
                      value: "50000.00",
                      below_min: false,
                    },
                  ],
                }),
              ],
              {
                consolidated: true,
                branches: [
                  {
                    branch_id: "b-1",
                    name: "Chilonzor-3",
                    value: "100000.00",
                    positions: 1,
                    below_min_count: 0,
                  },
                  {
                    branch_id: "b-2",
                    name: "Yunusobod-1",
                    value: "50000.00",
                    positions: 1,
                    below_min_count: 0,
                  },
                ],
                total: { value: "150000.00", positions: 1, below_min_count: 0 },
              },
            );
          }
          return report([
            balance("p-1"),
            balance("p-2", { below_min: true, value: "250.25", name: "Sut Oltin", barcode: "4780001" }),
            ...Array.from({ length: 60 }, (_, i) => balance(`x-${i}`, { value: "1.00" })),
          ]);
        },
      ],
      [listExpiringLotsFx, () => ({ items: [lot("l-1", "p-1", "2026-10-19")], next_cursor: null })],
      [
        loadExpiringFx,
        () => ({ lots: [lot("l-1", "p-1", "2026-10-19"), lot("l-2", "p-1", "2026-10-21")], capped: false }),
      ],
      [loadTransitFx, () => ({ inTransit: 2, overdue: 1, waitingEttn: 1 })],
      [loadReviewCountFx, () => 3],
      [loadDigestFx, () => []],
      [
        loadProductsFx,
        (ids: unknown) => {
          productCalls.push(ids);
          return {};
        },
      ],
    ],
  });
  return { s, calls, productCalls };
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

const flush = () => new Promise((r) => setTimeout(r, 0));
/** Topbar branch switch (the session's own event also persists it). */
const branchSwitched = createEvent<string>();
sample({ clock: branchSwitched, target: $activeBranchId });

describe("BO-03 stock page model (20 §20, 19 §7, US-M04-01…03, US-M04-06)", () => {
  it("mount → refs → the warehouse report: rows with card fields, KPI, expiry days, badges", async () => {
    const { s, calls, productCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canListStaff: false } });
    expect(s.getState($warehouses)).toHaveLength(2);
    expect(s.getState($warehouseId)).toBe("w-1");
    expect(calls).toEqual(["w-1"]);
    expect(s.getState($balances)).toHaveLength(50);
    expect(s.getState($hasMore)).toBe(true);
    expect(s.getState($summary)).toMatchObject({
      positions: 62,
      low: 1,
      value: "200000.00",
      lowNames: ["Sut Oltin"],
    });
    expect(s.getState($expiryDays)).toEqual({ "p-1": 3 });
    expect(s.getState($transit)).toEqual({ inTransit: 2, overdue: 1, waitingEttn: 1 });
    expect(s.getState($reviewCount)).toBe(3);
    expect(s.getState($consolidated)).toBe(false);
    // WEB-10: unit / category / barcode / marking come with the rows — no per-row product request.
    expect(productCalls).toEqual([]);

    await allSettled(moreRequested, { scope: s });
    expect(s.getState($balances)).toHaveLength(62);
    expect(s.getState($hasMore)).toBe(false);
  });

  it("search / lowOnly filter the report on the client (one request); the expiring view reads lots", async () => {
    const { s, calls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canListStaff: false } });
    await allSettled(searchChanged, { scope: s, params: "sut" });
    expect(s.getState($balances).map((b) => b.product_id)).toEqual(["p-2"]);
    await allSettled(searchChanged, { scope: s, params: "4780001" });
    expect(s.getState($balances).map((b) => b.product_id)).toEqual(["p-2"]);
    await allSettled(searchChanged, { scope: s, params: "" });
    await allSettled(lowOnlyToggled, { scope: s, params: true });
    expect(s.getState($filters)).toEqual({ search: "", lowOnly: true });
    expect(s.getState($balances).map((b) => b.product_id)).toEqual(["p-2"]);
    expect(s.getState($pageTotal)).toBe("250.25");
    expect(calls).toEqual(["w-1"]);

    await allSettled(viewChanged, { scope: s, params: "expiring" });
    expect(s.getState($lots).map((l) => l.id)).toEqual(["l-1"]);
  });

  it("QT-M04-03: «Barcha filiallar» reads the consolidated report — every branch and the total", async () => {
    const two = [...session.branches, { id: "b-2", name: "Yunusobod-1" }];
    const { s, calls } = scope(ALL_BRANCHES, two);
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canListStaff: false } });
    expect(calls).toEqual(["*"]);
    expect(s.getState($consolidated)).toBe(true);
    const [row] = s.getState($balances);
    expect(row?.by_branch.map((b) => [b.branch_name, b.qty])).toEqual([
      ["Chilonzor-3", "10.000"],
      ["Yunusobod-1", "5.000"],
    ]);
    expect(row?.qty).toBe("15.000");
    expect(s.getState($summary)?.value).toBe("150000.00");
    // Lots, transfers and counts are per warehouse — not read for «Barcha filiallar».
    expect(s.getState($transit)).toBeNull();
    expect(s.getState($reviewCount)).toBeNull();

    // Back to one branch → that warehouse's report.
    await allSettled(branchSwitched, { scope: s, params: "b-2" });
    expect(calls.at(-1)).toBe("w-2");
    expect(s.getState($consolidated)).toBe(false);
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
        [loadStockFx, () => report([])],
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
      ],
    });
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, canListStaff: false } });
    expect(review).toEqual(["w-1"]);
    expect(transit).toEqual(["b-1"]);
    expect(digest).toEqual([{ branchId: "b-1", from: "2026-10-10" }]);
    expect(s.getState($digest)?.map((t) => t.id)).toEqual(["t-1"]);
  });

  it("start A, switch to B, A answers → the stock / badge / lot stores stay empty (WEB-05)", async () => {
    type Set = {
      stock: ReturnType<typeof deferred<StockReport>>;
      review: ReturnType<typeof deferred<number>>;
      expiring: ReturnType<typeof deferred<{ lots: Lot[]; capped: boolean }>>;
      transit: ReturnType<typeof deferred<{ inTransit: number; overdue: number; waitingEttn: number }>>;
      lots: ReturnType<typeof deferred<{ items: Lot[]; next_cursor: string | null }>>;
    };
    const make = (): Set => ({
      stock: deferred(),
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
        [loadStockFx, (w: string) => pick(w).stock.promise],
        [loadExpiringFx, (w: string) => pick(w).expiring.promise],
        [loadReviewCountFx, (w: string) => pick(w).review.promise],
        [loadTransitFx, (br: string) => pick(br).transit.promise],
        [loadDigestFx, () => []],
        [listExpiringLotsFx, (r: { warehouseId: string }) => pick(r.warehouseId).lots.promise],
      ],
    });
    scopeBind(pageMounted, { scope: s })({ today: TODAY, canListStaff: false });
    scopeBind(viewChanged, { scope: s })("expiring");
    expect(s.getState($warehouseId)).toBe("w-1");
    scopeBind(branchSwitched, { scope: s })("b-2");
    expect(s.getState($warehouseId)).toBe("w-2");

    a.stock.resolve(report([balance("p-1")]));
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

    b.stock.resolve(report([]));
    b.review.resolve(1);
    b.expiring.resolve({ lots: [], capped: false });
    b.transit.resolve({ inTransit: 1, overdue: 0, waitingEttn: 0 });
    b.lots.resolve({ items: [], next_cursor: null });
    await allSettled(s);
    expect(s.getState($reviewCount)).toBe(1);
    expect(s.getState($transit)?.inTransit).toBe(1);
    expect(s.getState($summary)?.positions).toBe(0);
  });

  it("a failed report is an error state; «Qayta urinish» reads it again (WEB-06)", async () => {
    let fail = true;
    const s = fork({
      values: [
        [$session, session],
        [$activeBranchId, "b-1"],
        [$warehouses, [W1]],
      ],
      handlers: [
        [
          loadStockFx,
          () => {
            if (fail) throw new Error("boom");
            return report([balance("p-1")]);
          },
        ],
        [loadExpiringFx, () => ({ lots: [], capped: false })],
        [loadTransitFx, () => ({ inTransit: 0, overdue: 0, waitingEttn: 0 })],
        [loadReviewCountFx, () => 0],
        [loadDigestFx, () => []],
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

  it("three writes during a running read queue exactly one more run (WEB-10)", async () => {
    const runs: ReturnType<typeof deferred<StockReport>>[] = [];
    const s = fork({
      values: [
        [$session, session],
        [$activeBranchId, "b-1"],
        [$warehouses, [W1]],
      ],
      handlers: [
        [
          loadStockFx,
          () => {
            const d = deferred<StockReport>();
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
    runs[0]?.resolve(report([]));
    await flush();
    expect(runs).toHaveLength(2);
    runs[1]?.resolve(report([]));
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

  it("filters, summary and expiry are decimal-exact", () => {
    const rows = [
      balance("a", { qty: "0.000", value: "0.00", name: "Choy", name_ru: "Чай" }),
      balance("b", { qty: "-1.000", value: "-0.10", below_min: true }),
    ];
    expect(filterItems(rows, { search: "чай", lowOnly: false }).map((r) => r.product_id)).toEqual(["a"]);
    expect(filterItems(rows, { search: "", lowOnly: true }).map((r) => r.product_id)).toEqual(["b"]);
    expect(summarize(report(rows, { total: { value: "-0.10", positions: 1, below_min_count: 1 } }))).toEqual({
      value: "-0.10",
      positions: 1,
      low: 1,
      lowNames: ["Tovar b"],
      negative: 1,
    });
    expect(expiryByProduct([lot("x", "p", "2026-10-15"), lot("y", "q", null)], TODAY)).toEqual({ p: -1 });
  });
});
