/** BO-24 effects — generated `api.cash.*BankSettlement*` (20 #55a–#55h; `bank_settlements.manage`). */
import { api } from "@shared/api";

import { apiFx } from "#/shared/lib/effect.ts";

import { toListParams } from "../lib/index.ts";
import type {
  BankImportResult,
  BankSettlementIn,
  BankSettlementPage,
  BankSettlementPatch,
  ListRequest,
  Settlement,
  SettlementDetail,
  TransitBalances,
} from "../types/index.ts";

export const listSettlementsFx = apiFx<ListRequest, BankSettlementPage>((req) =>
  api.cash.listBankSettlements(toListParams(req)),
);
export const loadTransitFx = apiFx<{ branchId: string | null }, TransitBalances>(({ branchId }) =>
  api.cash.getBankSettlementTransitBalances(branchId ? { branch_id: branchId } : {}),
);
export const getSettlementFx = apiFx<string, SettlementDetail>((id) => api.cash.getBankSettlement(id));
export const createSettlementFx = apiFx<BankSettlementIn, Settlement>((body) =>
  api.cash.createBankSettlement(body),
);
export const updateSettlementFx = apiFx<{ id: string; body: BankSettlementPatch }, Settlement>(
  ({ id, body }) => api.cash.updateBankSettlement(id, body),
);
export const postSettlementFx = apiFx<string, Settlement>((id) => api.cash.postBankSettlement(id, {}));
export const cancelSettlementFx = apiFx<{ id: string; reason: string }, Settlement>(({ id, reason }) =>
  api.cash.cancelBankSettlement(id, { reason }),
);
/** 20 #55g: 1CClientBankExchange `.txt` → drafts only (never posted automatically). */
export const importStatementFx = apiFx<{ file: File; branchId: string | null }, BankImportResult>(
  ({ file, branchId }) =>
    api.cash.importBankStatement({ file, ...(branchId ? { branch_id: branchId } : {}) }),
);
