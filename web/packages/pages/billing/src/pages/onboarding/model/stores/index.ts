import { combine, createStore } from "effector";

import type { ApiError } from "@shared/api";
import type { SignupOut, TermsVersionOut } from "@shared/models";

import { currentVersion, secondsLeft } from "../lib/index.ts";
import type {
  AccountData,
  OtpChallenge,
  ProductsMethod,
  SignupFailure,
  SignupMethod,
  StepId,
  StoreData,
} from "../types/index.ts";

export const $method = createStore<SignupMethod>("phone");
export const $step = createStore<StepId>("account");
export const $completed = createStore<readonly StepId[]>([]);
export const $skipped = createStore<readonly StepId[]>([]);
/** Wizard finished → the page navigates to BO-02. */
export const $finished = createStore(false);

// ① account
export const $otp = createStore<OtpChallenge | null>(null);
export const $otpError = createStore<ApiError | null>(null);
/** Epoch ms when «Qayta yuborish» unlocks. */
export const $resendAvailableAt = createStore<number | null>(null);
export const $now = createStore(0);
export const $resendIn = combine($resendAvailableAt, $now, secondsLeft);
export const $account = createStore<AccountData | null>(null);

// ② store
export const $storeDraft = createStore<StoreData | null>(null);
export const $terms = createStore<readonly TermsVersionOut[] | null>(null);
export const $termsError = createStore<ApiError | null>(null);
export const $termsVersion = $terms.map((items) => currentVersion(items, "terms"));
export const $signup = createStore<SignupOut | null>(null);
export const $signupError = createStore<ApiError | null>(null);
export const $signupFailure = createStore<SignupFailure | null>(null);

// ③–⑥
export const $productsMethod = createStore<ProductsMethod | null>(null);
export const $importedCount = createStore<number | null>(null);
export const $connectNow = createStore(false);
