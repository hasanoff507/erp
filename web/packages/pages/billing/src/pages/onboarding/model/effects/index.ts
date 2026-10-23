import { createEffect } from "effector";

import { api, resetCsrfToken, toApiError, type ApiError } from "@shared/api";
import type { OtpRequestOut, OtpVerifyOut, SignupIn, SignupOut, TermsListOut } from "@shared/models";

import { track, type AnalyticsEvent } from "#/shared/lib/analytics.ts";

/** POST /auth/otp/request purpose=signup — Telegram bot first, SMS fallback (14 §4.2). */
export const requestOtpFx = createEffect<string, OtpRequestOut, ApiError>(async (phone) => {
  try {
    return await api.auth.otpRequest({ phone, purpose: "signup" }, { erpPublic: true });
  } catch (error) {
    throw toApiError(error);
  }
});

export const verifyOtpFx = createEffect<{ challengeId: string; code: string }, OtpVerifyOut, ApiError>(
  async ({ challengeId, code }) => {
    try {
      return await api.auth.otpVerify({ challenge_id: challengeId, code }, { erpPublic: true });
    } catch (error) {
      throw toApiError(error);
    }
  },
);

/** GET /auth/terms — current `terms` version for `accepted_terms_version` (07 BO-21 ②). */
export const loadTermsFx = createEffect<void, TermsListOut, ApiError>(async () => {
  try {
    return await api.auth.termsCurrent({ erpPublic: true });
  } catch (error) {
    throw toApiError(error);
  }
});

/** POST /auth/signup — provisions the tenant and sets the `__Host-sid` cookie (14 §20). */
export const signupFx = createEffect<SignupIn, SignupOut, ApiError>(async (body) => {
  try {
    return await api.auth.signup(body, { erpPublic: true });
  } catch (error) {
    throw toApiError(error);
  }
});

/** A fresh session cookie → a fresh CSRF token on the next authenticated write. */
export const resetCsrfFx = createEffect(() => resetCsrfToken());

export const trackFx = createEffect(
  ({ event, props }: { event: AnalyticsEvent; props?: Record<string, string> }) => track(event, props),
);

/** Reads the clock (kept in an effect so tests can replace it). */
export const readClockFx = createEffect(() => Date.now());

/** Epoch ms when «Qayta yuborish» unlocks after a code was sent. */
export const stampResendFx = createEffect((cooldownS: number) => Date.now() + cooldownS * 1000);
