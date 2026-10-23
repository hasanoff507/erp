/**
 * Small device-local caches of the warehouse screens (erp-device `device_settings`, 16 §12 — survive a
 * logout): warehouses of the tenant (POS-09 destination), the active stock count (POS-10) and incoming
 * transfers (POS-09 receive), so the screens keep working offline after one online visit.
 * Storage is injected for tests; the default is `deviceSettings` of @shared/offline.
 */
import { api } from "@shared/api";
import type { WarehouseOut } from "@shared/models";
import { deviceSettings } from "@shared/offline";

export interface KeyValueStore {
  get<T>(key: string): Promise<T | undefined>;
  set<T>(key: string, value: T): Promise<void>;
  remove(key: string): Promise<void>;
}

export const WH_CACHE_KEYS = {
  warehouses: "pos.wh.warehouses",
  counts: "pos.wh.counts",
  count: (id: string) => `pos.wh.count.${id}`,
  incoming: "pos.wh.incoming_transfers",
} as const;

export interface WarehouseRef {
  id: string;
  branchId: string;
  name: string;
}

export async function readCache<T>(key: string, store: KeyValueStore = deviceSettings): Promise<T | null> {
  try {
    return (await store.get<T>(key)) ?? null;
  } catch {
    return null;
  }
}

export async function writeCache<T>(
  key: string,
  value: T,
  store: KeyValueStore = deviceSettings,
): Promise<void> {
  try {
    await store.set(key, value);
  } catch {
    /* storage blocked — the screen works from memory */
  }
}

export const toWarehouseRef = (w: Pick<WarehouseOut, "id" | "branch_id" | "name">): WarehouseRef => ({
  id: w.id,
  branchId: w.branch_id,
  name: w.name,
});

/** Online: GET /warehouses (all branches the user sees) → cache; offline / error: the cached list. */
export async function loadWarehouses(
  online: boolean,
  store: KeyValueStore = deviceSettings,
): Promise<WarehouseRef[]> {
  if (online) {
    try {
      const list = (await api.branches.warehousesList()).items.map(toWarehouseRef);
      await writeCache(WH_CACHE_KEYS.warehouses, list, store);
      return list;
    } catch {
      /* fall back to the cache */
    }
  }
  return (await readCache<WarehouseRef[]>(WH_CACHE_KEYS.warehouses, store)) ?? [];
}
