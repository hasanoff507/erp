/**
 * Sale screen context (07 POS-02, 24 §5.1): pulled POS settings (weight-barcode templates, marking precheck,
 * card fallback, store requisites), category tabs, the device's catalog view, the fiscal register state
 * (`fm_state`, 18 §4.10) and the moment the device went offline (`offline_since`, 18 §4.1).
 */
import { createEffect, createEvent, createStore, sample } from "effector";

import {
  catalog,
  deviceSettings,
  fiscal,
  pullApplied,
  settings,
  type CategoryRow,
  type FiscalRegisterRow,
  type PosSettings,
} from "@shared/offline";
import { $isOnline } from "@shared/state/network";

import { $posDevice } from "#/entities/pos-session/index.ts";

import { setFractionalUnits } from "./units.ts";

export type CatalogView = "grid" | "list";
export const CATALOG_VIEW_KEY = "pos.catalog_view";

export const saleScreenOpened = createEvent();
export const catalogViewChanged = createEvent<CatalogView>();
export const categoryChanged = createEvent<string | null>();

export const loadContextFx = createEffect(async (cashRegisterId: string | null) => {
  const [posSettings, categories, view, register, units] = await Promise.all([
    settings.get(),
    catalog.categories(),
    deviceSettings.get<CatalogView>(CATALOG_VIEW_KEY).catch(() => undefined),
    cashRegisterId ? fiscal.register(cashRegisterId) : Promise.resolve(undefined),
    catalog.units().catch(() => []),
  ]);
  setFractionalUnits(units.filter((u) => u.is_fractional === true).map((u) => u.code));
  void catalog.warmUp().catch(() => undefined);
  return { posSettings, categories, view: view === "list" ? "list" : "grid", register: register ?? null };
});

const saveViewFx = createEffect((view: CatalogView) => deviceSettings.set(CATALOG_VIEW_KEY, view));

export const $posSettings = createStore<PosSettings | null>(null).on(
  loadContextFx.doneData,
  (_, r) => r.posSettings,
);
export const $categories = createStore<CategoryRow[]>([]).on(loadContextFx.doneData, (_, r) => r.categories);
export const $catalogView = createStore<CatalogView>("grid")
  .on(loadContextFx.doneData, (_, r) => r.view as CatalogView)
  .on(catalogViewChanged, (_, v) => v);
export const $categoryId = createStore<string | null>(null).on(categoryChanged, (_, c) => c);
export const $fiscalRegister = createStore<FiscalRegisterRow | null>(null).on(
  loadContextFx.doneData,
  (_, r) => r.register,
);
export const $contextLoaded = createStore(false).on(loadContextFx.finally, () => true);

/** `fm_state` that refuses a new fiscal receipt (18 §4.10). `unknown` is allowed — the fake provider starts there. */
export const LOCKED_FM_STATES: ReadonlySet<string> = new Set(["locked", "ack_overdue", "memory_full"]);
export const $fiscalDeviceLocked = $fiscalRegister.map((r) =>
  r?.fm_state ? LOCKED_FM_STATES.has(r.fm_state) : false,
);

/** Store requisites for the printed receipt (pull `settings`: tenant, branch, cash_register). */
export interface StoreInfo {
  name: string;
  stir: string | null;
  branchName: string | null;
  registerName: string | null;
}

const obj = (v: unknown): Record<string, unknown> =>
  v && typeof v === "object" ? (v as Record<string, unknown>) : {};
const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);

export const $storeInfo = $posSettings.map((s): StoreInfo => {
  const raw = s?.raw ?? {};
  return {
    name: str(obj(raw.tenant).name) ?? "",
    stir: str(obj(raw.tenant).stir),
    branchName: str(obj(raw.branch).name),
    registerName: str(obj(raw.cash_register).name),
  };
});

/** When the device went offline (null while online) — `offline_since` of offline sales. */
export const $offlineSince = createStore<string | null>(
  typeof navigator !== "undefined" && navigator.onLine === false ? new Date().toISOString() : null,
).on($isOnline.updates, (since, online) => (online ? null : (since ?? new Date().toISOString())));

sample({
  clock: saleScreenOpened,
  source: $posDevice,
  fn: (d) => d?.cashRegisterId ?? null,
  target: loadContextFx,
});
sample({
  clock: pullApplied,
  source: $posDevice,
  filter: (_, scopes) =>
    scopes.some((s) => s === "settings" || s === "catalog" || s === "fiscal" || s === "prices"),
  fn: (d) => d?.cashRegisterId ?? null,
  target: loadContextFx,
});
sample({ clock: catalogViewChanged, target: saveViewFx });
