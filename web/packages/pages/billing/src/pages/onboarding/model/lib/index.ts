import type { ApiError } from "@shared/api";
import { dayjs } from "@shared/lib/date";
import type { SignupIn, TermsVersionOut } from "@shared/models";
import type { StepItem } from "@shared/ui";

import {
  SKIPPABLE_STEPS,
  STEP_IDS,
  TRIAL_DAYS,
  type AccountData,
  type SignupFailure,
  type SignupMethod,
  type StepId,
  type StoreData,
} from "../types/index.ts";

export const stepIndex = (step: StepId): number => STEP_IDS.indexOf(step);

export function nextStep(step: StepId): StepId | null {
  return STEP_IDS[stepIndex(step) + 1] ?? null;
}

export function previousStep(step: StepId): StepId | null {
  return STEP_IDS[stepIndex(step) - 1] ?? null;
}

/** Left-panel states (mockup Bo21Royxat): done / current / optional (④⑤⑥ not reached) / next. */
export function stepStates(
  current: StepId,
  completed: readonly StepId[],
  labels: (id: StepId) => { title: string; description: string },
): StepItem[] {
  return STEP_IDS.map((id) => {
    const state: StepItem["state"] =
      id === current
        ? "current"
        : completed.includes(id)
          ? "done"
          : SKIPPABLE_STEPS.includes(id)
            ? "optional"
            : "next";
    return { id, state, ...labels(id) };
  });
}

/** Current version of a document kind from GET /auth/terms (`null` while unknown). */
export function currentVersion(items: readonly TermsVersionOut[] | null, kind: TermsVersionOut["kind"]) {
  return items?.find((item) => item.kind === kind) ?? null;
}

/** Trial preview under «Davom» on ② (07): start today, 30 days (server value wins after signup). */
export function trialPeriod(start: Date, endsAt?: string | null): { from: Date; to: Date } {
  return { from: start, to: endsAt ? new Date(endsAt) : dayjs(start).add(TRIAL_DAYS, "day").toDate() };
}

export function signupBody(input: {
  account: AccountData;
  store: StoreData;
  challengeId: string;
  termsVersion: string;
}): SignupIn {
  const { account, store } = input;
  return {
    otp_challenge_id: input.challengeId,
    ...(account.password !== null ? { password: account.password } : {}),
    owner_name: account.ownerName.trim(),
    store_name: store.storeName.trim(),
    business_type: store.businessType,
    legal_form: store.legalForm,
    accepted_terms_version: input.termsVersion,
    ai_cross_border_consent: store.aiCrossBorderConsent,
  };
}

const ACCOUNT_FIELDS = new Set(["phone", "password", "owner_name", "otp_challenge_id"]);

/** POST /auth/signup error → where the user has to go (backend auth/application/signup.py). */
export function classifySignupError(error: ApiError, method: SignupMethod): SignupFailure {
  const fields = error.details.map((d) => d.field);
  if (error.code === "OTP_INVALID" || error.code === "OTP_EXPIRED") return "otp_stale";
  if (error.code !== "VALIDATION_ERROR") return "general";
  if (error.details.some((d) => d.field === "phone" && d.messageKey === "validation.phone_taken")) {
    return "phone_taken";
  }
  if (fields.includes("accepted_terms_version")) return "terms_outdated";
  if (method === "google" && error.details.some((d) => d.field === "password")) return "google_expired";
  return fields.length > 0 ? "fields" : "general";
}

/** A signup failure that must be fixed on step ① (account fields / phone proof). */
export function isAccountFailure(failure: SignupFailure, error: ApiError): boolean {
  if (failure === "phone_taken" || failure === "otp_stale" || failure === "google_expired") return true;
  return failure === "fields" && error.details.every((d) => ACCOUNT_FIELDS.has(d.field));
}

/** Whole seconds left before «Qayta yuborish» is allowed. */
export function secondsLeft(availableAt: number | null, now: number): number {
  if (availableAt === null) return 0;
  return Math.max(0, Math.ceil((availableAt - now) / 1000));
}

/** `m:ss` for the resend countdown. */
export function formatCountdown(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(s / 60);
  const rest = s % 60;
  return `${minutes}:${rest < 10 ? "0" : ""}${rest}`;
}
