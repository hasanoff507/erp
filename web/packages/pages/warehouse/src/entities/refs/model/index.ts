/**
 * Reference data shared by the warehouse and purchasing screens (one copy per visit, loaded lazily):
 * warehouses (`GET /warehouses` — the branch's own store + other branches as transfer targets),
 * units (`GET /units` — whole vs fractional quantities, 08 §8), categories (`GET /product-categories`)
 * and a product cache (`GET /products/{id}` — barcode, unit, category, marking of list rows that only
 * carry `product_id`). Staff (`GET /admin/users`, `settings.users`) feeds the «Javobgar shaxs» select.
 */
import { combine, createEvent, createStore, sample } from "effector";

import { api } from "@shared/api";
import type { CategoryOut, ProductOut, StaffOut, UnitOut, WarehouseOut } from "@shared/models";

import { $activeBranchId, $branches, ALL_BRANCHES } from "@shared/state/session";

import { apiFx, BULK_LIMIT } from "#/shared/lib/effect.ts";

import { missingIds, warehouseOfBranch } from "../lib/index.ts";

export type Warehouse = WarehouseOut;
export type Product = ProductOut;
export type Staff = StaffOut;

export const refsRequested = createEvent<{ canListStaff: boolean }>();
/** Product ids whose card is needed (list rows); already cached ids are skipped. */
export const productsRequested = createEvent<readonly string[]>();
/** A product picked in a form (search result) — cached without another request. */
export const productCached = createEvent<Product>();
/** Cards read elsewhere (e.g. with a purchase order) — cached without another request. */
export const productsCached = createEvent<readonly Product[]>();

export const loadWarehousesFx = apiFx<void, Warehouse[]>(async () => {
  const { items } = await api.branches.warehousesList();
  return items;
});

export const loadUnitsFx = apiFx<void, UnitOut[]>(async () => (await api.pricing.listUnits()).items);

export const loadCategoriesFx = apiFx<void, CategoryOut[]>(
  async () => (await api.pricing.listProductCategories({ size: BULK_LIMIT })).items,
);

/** At most this many `GET /products/{id}` at once (a long list must not flood the API). */
export const PRODUCT_FETCH_CONCURRENCY = 6;

/**
 * Cards of the given products, {@link PRODUCT_FETCH_CONCURRENCY} requests at a time; an unreadable one
 * (deleted, no access) is simply left out.
 */
export const loadProductsFx = apiFx<readonly string[], Record<string, Product>>(async (ids) => {
  const out: Record<string, Product> = {};
  let next = 0;
  const worker = async () => {
    while (next < ids.length) {
      const id = ids[next] as string;
      next += 1;
      try {
        const p = await api.pricing.getProduct(id);
        out[p.id] = p;
      } catch {
        // left out — the row shows the id-less fallback
      }
    }
  };
  await Promise.all(Array.from({ length: Math.min(PRODUCT_FETCH_CONCURRENCY, ids.length) }, worker));
  return out;
});

export const loadStaffFx = apiFx<void, Staff[]>(
  async () => (await api.auth.adminUsersList({ limit: BULK_LIMIT })).items,
);

export const $warehouses = createStore<Warehouse[]>([]);
export const $warehousesLoaded = createStore(false);
/** unit code → is_fractional. */
export const $units = createStore<Record<string, boolean>>({});
/** category id → name. */
export const $categories = createStore<Record<string, string>>({});
export const $products = createStore<Record<string, Product>>({});
export const $staff = createStore<Staff[]>([]);
/** Product ids being fetched right now — an overlapping request does not fetch them again. */
export const $inFlight = createStore<ReadonlySet<string>>(new Set());

const $requested = createStore({ warehouses: false, units: false, categories: false, staff: false });

sample({
  clock: refsRequested,
  source: $requested,
  filter: (r) => !r.warehouses,
  fn: () => undefined,
  target: loadWarehousesFx,
});
sample({
  clock: refsRequested,
  source: $requested,
  filter: (r) => !r.units,
  fn: () => undefined,
  target: loadUnitsFx,
});
sample({
  clock: refsRequested,
  source: $requested,
  filter: (r) => !r.categories,
  fn: () => undefined,
  target: loadCategoriesFx,
});
sample({
  clock: refsRequested,
  source: $requested,
  filter: (r, { canListStaff }) => canListStaff && !r.staff,
  fn: () => undefined,
  target: loadStaffFx,
});
$requested
  .on(loadWarehousesFx, (r) => ({ ...r, warehouses: true }))
  .on(loadUnitsFx, (r) => ({ ...r, units: true }))
  .on(loadCategoriesFx, (r) => ({ ...r, categories: true }))
  .on(loadStaffFx, (r) => ({ ...r, staff: true }))
  // A failed load is retried on the next visit.
  .on(loadWarehousesFx.fail, (r) => ({ ...r, warehouses: false }))
  .on(loadUnitsFx.fail, (r) => ({ ...r, units: false }))
  .on(loadCategoriesFx.fail, (r) => ({ ...r, categories: false }))
  .on(loadStaffFx.fail, (r) => ({ ...r, staff: false }));

$warehouses.on(loadWarehousesFx.doneData, (_, items) => items);
$warehousesLoaded.on(loadWarehousesFx.finally, () => true);
$units.on(loadUnitsFx.doneData, (_, items) =>
  Object.fromEntries(items.map((u) => [u.code, u.is_fractional])),
);
$categories.on(loadCategoriesFx.doneData, (_, items) => Object.fromEntries(items.map((c) => [c.id, c.name])));
$staff.on(loadStaffFx.doneData, (_, items) => items.filter((s) => s.status === "active"));

const toFetch = sample({
  clock: productsRequested,
  source: { known: $products, inFlight: $inFlight },
  fn: ({ known, inFlight }, ids) => missingIds(ids, known).filter((id) => !inFlight.has(id)),
});
sample({ clock: toFetch, filter: (ids) => ids.length > 0, target: loadProductsFx });
$inFlight
  .on(loadProductsFx, (set, ids) => new Set([...set, ...ids]))
  .on(loadProductsFx.finally, (set, { params }) => {
    const rest = new Set(set);
    for (const id of params) rest.delete(id);
    return rest;
  });
$products
  .on(loadProductsFx.doneData, (known, loaded) => ({ ...known, ...loaded }))
  .on(productCached, (known, p) => ({ ...known, [p.id]: p }))
  .on(productsCached, (known, list) => ({ ...known, ...Object.fromEntries(list.map((p) => [p.id, p])) }));

/**
 * The branch the warehouse screens work in: the topbar branch; `null` for «Barcha filiallar» (the
 * consolidated stock needs `GET /reports/stock`, Bosqich 4) or when none is chosen yet.
 */
export const $currentBranchId = combine($activeBranchId, $branches, (active, branches) => {
  if (active && active !== ALL_BRANCHES) return active;
  return branches.length === 1 ? (branches[0]?.id ?? null) : null;
});
/** The current branch's warehouse (MVP: one per branch, chosen automatically — qaror #54). */
export const $currentWarehouse = combine($warehouses, $currentBranchId, (list, branchId) =>
  warehouseOfBranch(list, branchId),
);
