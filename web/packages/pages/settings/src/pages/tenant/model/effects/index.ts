/** BO-14 effects — 20 #40a/#40b/#40c/#40h + GET /auth/terms (current consent text version). */
import { createEffect } from "effector";

import { api, type ApiError } from "@shared/api";
import type {
  ConsentOut,
  TaxRegimeOut,
  TenantSettingsFullOut,
  TenantSettingsOut,
  TenantSettingsPatchIn,
  TermsListOut,
} from "@shared/models";

import type { TaxRegime } from "../types/index.ts";

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
