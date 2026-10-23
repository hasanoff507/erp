import { combine, createStore } from "effector";

import type { ApiError } from "@shared/api";
import type { TenantSettingsOut } from "@shared/models";

import { sortBranches } from "../lib/index.ts";
import type { Branch, BranchDetail, CashRegister, TaxSetting, Warehouse } from "../types/index.ts";

export const $branchList = createStore<Branch[]>([]);
export const $branches = $branchList.map(sortBranches);
export const $branchesLoaded = createStore(false);
export const $branchesError = createStore<ApiError | null>(null);

export const $selectedBranchId = createStore<string | null>(null);
export const $selectedBranch = combine(
  $branchList,
  $selectedBranchId,
  (list, id) => list.find((b) => b.id === id) ?? null,
);

export const $branchDetail = createStore<BranchDetail | null>(null);
export const $branchDetailError = createStore<ApiError | null>(null);
export const $taxSettings = createStore<TaxSetting[]>([]);
export const $taxSettingsError = createStore<ApiError | null>(null);
export const $warehouses = createStore<Warehouse[]>([]);
export const $warehousesError = createStore<ApiError | null>(null);
export const $cashRegisters = createStore<CashRegister[]>([]);
export const $cashRegistersError = createStore<ApiError | null>(null);
export const $includeArchived = createStore(false);

/** Branches saved with the default category the owner never chose (US-M14-04: "tekshiring"). */
export const $verifyHints = createStore<readonly string[]>([]);
/** Branches whose address changed in this visit: re-register their registers within 3 working days. */
export const $addressReminders = createStore<readonly string[]>([]);

/** Store-level settings (only for `settings.tenant`): `card_manual_fallback` + `version`. */
export const $tenantSettings = createStore<Pick<TenantSettingsOut, "settings" | "version"> | null>(null);
export const $tenantSettingsError = createStore<ApiError | null>(null);
