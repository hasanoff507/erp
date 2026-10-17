/**
 * BO-14 effects — 20 #40a/#40b/#40c/#40h + GET /auth/terms (current consent text version);
 * zaxira usuli — 19 §17 `GET/PATCH /valuation-settings`; «Qayta hisoblash navbati» holat qatori —
 * 19 §18 `GET /recost-jobs?status=` (qaror #56c).
 */
import { createEffect } from "effector";

import { api, type ApiError } from "@shared/api";
import type {
  ConsentOut,
  ValuationSettingsOut,
  TaxRegimeOut,
  TenantSettingsFullOut,
  TenantSettingsOut,
  TenantSettingsPatchIn,
  TermsListOut,
} from "@shared/models";

import {
  RECOST_SUMMARY_LIMIT,
  type RecostSummary,
  type TaxRegime,
  type ValuationMethod,
} from "../types/index.ts";

export const fetchSettingsFx = createEffect<void, TenantSettingsFullOut, ApiError>(() =>
  api.branches.tenantSettingsGet(),
);

export const fetchTermsFx = createEffect<void, TermsListOut, ApiError>(() => api.auth.termsCurrent());

export const updateSettingsFx = createEffect<TenantSettingsPatchIn, TenantSettingsOut, ApiError>((patch) =>
  api.branches.tenantSettingsUpdate(patch),
);

export const createTaxRegimeFx = createEffect<
  { regime: TaxRegime; validFrom: string },
  TaxRegimeOut,
  ApiError
>(({ regime, validFrom }) => api.branches.tenantTaxRegimesCreate({ regime, valid_from: validFrom }));

/** Only the owner gives / withdraws the AI cross-border consent (qaror #61). */
export const createConsentFx = createEffect<
  { accepted: boolean; termsVersion: string },
  ConsentOut,
  ApiError
>(({ accepted, termsVersion }) =>
  api.branches.tenantConsentsCreate({ purpose: "ai_cross_border", terms_version: termsVersion, accepted }),
);

/** `GET /valuation-settings` (`stock.view`). */
export const fetchValuationFx = createEffect<void, ValuationSettingsOut, ApiError>(() =>
  api.inventory.getValuationSettings(),
);

/**
 * `PATCH /valuation-settings {method}` (`valuation.settings.manage`, US-M04-05): inside a year with stock
 * moves the change is stored as `pending_change` from 1 January of next year; 409
 * VALUATION_METHOD_CHANGE_NOT_ALLOWED — already changed this year.
 */
export const updateValuationFx = createEffect<ValuationMethod, ValuationSettingsOut, ApiError>((method) =>
  api.inventory.updateValuationSettings({ method }),
);

/** Open recost jobs (queued + running) and failed ones — counts for the status line. */
export const fetchRecostSummaryFx = createEffect<void, RecostSummary, ApiError>(async () => {
  const page = (status: "queued" | "running" | "failed") =>
    api.inventory.listRecostJobs({ status, limit: RECOST_SUMMARY_LIMIT });
  const [queued, running, failed] = await Promise.all([page("queued"), page("running"), page("failed")]);
  return {
    pending: queued.items.length + running.items.length,
    failed: failed.items.length,
    more: queued.next_cursor !== null || running.next_cursor !== null || failed.next_cursor !== null,
  };
});
