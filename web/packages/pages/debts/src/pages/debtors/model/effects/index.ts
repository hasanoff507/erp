/** BO-06 effects — `GET /reports/debts-aging` (20 #21; contracts b4/debts-aging.md). */
import { api } from "@shared/api";
import type { DebtsAgingOut } from "@shared/models";

import { apiFx } from "#/shared/lib/effect.ts";

import type { AgingRequest } from "../types/index.ts";

export const loadAgingFx = apiFx<AgingRequest, DebtsAgingOut>(({ direction, branchId }) =>
  api.reports.getDebtsAging({ direction, ...(branchId ? { branch_id: branchId } : {}) }),
);
