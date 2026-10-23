export { unitLabel } from "#/shared/lib/units.ts";
import { useUnit } from "effector-react";
import { useCallback } from "react";

import { formatQty } from "@shared/lib/format";
import { $activeBranchId, $branches, ALL_BRANCHES } from "@shared/state/session";

import { unitLabel } from "#/shared/lib/units.ts";

import { qtyKindOf, warehouseOfBranch } from "../lib/index.ts";
import { $products, $units, $warehouses, type Warehouse } from "../model/index.ts";

/** `(qty, unitCode?) → "40"` / `"1,250"` (08 §8; the unit label is added by the caller when needed). */
export function useQtyFormat(): (value: string, unitCode?: string | null) => string {
  const units = useUnit($units);
  return useCallback(
    (value: string, unitCode?: string | null) => formatQty(value, qtyKindOf(unitCode, units, value)),
    [units],
  );
}

/** Quantity of a product with its unit: `"12 dona"`, `"1,250 kg"` (unit from the product cache). */
export function useProductQty(): (value: string, productId: string) => string {
  const format = useQtyFormat();
  const products = useUnit($products);
  return useCallback(
    (value: string, productId: string) => {
      const unit = products[productId]?.unit_code;
      const label = unitLabel(unit);
      return label ? `${format(value, unit)} ${label}` : format(value, unit);
    },
    [format, products],
  );
}

/**
 * The branch the screen works in: the topbar branch; `null` when «Barcha filiallar» is chosen (the
 * consolidated stock view needs `GET /reports/stock` — Bosqich 4) or nothing is chosen yet.
 */
export function useCurrentBranchId(): string | null {
  const [active, branches] = useUnit([$activeBranchId, $branches]);
  if (active && active !== ALL_BRANCHES) return active;
  return branches.length === 1 ? (branches[0]?.id ?? null) : null;
}

/** The current branch's warehouse (MVP: one per branch, chosen automatically — qaror #54). */
export function useCurrentWarehouse(): Warehouse | null {
  const branchId = useCurrentBranchId();
  const warehouses = useUnit($warehouses);
  return warehouseOfBranch(warehouses, branchId);
}

/** Branch name by id (session branches first, then a warehouse's own name), `"—"` when unknown. */
export function useBranchName(): (branchId: string) => string {
  const [branches, warehouses] = useUnit([$branches, $warehouses]);
  return useCallback(
    (branchId: string) =>
      branches.find((b) => b.id === branchId)?.name ??
      warehouses.find((w) => w.branch_id === branchId)?.name ??
      "—",
    [branches, warehouses],
  );
}
