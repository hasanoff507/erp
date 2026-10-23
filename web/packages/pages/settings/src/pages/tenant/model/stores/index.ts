import { createStore } from "effector";

import type { ApiError } from "@shared/api";
import type { ConsentOut, ValuationSettingsOut } from "@shared/models";

import { aiTermsOf } from "../lib/index.ts";
import type { RecostSummary, TenantSettings, TermsVersion } from "../types/index.ts";

export const $settings = createStore<TenantSettings | null>(null);
export const $settingsError = createStore<ApiError | null>(null);
export const $terms = createStore<TermsVersion[]>([]);
export const $termsError = createStore<ApiError | null>(null);
export const $aiTerms = $terms.map(aiTermsOf);
/** Last consent answer in this visit (its `at` is shown next to the switch). */
export const $lastConsent = createStore<ConsentOut | null>(null);

/** 19 §17 `GET /valuation-settings` — current method, since when, the scheduled change. */
export const $valuation = createStore<ValuationSettingsOut | null>(null);
export const $valuationError = createStore<ApiError | null>(null);
/** Counts for the «Qayta hisoblash navbati» status line (qaror #56c). */
export const $recostSummary = createStore<RecostSummary | null>(null);
export const $recostSummaryError = createStore<ApiError | null>(null);
