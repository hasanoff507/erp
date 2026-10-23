import { allSettled, fork, type Scope } from "effector";
import { describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";
import type { SignupIn, SignupOut } from "@shared/models";
import { getSessionFx } from "@shared/state/session";

import { readClockFx, resetCsrfFx, stampResendFx, trackFx } from "./effects/index.ts";
import {
  $account,
  $completed,
  $finished,
  $method,
  $openingStockLines,
  $openingStockMethod,
  $otp,
  $resendAvailableAt,
  $resendIn,
  $signupFailure,
  $skipped,
  $step,
  accountSubmitted,
  backClicked,
  classifySignupError,
  finishClicked,
  formatCountdown,
  loadTermsFx,
  nextClicked,
  openingStockMethodSelected,
  openingStockSaved,
  otpCodeSubmitted,
  otpRequested,
  pageMounted,
  phoneChanged,
  requestOtpFx,
  signupBody,
  signupFx,
  skipClicked,
  stepStates,
  storeSubmitted,
  verifyOtpFx,
  type StoreData,
} from "./index.ts";

const PHONE = "+998901234567";
const STORE: StoreData = {
  storeName: "Baraka do'koni",
  businessType: "retail",
  legalForm: "llc",
  acceptTerms: true,
  aiCrossBorderConsent: true,
};
const TERMS = {
  items: [
    {
      kind: "terms" as const,
      version: "1.2",
      text_url: "/t",
      text_sha256: "x",
      effective_from: "2026-10-01",
    },
    {
      kind: "ai_cross_border" as const,
      version: "1.0",
      text_url: "/a",
      text_sha256: "y",
      effective_from: "2026-10-01",
    },
  ],
};
const SIGNUP_OUT: SignupOut = {
  tenant_id: "t-1",
  user_id: "u-1",
  sub_status: "trial",
  trial_ends_at: "2026-11-16T00:00:00Z",
};

const validation = (field: string, messageKey: string) =>
  new ApiError({
    status: 422,
    code: "VALIDATION_ERROR",
    messageKey: "errors.validation",
    details: [{ field, messageKey }],
  });

function setup(signup: (body: SignupIn) => Promise<SignupOut> = () => Promise.resolve(SIGNUP_OUT)) {
  const signupCalls: SignupIn[] = [];
  const tracked: string[] = [];
  const scope = fork({
    handlers: [
      [
        requestOtpFx,
        () =>
          Promise.resolve({
            challenge_id: "ch-1",
            channel_used: "sms" as const,
            expires_at: "2026-10-17T10:05:00Z",
            warnings: [{ code: "TELEGRAM_NOT_LINKED", message_key: "errors.telegram_not_linked" }],
          }),
      ],
      [
        verifyOtpFx,
        ({ challengeId, code }: { challengeId: string; code: string }) =>
          code === "123456"
            ? Promise.resolve({ challenge_id: challengeId, purpose: "signup" as const, verified: true })
            : Promise.reject(
                new ApiError({ status: 400, code: "OTP_INVALID", messageKey: "errors.otp_invalid" }),
              ),
      ],
      [loadTermsFx, () => Promise.resolve(TERMS)],
      [
        signupFx,
        (body: SignupIn) => {
          signupCalls.push(body);
          return signup(body);
        },
      ],
      [resetCsrfFx, () => undefined],
      [stampResendFx, () => 1_000 + 60_000],
      // The first countdown tick is past the cooldown → the interval stops (allSettled can settle).
      [readClockFx, () => 1_000 + 120_000],
      [trackFx, ({ event }: { event: string }) => void tracked.push(event)],
      [
        getSessionFx,
        () =>
          Promise.reject(
            new ApiError({ status: 401, code: "UNAUTHORIZED", messageKey: "errors.unauthorized" }),
          ),
      ],
    ],
  });
  return { scope, signupCalls, tracked };
}

async function passAccount(scope: Scope, password: string | null = "secret-pass") {
  await allSettled(pageMounted, { scope, params: { method: password === null ? "google" : "phone" } });
  await allSettled(otpRequested, { scope, params: PHONE });
  await allSettled(otpCodeSubmitted, { scope, params: "123456" });
  await allSettled(accountSubmitted, { scope, params: { phone: PHONE, ownerName: "Akmal", password } });
}

describe("BO-21 onboarding model", () => {
  it("① sends the code, verifies it and only then opens ②", async () => {
    const { scope } = setup();
    await allSettled(pageMounted, { scope, params: { method: "phone" } });
    await allSettled(otpRequested, { scope, params: PHONE });
    expect(scope.getState($otp)).toMatchObject({
      challengeId: "ch-1",
      channel: "sms",
      telegramNotLinked: true,
      verified: false,
    });
    expect(scope.getState($resendAvailableAt)).toBe(61_000);
    expect(scope.getState($resendIn)).toBe(0); // one tick later

    // Not verified yet → «Davom» does nothing.
    await allSettled(accountSubmitted, {
      scope,
      params: { phone: PHONE, ownerName: "Akmal", password: "secret-pass" },
    });
    expect(scope.getState($step)).toBe("account");

    await allSettled(otpCodeSubmitted, { scope, params: "000000" });
    expect(scope.getState($otp)?.verified).toBe(false);
    await allSettled(otpCodeSubmitted, { scope, params: "123456" });
    expect(scope.getState($otp)?.verified).toBe(true);

    await allSettled(accountSubmitted, {
      scope,
      params: { phone: PHONE, ownerName: "Akmal", password: "secret-pass" },
    });
    expect(scope.getState($step)).toBe("store");
  });

  it("a different phone drops the sent code", async () => {
    const { scope } = setup();
    await allSettled(otpRequested, { scope, params: PHONE });
    await allSettled(phoneChanged, { scope, params: "901234567" });
    expect(scope.getState($otp)).not.toBeNull();
    await allSettled(phoneChanged, { scope, params: "901234568" });
    expect(scope.getState($otp)).toBeNull();
  });

  it("② signs up with the current terms version, then ③–⑥ and finish", async () => {
    const { scope, signupCalls, tracked } = setup();
    await passAccount(scope);
    await allSettled(storeSubmitted, { scope, params: STORE });

    expect(signupCalls).toEqual([
      {
        otp_challenge_id: "ch-1",
        password: "secret-pass",
        owner_name: "Akmal",
        store_name: "Baraka do'koni",
        business_type: "retail",
        legal_form: "llc",
        accepted_terms_version: "1.2",
        ai_cross_border_consent: true,
      },
    ]);
    expect(scope.getState($step)).toBe("products");
    expect(scope.getState($completed)).toEqual(["account", "store"]);
    expect(scope.getState($account)?.password).toBeNull();
    expect(tracked).toEqual(
      expect.arrayContaining(["onboarding_started", "terms_accepted", "consent.ai_cross_border_changed"]),
    );

    // ③ has no «Orqaga» (①② are closed once the tenant exists).
    await allSettled(backClicked, { scope });
    expect(scope.getState($step)).toBe("products");
    await allSettled(nextClicked, { scope });
    await allSettled(skipClicked, { scope }); // ④
    expect(scope.getState($step)).toBe("ofd");
    await allSettled(backClicked, { scope });
    expect(scope.getState($step)).toBe("debts");
    await allSettled(nextClicked, { scope });
    await allSettled(nextClicked, { scope });
    expect(scope.getState($step)).toBe("install");
    await allSettled(finishClicked, { scope });
    expect(scope.getState($finished)).toBe(true);
    expect(scope.getState($skipped)).toEqual(["debts"]);
    expect(tracked).toContain("onboarding_completed");
  });

  it("unchecked terms never call signup", async () => {
    const { scope, signupCalls } = setup();
    await passAccount(scope);
    await allSettled(storeSubmitted, { scope, params: { ...STORE, acceptTerms: false } });
    expect(signupCalls).toEqual([]);
    expect(scope.getState($step)).toBe("store");
  });

  it("Google path: no password in the body", async () => {
    const { scope, signupCalls } = setup();
    await passAccount(scope, null);
    expect(scope.getState($method)).toBe("google");
    await allSettled(storeSubmitted, { scope, params: STORE });
    expect(signupCalls[0]).not.toHaveProperty("password");
  });

  it("phone already registered → back to ① with a fresh code required", async () => {
    const { scope } = setup(() => Promise.reject(validation("phone", "validation.phone_taken")));
    await passAccount(scope);
    await allSettled(storeSubmitted, { scope, params: STORE });
    expect(scope.getState($step)).toBe("account");
    expect(scope.getState($signupFailure)).toBe("phone_taken");
    expect(scope.getState($otp)).toBeNull();
  });

  it("expired Google identity → phone path", async () => {
    const { scope } = setup(() => Promise.reject(validation("password", "validation.required")));
    await passAccount(scope, null);
    await allSettled(storeSubmitted, { scope, params: STORE });
    expect(scope.getState($signupFailure)).toBe("google_expired");
    expect(scope.getState($method)).toBe("phone");
    expect(scope.getState($step)).toBe("account");
  });

  it("outdated terms stay on ② and reload the version", async () => {
    const { scope } = setup(() =>
      Promise.reject(validation("accepted_terms_version", "validation.terms_version_not_current")),
    );
    await passAccount(scope);
    await allSettled(storeSubmitted, { scope, params: STORE });
    expect(scope.getState($step)).toBe("store");
    expect(scope.getState($signupFailure)).toBe("terms_outdated");
  });
});

describe("BO-21 lib", () => {
  it("classifies signup errors", () => {
    expect(
      classifySignupError(new ApiError({ status: 400, code: "OTP_INVALID", messageKey: "x" }), "phone"),
    ).toBe("otp_stale");
    expect(
      classifySignupError(new ApiError({ status: 429, code: "RATE_LIMITED", messageKey: "x" }), "phone"),
    ).toBe("general");
    expect(classifySignupError(validation("store_name", "validation.max_length"), "phone")).toBe("fields");
  });

  it("step states: done / current / optional / next", () => {
    const states = stepStates("store", ["account"], (id) => ({ title: id, description: "" })).map(
      (s) => s.state,
    );
    expect(states).toEqual(["done", "current", "next", "optional", "optional", "optional"]);
  });

  it("signup body trims names and omits the Google password", () => {
    const body = signupBody({
      account: { phone: PHONE, ownerName: "  Akmal ", password: null },
      store: { ...STORE, storeName: " Baraka " },
      challengeId: "c",
      termsVersion: "1",
    });
    expect(body).not.toHaveProperty("password");
    expect(body.owner_name).toBe("Akmal");
    expect(body.store_name).toBe("Baraka");
  });

  it("formats the resend countdown", () => {
    expect(formatCountdown(65)).toBe("1:05");
    expect(formatCountdown(0)).toBe("0:00");
  });
});

describe("BO-21 ③b opening stock (optional)", () => {
  it("method choice and posted lines add up; «Davom» on ③ does not wait for it", async () => {
    const scope = fork({ values: [[$step, "products"]] });
    await allSettled(openingStockMethodSelected, { scope, params: "manual" });
    expect(scope.getState($openingStockMethod)).toBe("manual");
    await allSettled(openingStockSaved, { scope, params: 3 });
    await allSettled(openingStockSaved, { scope, params: 2 });
    expect(scope.getState($openingStockLines)).toBe(5);
    await allSettled(openingStockMethodSelected, { scope, params: null });
    expect(scope.getState($openingStockMethod)).toBeNull();

    const fresh = fork({ values: [[$step, "products"]], handlers: [[trackFx, () => undefined]] });
    await allSettled(nextClicked, { scope: fresh });
    expect(fresh.getState($step)).toBe("debts");
    expect(fresh.getState($openingStockLines)).toBeNull();
  });
});
