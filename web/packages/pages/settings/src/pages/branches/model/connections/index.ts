import { sample } from "effector";

import {
  archiveCashRegisterFx,
  createBranchFx,
  createCashRegisterFx,
  createTaxSettingFx,
  fetchBranchFx,
  fetchBranchesFx,
  fetchCashRegistersFx,
  fetchTaxSettingsFx,
  fetchTenantSettingsFx,
  fetchWarehousesFx,
  renameCashRegisterFx,
  updateBranchFx,
  updateCardFallbackFx,
  updateWarehouseFx,
} from "../effects/index.ts";
import {
  addressReminderDismissed,
  branchDataReloadRequested,
  branchSelected,
  branchesReloadRequested,
  includeArchivedToggled,
  pageMounted,
  verifyHintDismissed,
} from "../events/index.ts";
import { patchById, sortBranches, upsertBranch } from "../lib/index.ts";
import {
  $addressReminders,
  $branchDetail,
  $branchDetailError,
  $branchList,
  $branchesError,
  $branchesLoaded,
  $cashRegisters,
  $cashRegistersError,
  $includeArchived,
  $selectedBranchId,
  $taxSettings,
  $taxSettingsError,
  $tenantSettings,
  $tenantSettingsError,
  $verifyHints,
  $warehouses,
  $warehousesError,
} from "../stores/index.ts";

// --- List --------------------------------------------------------------------------------------------
$includeArchived.reset(pageMounted);
sample({ clock: [pageMounted, branchesReloadRequested], target: fetchBranchesFx });
sample({ clock: pageMounted, filter: ({ canTenant }) => canTenant, target: fetchTenantSettingsFx });

$branchList.on(fetchBranchesFx.doneData, (_, page) => page.items);
$branchesLoaded.on(fetchBranchesFx.done, () => true);
$branchesError.on(fetchBranchesFx.failData, (_, e) => e).reset(fetchBranchesFx.done);

// Keep the selection if it still exists, otherwise the default branch (first after sorting).
sample({
  clock: fetchBranchesFx.doneData,
  source: $selectedBranchId,
  filter: (selected, page) => page.items.length > 0 && !page.items.some((b) => b.id === selected),
  fn: (_, page) => sortBranches(page.items)[0]?.id ?? "",
  target: branchSelected,
});

// --- Selected branch: detail, tax history, warehouses, registers --------------------------------------
$selectedBranchId.on(branchSelected, (_, id) => id);
$branchDetail.reset(branchSelected);
$taxSettings.reset(branchSelected);
$warehouses.reset(branchSelected);
$cashRegisters.reset(branchSelected);

sample({
  clock: [branchSelected, branchDataReloadRequested],
  source: $selectedBranchId,
  filter: Boolean,
  target: [fetchBranchFx, fetchTaxSettingsFx, fetchWarehousesFx],
});
sample({
  clock: [branchSelected, branchDataReloadRequested, includeArchivedToggled],
  source: { branchId: $selectedBranchId, includeArchived: $includeArchived },
  filter: (s): s is { branchId: string; includeArchived: boolean } => s.branchId !== null,
  target: fetchCashRegistersFx,
});
$includeArchived.on(includeArchivedToggled, (_, value) => value);

// Answers for a branch that is no longer selected are dropped.
sample({
  clock: fetchBranchFx.done,
  source: $selectedBranchId,
  filter: (selected, { params }) => selected === params,
  fn: (_, { result }) => result,
  target: $branchDetail,
});
$branchDetailError.on(fetchBranchFx.failData, (_, e) => e).reset([fetchBranchFx.done, branchSelected]);

sample({
  clock: fetchTaxSettingsFx.done,
  source: $selectedBranchId,
  filter: (selected, { params }) => selected === params,
  fn: (_, { result }) => result.items,
  target: $taxSettings,
});
$taxSettingsError
  .on(fetchTaxSettingsFx.failData, (_, e) => e)
  .reset([fetchTaxSettingsFx.done, branchSelected]);

sample({
  clock: fetchWarehousesFx.done,
  source: $selectedBranchId,
  filter: (selected, { params }) => selected === params,
  fn: (_, { result }) => result.items,
  target: $warehouses,
});
$warehousesError.on(fetchWarehousesFx.failData, (_, e) => e).reset([fetchWarehousesFx.done, branchSelected]);

sample({
  clock: fetchCashRegistersFx.done,
  source: $selectedBranchId,
  filter: (selected, { params }) => selected === params.branchId,
  fn: (_, { result }) => result.items,
  target: $cashRegisters,
});
$cashRegistersError
  .on(fetchCashRegistersFx.failData, (_, e) => e)
  .reset([fetchCashRegistersFx.done, branchSelected]);

// --- Create / edit branch --------------------------------------------------------------------------
$branchList.on(createBranchFx.doneData, (list, created) =>
  upsertBranch(list, {
    id: created.id,
    name: created.name,
    code: created.code,
    address: created.address,
    is_default: false,
    settlement_category: created.settlement_category,
    activity_type: created.activity_type,
    version: created.version,
  }),
);
sample({ clock: createBranchFx.doneData, fn: (created) => created.id, target: branchSelected });
$verifyHints.on(createBranchFx.done, (ids, { params, result }) =>
  params.categoryChosen ? ids : [...ids, result.id],
);

$branchList.on(updateBranchFx.doneData, (list, updated) =>
  patchById(list, updated.id, {
    name: updated.name,
    address: updated.address,
    settlement_category: updated.settlement_category,
    activity_type: updated.activity_type,
    version: updated.version,
  }),
);
$branchDetail.on(updateBranchFx.doneData, (detail, updated) =>
  detail && detail.id === updated.id
    ? {
        ...detail,
        name: updated.name,
        address: updated.address,
        settlement_category: updated.settlement_category,
        activity_type: updated.activity_type,
        version: updated.version,
      }
    : detail,
);
// A deliberately saved category counts as checked.
$verifyHints
  .on(updateBranchFx.done, (ids, { params }) =>
    params.settlementCategory !== undefined ? ids.filter((id) => id !== params.branchId) : ids,
  )
  .on(verifyHintDismissed, (ids, id) => ids.filter((x) => x !== id));
$addressReminders
  .on(updateBranchFx.done, (ids, { params }) =>
    params.address !== undefined && !ids.includes(params.branchId) ? [...ids, params.branchId] : ids,
  )
  .on(addressReminderDismissed, (ids, id) => ids.filter((x) => x !== id));
// The category change upserts branch_tax_settings (20 #33) → refresh the history.
sample({
  clock: updateBranchFx.done,
  source: $selectedBranchId,
  filter: (selected, { params }) => selected === params.branchId && params.settlementCategory !== undefined,
  fn: (selected) => selected as string,
  target: fetchTaxSettingsFx,
});

sample({
  clock: createTaxSettingFx.done,
  source: $selectedBranchId,
  filter: (selected, { params }) => selected === params.branchId,
  fn: (selected) => selected as string,
  target: fetchTaxSettingsFx,
});

// --- Warehouses ------------------------------------------------------------------------------------------
$warehouses.on(updateWarehouseFx.doneData, (list, updated) =>
  patchById(list, updated.id, {
    name: updated.name,
    type: updated.type,
    inventory_account: updated.inventory_account,
    version: updated.version,
  }),
);

// --- Cash registers ------------------------------------------------------------------------------------
$cashRegisters
  .on(renameCashRegisterFx.doneData, (list, updated) =>
    patchById(list, updated.id, {
      name: updated.name,
      fiscal_agent_id: updated.fiscal_agent_id,
      fiscal_local_device_id: updated.fiscal_local_device_id,
      version: updated.version,
    }),
  )
  .on(archiveCashRegisterFx.doneData, (list, archived) =>
    patchById(list, archived.id, { archived_at: archived.archived_at }),
  );
// New registers and archived ones (which leave the default list) → reload the list.
sample({
  clock: [createCashRegisterFx.done, archiveCashRegisterFx.done],
  source: { branchId: $selectedBranchId, includeArchived: $includeArchived },
  filter: (s): s is { branchId: string; includeArchived: boolean } => s.branchId !== null,
  target: fetchCashRegistersFx,
});

// --- Store-level card policy -----------------------------------------------------------------------------
$tenantSettings
  .on(fetchTenantSettingsFx.doneData, (_, s) => ({ settings: s.settings, version: s.version }))
  .on(updateCardFallbackFx.doneData, (_, s) => ({ settings: s.settings, version: s.version }));
$tenantSettingsError.on(fetchTenantSettingsFx.failData, (_, e) => e).reset(fetchTenantSettingsFx.done);
