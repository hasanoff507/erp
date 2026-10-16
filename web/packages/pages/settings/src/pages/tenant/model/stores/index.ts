import { createStore } from "effector";

import type { ApiError } from "@shared/api";
import type { ConsentOut } from "@shared/models";

import { aiTermsOf } from "../lib/index.ts";
import type { TenantSettings, TermsVersion } from "../types/index.ts";

export const $settings = createStore<TenantSettings | null>(null);
export const $settingsError = createStore<ApiError | null>(null);
export const $terms = createStore<TermsVersion[]>([]);
export const $termsError = createStore<ApiError | null>(null);
export const $aiTerms = $terms.map(aiTermsOf);
/** Last consent answer in this visit (its `at` is shown next to the switch). */
export const $lastConsent = createStore<ConsentOut | null>(null);
