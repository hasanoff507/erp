import type { QtyUnitKind } from "@shared/lib/format";
import type { WarehouseOut } from "@shared/models";

/** Ids not yet resolved (deduplicated, order kept). */
export function missingIds(ids: readonly string[], known: Readonly<Record<string, unknown>>): string[] {
  return [...new Set(ids)].filter((id) => !(id in known));
}

/**
 * Whole vs fractional display (08 §8: `40` dona, `1,250` kg). An unknown unit falls back to the value
 * itself — a fraction is shown with 3 places, a whole number without.
 */
export function qtyKindOf(
  unitCode: string | null | undefined,
  units: Readonly<Record<string, boolean>>,
  value: string,
): QtyUnitKind {
  if (unitCode && unitCode in units) return units[unitCode] ? "fractional" : "integer";
  const dot = value.indexOf(".");
  const fraction = dot === -1 ? "" : value.slice(dot + 1);
  return [...fraction].every((ch) => ch === "0") ? "integer" : "fractional";
}

/**
 * The branch's warehouse (MVP: one per branch, qaror #54). A `store` (savdo zali) wins over a `stock`
 * warehouse when a branch somehow has both.
 */
export function warehouseOfBranch(
  warehouses: readonly WarehouseOut[],
  branchId: string | null,
): WarehouseOut | null {
  if (!branchId) return null;
  const own = warehouses.filter((w) => w.branch_id === branchId);
  return own.find((w) => w.type === "store") ?? own[0] ?? null;
}

/** Transfer targets: warehouses of other branches (no transfer inside one branch — 19 §13). */
export function otherBranchWarehouses(
  warehouses: readonly WarehouseOut[],
  branchId: string | null,
): WarehouseOut[] {
  return warehouses.filter((w) => w.branch_id !== branchId);
}
