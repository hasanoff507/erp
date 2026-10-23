import { allSettled, fork } from "effector";
import { describe, expect, it, vi } from "vitest";

import type { BranchListItemOut } from "@shared/models";

import {
  $addressReminders,
  $branches,
  $cashRegisters,
  $selectedBranchId,
  $taxSettings,
  $verifyHints,
  SETTLEMENT_RATE,
  branchSelected,
  createBranchFx,
  createCashRegisterFx,
  currentMonthStart,
  fetchBranchFx,
  fetchBranchesFx,
  fetchCashRegistersFx,
  fetchTaxSettingsFx,
  fetchTenantSettingsFx,
  fetchWarehousesFx,
  isPastMonth,
  monthToValidFrom,
  pageMounted,
  updateBranchFx,
} from "./index.ts";

const branch = (id: string, patch: Partial<BranchListItemOut> = {}): BranchListItemOut => ({
  id,
  name: `Filial ${id}`,
  code: id === "b-1" ? "01" : "02",
  address: null,
  is_default: id === "b-1",
  settlement_category: "city_100k_plus",
  activity_type: "retail",
  version: 1,
  ...patch,
});

function detailHandlers() {
  return {
    branch: vi.fn((id: string) =>
      Promise.resolve({ ...branch(id), today_sales: "0.00", stock_value: "0.00" }),
    ),
    tax: vi.fn(() =>
      Promise.resolve({
        items: [
          {
            valid_from: "2026-10-01",
            settlement_category: "city_100k_plus" as const,
            activity_type: "retail" as const,
          },
        ],
        total: 1,
        page: 1,
        size: 200,
      }),
    ),
    warehouses: vi.fn(() => Promise.resolve({ items: [] })),
    registers: vi.fn(() => Promise.resolve({ items: [] })),
  };
}

function scopeWith(extra: { values?: unknown; handlers?: unknown } = {}) {
  const h = detailHandlers();
  const scope = fork({
    values: (extra.values ?? []) as never,
    handlers: [
      [fetchBranchFx, h.branch],
      [fetchTaxSettingsFx, h.tax],
      [fetchWarehousesFx, h.warehouses],
      [fetchCashRegistersFx, h.registers],
      ...((extra.handlers ?? []) as never[]),
    ] as never,
  });
  return { scope, h };
}

describe("BO-12 branches model", () => {
  it("US-M14-01: loads branches, selects the default one and loads its data", async () => {
    const { scope, h } = scopeWith({
      handlers: [
        [
          fetchBranchesFx,
          vi.fn(() =>
            Promise.resolve({ items: [branch("b-2"), branch("b-1")], total: 2, page: 1, size: 200 }),
          ),
        ],
        [fetchTenantSettingsFx, vi.fn(() => Promise.reject(new Error("not called")))],
      ] as never,
    });
    await allSettled(pageMounted, { scope, params: { canTenant: false } });
    expect(scope.getState($branches).map((b) => b.id)).toEqual(["b-1", "b-2"]);
    expect(scope.getState($selectedBranchId)).toBe("b-1");
    expect(h.branch).toHaveBeenCalledWith("b-1");
    expect(h.registers).toHaveBeenCalledWith({ branchId: "b-1", includeArchived: false });
    expect(scope.getState($taxSettings)).toHaveLength(1);
  });

  it("QT-M14-02 / US-M14-03: a created branch is added, selected and gets its own warehouse/registers loaded", async () => {
    const { scope, h } = scopeWith({
      values: [[$selectedBranchId, "b-1"]],
      handlers: [
        [
          createBranchFx,
          vi.fn(() =>
            Promise.resolve({
              id: "b-3",
              name: "Yunusobod-1",
              address: null,
              code: "03",
              settlement_category: "other" as const,
              activity_type: "retail" as const,
              version: 1,
              warehouse: { id: "w-3", type: "store" as const, inventory_account: "2920" as const },
            }),
          ),
        ],
      ] as never,
    });
    await allSettled(createBranchFx, {
      scope,
      params: {
        name: "Yunusobod-1",
        address: "",
        settlementCategory: "other",
        categoryChosen: true,
        warehouseType: "store",
      },
    });
    expect(scope.getState($selectedBranchId)).toBe("b-3");
    expect(h.warehouses).toHaveBeenCalledWith("b-3");
    expect(scope.getState($verifyHints)).toEqual([]);
  });

  it("QT-M14-04: a branch saved with the untouched default category gets the 'please verify' hint", async () => {
    const { scope } = scopeWith({
      handlers: [
        [
          createBranchFx,
          vi.fn(() =>
            Promise.resolve({
              id: "b-4",
              name: "Sergeli",
              address: null,
              code: "04",
              settlement_category: "city_100k_plus" as const,
              activity_type: "retail" as const,
              version: 1,
              warehouse: { id: "w-4", type: "store" as const, inventory_account: "2920" as const },
            }),
          ),
        ],
        [
          updateBranchFx,
          vi.fn(() =>
            Promise.resolve({
              id: "b-4",
              name: "Sergeli",
              address: null,
              settlement_category: "city_100k_plus" as const,
              activity_type: "retail" as const,
              version: 2,
            }),
          ),
        ],
      ] as never,
    });
    await allSettled(createBranchFx, {
      scope,
      params: {
        name: "Sergeli",
        address: "",
        settlementCategory: "city_100k_plus",
        categoryChosen: false,
        warehouseType: "store",
      },
    });
    expect(scope.getState($verifyHints)).toEqual(["b-4"]);
    // Saving the category deliberately clears the hint.
    await allSettled(updateBranchFx, {
      scope,
      params: { branchId: "b-4", version: 1, settlementCategory: "city_100k_plus" },
    });
    expect(scope.getState($verifyHints)).toEqual([]);
  });

  it("QT-M14-03: category change → rate 2%, history reloaded; address change → re-registration reminder", async () => {
    const { scope, h } = scopeWith({
      values: [[$selectedBranchId, "b-1"]],
      handlers: [
        [
          updateBranchFx,
          vi.fn(() =>
            Promise.resolve({
              id: "b-1",
              name: "Filial b-1",
              address: "Yangi manzil",
              settlement_category: "other" as const,
              activity_type: "retail" as const,
              version: 2,
            }),
          ),
        ],
      ] as never,
    });
    await allSettled(updateBranchFx, {
      scope,
      params: { branchId: "b-1", version: 1, settlementCategory: "other", address: "Yangi manzil" },
    });
    expect(SETTLEMENT_RATE.other).toBe("2");
    expect(h.tax).toHaveBeenCalledWith("b-1");
    expect(scope.getState($addressReminders)).toEqual(["b-1"]);
  });

  it("new register → the branch register list is reloaded", async () => {
    const { scope, h } = scopeWith({
      values: [[$selectedBranchId, "b-1"]],
      handlers: [
        [
          createCashRegisterFx,
          vi.fn(() =>
            Promise.resolve({
              id: "cr-2",
              branch_id: "b-1",
              name: "Kassa 2",
              kind: "web" as const,
              ofd_status: "pending" as const,
              version: 1,
            }),
          ),
        ],
      ] as never,
    });
    await allSettled(createCashRegisterFx, {
      scope,
      params: { branchId: "b-1", name: "Kassa 2", kind: "web" },
    });
    expect(h.registers).toHaveBeenCalledWith({ branchId: "b-1", includeArchived: false });
    expect(scope.getState($cashRegisters)).toEqual([]);
  });

  it("late answers for another branch are dropped", async () => {
    let resolveFirst: (v: unknown) => void = () => undefined;
    const registers = vi.fn(({ branchId }: { branchId: string }) =>
      branchId === "b-1"
        ? new Promise((r) => (resolveFirst = r))
        : Promise.resolve({ items: [{ id: "cr-b2" }] }),
    );
    const h = detailHandlers();
    const scope = fork({
      handlers: [
        [fetchBranchFx, h.branch],
        [fetchTaxSettingsFx, h.tax],
        [fetchWarehousesFx, h.warehouses],
        [fetchCashRegistersFx, registers],
      ] as never,
    });
    const first = allSettled(branchSelected, { scope, params: "b-1" });
    const second = allSettled(branchSelected, { scope, params: "b-2" });
    await Promise.resolve();
    resolveFirst({ items: [{ id: "cr-b1" }] });
    await Promise.all([first, second]);
    expect(scope.getState($cashRegisters).map((r) => r.id)).toEqual(["cr-b2"]);
  });

  it("month helpers: valid_from is the 1st; past months are refused", () => {
    const today = new Date("2026-10-17T10:00:00");
    expect(currentMonthStart(today)).toBe("2026-10-01");
    expect(monthToValidFrom("2026-11")).toBe("2026-11-01");
    expect(isPastMonth("2026-09", today)).toBe(true);
    expect(isPastMonth("2026-10", today)).toBe(false);
  });
});
