import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import type { PriceChangeOut, ProductOut, ProductPage } from "@shared/models";

import {
  $changes,
  $drafts,
  $history,
  $prices,
  $saveResult,
  $selectedId,
  approvalLimitOf,
  collectChanges,
  draftChanged,
  draftsReset,
  listProductsFx,
  loadHistoryFx,
  loadPricesFx,
  pageChanged,
  pageMounted,
  rowStateOf,
  savePricesFx,
  saveRequested,
  scopeChanged,
  validFromOf,
  type SavePricesParams,
} from "./index.ts";

function product(id: string, name: string): ProductOut {
  return {
    id,
    name,
    name_ru: null,
    category_id: null,
    unit_code: "pcs",
    mxik_code: null,
    package_code: null,
    vat_rate: "12.00",
    vat_exemption_code: null,
    is_marked: false,
    marking_group_code: null,
    is_weighed: false,
    min_stock: null,
    archived_at: null,
    version: 1,
    barcodes: [],
  };
}

const page: ProductPage = {
  items: [
    { ...product("p1", "Sut 1 l"), current_price: "12000.0000" },
    { ...product("p2", "Choy 100 g"), current_price: null },
  ],
  total: 2,
  page: 1,
  size: 20,
};

const page2: ProductPage = {
  items: [{ ...product("p3", "Non"), current_price: "5000.0000" }],
  total: 21,
  page: 2,
  size: 20,
};

function doc(status: string): PriceChangeOut {
  return {
    id: "doc-1",
    status,
    number: null,
    doc_date: "2026-10-17",
    branch_id: "b-1",
    comment: null,
    posted_at: null,
    approval_request_id: status === "pending_approval" ? "ar-1" : null,
    warnings: status === "pending_approval" ? ["APPROVAL_REQUIRED"] : [],
    lines: [],
  };
}

function scope(saveStatus = "posted") {
  const saved: SavePricesParams[] = [];
  const s = fork({
    handlers: [
      [listProductsFx, ({ page: n }: { page: number }) => (n === 2 ? page2 : page)],
      [
        loadPricesFx,
        ({ productIds }: { productIds: string[] }) =>
          Object.fromEntries(
            productIds.map((id) => [
              id,
              {
                current: { p1: "13500.0000", p2: "21000.0000", p3: "5000.0000" }[id] ?? null,
                scheduled: null,
              },
            ]),
          ),
      ],
      [loadHistoryFx, () => ({ items: [], next_cursor: null })],
      [
        savePricesFx,
        (params: SavePricesParams) => {
          saved.push(params);
          return doc(saveStatus);
        },
      ],
    ],
  });
  return { s, saved };
}

describe("BO-05 prices model (US-M09-01/02)", () => {
  it("loads rows + current prices, selects the first row for the history panel", async () => {
    const { s } = scope();
    await allSettled(pageMounted, { scope: s });
    expect(s.getState($prices).p1?.current).toBe("13500.0000");
    expect(s.getState($selectedId)).toBe("p1");
    expect(s.getState($history)).toEqual([]);
  });

  it("only changed rows become lines; save sends one document and clears the drafts", async () => {
    const { s, saved } = scope();
    await allSettled(pageMounted, { scope: s });
    await allSettled(draftChanged, { scope: s, params: { productId: "p1", value: "14000.00" } });
    await allSettled(draftChanged, { scope: s, params: { productId: "p2", value: "21000.00" } });
    expect(s.getState($changes).map((c) => c.product.id)).toEqual(["p1"]);

    await allSettled(saveRequested, { scope: s });
    expect(saved).toHaveLength(1);
    expect(saved[0]?.lines).toEqual([{ productId: "p1", newPrice: "14000.00" }]);
    expect(saved[0]?.validFrom).toBeNull();
    expect(saved[0]?.branchId).toBeNull();
    expect(s.getState($drafts)).toEqual({});
    expect(s.getState($saveResult)?.status).toBe("posted");
  });

  it("over-limit change → 202 pending_approval result is kept for the banner", async () => {
    const { s } = scope("pending_approval");
    await allSettled(pageMounted, { scope: s });
    await allSettled(draftChanged, { scope: s, params: { productId: "p2", value: "23500.00" } });
    const change = s.getState($changes)[0];
    expect(change?.pct).toBe("11.9");
    expect(change?.overLimit).toBe(true);
    // No grant: the server's default 10% — exact. A grant with an unknown limit: advisory only.
    expect(rowStateOf(change, approvalLimitOf(false))).toBe("approval");
    expect(rowStateOf(change, approvalLimitOf(true))).toBe("approvalMaybe");
    expect(rowStateOf(change, approvalLimitOf(true, null))).toBe("changed");
    expect(rowStateOf(change, approvalLimitOf(true, "15.00"))).toBe("changed");
    expect(rowStateOf(change, approvalLimitOf(true, "5.00"))).toBe("approval");

    await allSettled(saveRequested, { scope: s });
    expect(s.getState($saveResult)?.status).toBe("pending_approval");
    expect(s.getState($saveResult)?.approval_request_id).toBe("ar-1");
  });

  it("a zero price is not sent (newPrice > 0, 07 BO-05)", async () => {
    const { s, saved } = scope();
    await allSettled(pageMounted, { scope: s });
    await allSettled(draftChanged, { scope: s, params: { productId: "p1", value: "0.00" } });
    expect(rowStateOf(s.getState($changes)[0], approvalLimitOf(false))).toBe("invalid");
    await allSettled(saveRequested, { scope: s });
    expect(saved).toHaveLength(0);
  });

  it("drafts survive paging: edits on page 1 and page 2 are saved as one document", async () => {
    const { s, saved } = scope();
    await allSettled(pageMounted, { scope: s });
    await allSettled(draftChanged, { scope: s, params: { productId: "p1", value: "14000.00" } });
    await allSettled(pageChanged, { scope: s, params: 2 });
    await allSettled(draftChanged, { scope: s, params: { productId: "p3", value: "5200.00" } });
    expect(s.getState($changes).map((c) => c.product.id)).toEqual(["p1", "p3"]);
    expect(s.getState($changes)[0]?.oldPrice).toBe("13500.0000");

    await allSettled(saveRequested, { scope: s });
    expect(saved[0]?.lines).toEqual([
      { productId: "p1", newPrice: "14000.00" },
      { productId: "p3", newPrice: "5200.00" },
    ]);
    expect(s.getState($drafts)).toEqual({});
  });

  it("scope change and «Bekor qilish» drop the drafts", async () => {
    const { s } = scope();
    await allSettled(pageMounted, { scope: s });
    await allSettled(draftChanged, { scope: s, params: { productId: "p1", value: "14000.00" } });
    await allSettled(scopeChanged, { scope: s, params: "b-1" });
    expect(s.getState($drafts)).toEqual({});
    await allSettled(draftChanged, { scope: s, params: { productId: "p1", value: "14000.00" } });
    await allSettled(draftsReset, { scope: s });
    expect(s.getState($changes)).toEqual([]);
  });
});

describe("prices lib", () => {
  it("valid_from: today → null (from posting), later date → local midnight ISO", () => {
    expect(validFromOf("2026-10-17", "2026-10-17")).toBeNull();
    const later = validFromOf("2026-10-20", "2026-10-17");
    expect(later).not.toBeNull();
    expect(new Date(later ?? "").getDate()).toBe(20);
  });

  it("a product without a current price is a change without percent", () => {
    const changes = collectChanges(
      { p3: { current: null, scheduled: null } },
      { p3: { product: product("p3", "Yangi"), oldPrice: null, value: "5000.00" } },
    );
    expect(changes[0]?.pct).toBeNull();
    expect(changes[0]?.overLimit).toBe(false);
  });
});
