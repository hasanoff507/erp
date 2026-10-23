/** BO-12 effects — 20 #30–#40i (branches, tax settings, warehouses, cash registers) + #40a/#40b. */
import { createEffect } from "effector";

import { api, type ApiError } from "@shared/api";
import type {
  BranchCreatedOut,
  BranchDetailOut,
  BranchPageOut,
  BranchUpdatedOut,
  CashRegisterArchivedOut,
  CashRegisterCreatedOut,
  CashRegisterListOut,
  CashRegisterUpdatedOut,
  TaxSettingCreatedOut,
  TaxSettingPageOut,
  TenantSettingsFullOut,
  TenantSettingsOut,
  WarehouseListOut,
  WarehouseUpdatedOut,
} from "@shared/models";

import type {
  CardManualFallback,
  CashRegisterKind,
  CreateBranchInput,
  CreateTaxSettingInput,
  InventoryAccount,
  UpdateBranchInput,
} from "../types/index.ts";

export const fetchBranchesFx = createEffect<void, BranchPageOut, ApiError>(() =>
  api.branches.listBranches({ page: 1, size: 200 }),
);

export const fetchBranchFx = createEffect<string, BranchDetailOut, ApiError>((id) =>
  api.branches.getBranch(id),
);

export const createBranchFx = createEffect<CreateBranchInput, BranchCreatedOut, ApiError>((input) =>
  api.branches.createBranch({
    name: input.name.trim(),
    address: input.address.trim() === "" ? null : input.address.trim(),
    settlement_category: input.settlementCategory,
    warehouse: { type: input.warehouseType },
  }),
);

export const updateBranchFx = createEffect<UpdateBranchInput, BranchUpdatedOut, ApiError>((input) =>
  api.branches.updateBranch(input.branchId, {
    ...(input.name !== undefined ? { name: input.name.trim() } : {}),
    ...(input.address !== undefined ? { address: input.address } : {}),
    ...(input.settlementCategory !== undefined ? { settlement_category: input.settlementCategory } : {}),
    version: input.version,
  }),
);

export const fetchTaxSettingsFx = createEffect<string, TaxSettingPageOut, ApiError>((branchId) =>
  api.branches.branchTaxSettingsList(branchId, { page: 1, size: 200 }),
);

export const createTaxSettingFx = createEffect<CreateTaxSettingInput, TaxSettingCreatedOut, ApiError>(
  (input) =>
    api.branches.branchTaxSettingsCreate(input.branchId, {
      valid_from: input.validFrom,
      settlement_category: input.settlementCategory,
      activity_type: input.activityType,
    }),
);

export const fetchWarehousesFx = createEffect<string, WarehouseListOut, ApiError>((branchId) =>
  api.branches.warehousesList({ branch_id: branchId }),
);

export const updateWarehouseFx = createEffect<
  { warehouseId: string; inventoryAccount: InventoryAccount; version: number },
  WarehouseUpdatedOut,
  ApiError
>(({ warehouseId, inventoryAccount, version }) =>
  api.branches.warehousesUpdate(warehouseId, { inventory_account: inventoryAccount, version }),
);

export const fetchCashRegistersFx = createEffect<
  { branchId: string; includeArchived: boolean },
  CashRegisterListOut,
  ApiError
>(({ branchId, includeArchived }) =>
  api.branches.cashRegistersList({ branch_id: branchId, include_archived: includeArchived }),
);

export const createCashRegisterFx = createEffect<
  { branchId: string; name: string; kind: CashRegisterKind },
  CashRegisterCreatedOut,
  ApiError
>(({ branchId, name, kind }) =>
  api.branches.cashRegistersCreate({ branch_id: branchId, name: name.trim(), kind }),
);

export const renameCashRegisterFx = createEffect<
  { registerId: string; name: string; version: number },
  CashRegisterUpdatedOut,
  ApiError
>(({ registerId, name, version }) =>
  api.branches.cashRegistersUpdate(registerId, { name: name.trim(), version }),
);

export const archiveCashRegisterFx = createEffect<string, CashRegisterArchivedOut, ApiError>((registerId) =>
  api.branches.cashRegistersArchive(registerId, {}),
);

export const fetchTenantSettingsFx = createEffect<void, TenantSettingsFullOut, ApiError>(() =>
  api.branches.tenantSettingsGet(),
);

/** BO-12 "Terminalsiz karta (rekvizitsiz)" — the store-level `card_manual_fallback` (qaror #71). */
export const updateCardFallbackFx = createEffect<
  { value: CardManualFallback; version: number },
  TenantSettingsOut,
  ApiError
>(({ value, version }) =>
  api.branches.tenantSettingsUpdate({ settings: { card_manual_fallback: value }, version }),
);
