/**
 * BO-21 wizard flow — sample() wiring only (24 §2).
 *
 * ① phone → POST /auth/otp/request (signup) → POST /auth/otp/verify → password + name (Google path:
 * no password, the pending Google identity cookie stands in for it, 14 §2.2/§20);
 * ② store → POST /auth/signup: the tenant is created right here (before ③–⑥) and the response sets
 * the `__Host-sid` cookie, so the session is re-read and ③–⑥ run as the new owner;
 * ③–⑥ are navigation only in Bosqich 1 (import is embedded; ④–⑥ may be skipped).
 */
import { sample } from "effector";
import { interval } from "patronum";

import { toE164 } from "@shared/lib/phone";
import { $authStatus, sessionCheckRequested } from "@shared/state/session";

import { postDraftFx as openingStockPostFx } from "#/features/opening-stock/model/index.ts";

import {
  loadTermsFx,
  readClockFx,
  requestOtpFx,
  resetCsrfFx,
  signupFx,
  stampResendFx,
  trackFx,
  verifyOtpFx,
} from "../effects/index.ts";
import {
  accountSubmitted,
  backClicked,
  connectNowToggled,
  countdownTicked,
  finishClicked,
  methodSelected,
  nextClicked,
  openingStockMethodSelected,
  openingStockSaved,
  otpCodeSubmitted,
  otpRequested,
  pageMounted,
  phoneChanged,
  productsImported,
  productsMethodSelected,
  skipClicked,
  stepEditRequested,
  storeDraftChanged,
  storeSubmitted,
  termsReloadRequested,
} from "../events/index.ts";
import { classifySignupError, isAccountFailure, nextStep, previousStep, signupBody } from "../lib/index.ts";
import {
  $account,
  $completed,
  $connectNow,
  $finished,
  $importedCount,
  $method,
  $now,
  $openingStockLines,
  $openingStockMethod,
  $otp,
  $otpError,
  $productsMethod,
  $resendAvailableAt,
  $resendIn,
  $signup,
  $signupError,
  $signupFailure,
  $skipped,
  $step,
  $storeDraft,
  $terms,
  $termsError,
  $termsVersion,
} from "../stores/index.ts";
import { PRE_SIGNUP_STEPS, RESEND_COOLDOWN_S, type StepId } from "../types/index.ts";

const addStep = (list: readonly StepId[], step: StepId): readonly StepId[] =>
  list.includes(step) ? list : [...list, step];

// --- mount ------------------------------------------------------------------------------------------
sample({ clock: pageMounted, fn: ({ method }) => method, target: $method });
sample({ clock: pageMounted, fn: () => ({ event: "onboarding_started" as const }), target: trackFx });
sample({ clock: [pageMounted, termsReloadRequested], fn: () => undefined, target: loadTermsFx });
$terms.on(loadTermsFx.doneData, (_, result) => result.items);
$termsError.on(loadTermsFx.failData, (_, error) => error).reset(loadTermsFx);

// Already signed in (reload on ③–⑥, or back from the product form) → continue at ③.
sample({
  clock: [pageMounted, $authStatus.updates],
  source: { status: $authStatus, step: $step, completed: $completed, otp: $otp, pending: signupFx.pending },
  filter: ({ status, step, completed, otp, pending }) =>
    status === "authenticated" && step === "account" && completed.length === 0 && otp === null && !pending,
  fn: () => "products" as const,
  target: $step,
});
sample({
  clock: $step.updates,
  source: $completed,
  filter: (completed, step) => step === "products" && completed.length === 0,
  fn: (): readonly StepId[] => [...PRE_SIGNUP_STEPS],
  target: $completed,
});

sample({ clock: methodSelected, target: $method });

// --- ① phone + code ---------------------------------------------------------------------------------
sample({
  clock: phoneChanged,
  source: $otp,
  filter: (otp, digits) => otp !== null && otp.phone !== toE164(digits),
  fn: () => null,
  target: [$otp, $resendAvailableAt],
});

sample({ clock: otpRequested, target: requestOtpFx });
$otpError.on([requestOtpFx.failData, verifyOtpFx.failData], (_, error) => error);
$otpError.reset(requestOtpFx, verifyOtpFx, phoneChanged);

sample({
  clock: requestOtpFx.done,
  fn: ({ params, result }) => ({
    challengeId: result.challenge_id,
    phone: params,
    channel: result.channel_used,
    expiresAt: result.expires_at,
    telegramNotLinked: (result.warnings ?? []).some((w) => w.code === "TELEGRAM_NOT_LINKED"),
    verified: false,
  }),
  target: $otp,
});

// Resend countdown (14 §12 limits stay server-side; this only prevents double sends).
sample({ clock: requestOtpFx.done, fn: () => RESEND_COOLDOWN_S, target: stampResendFx });
sample({ clock: stampResendFx.doneData, target: $resendAvailableAt });
sample({
  clock: stampResendFx.doneData,
  fn: (availableAt) => availableAt - RESEND_COOLDOWN_S * 1000,
  target: $now,
});
const countdown = interval({
  timeout: 1000,
  start: stampResendFx.done,
  stop: $resendIn.updates.filter({ fn: (seconds) => seconds === 0 }),
});
sample({ clock: countdown.tick, target: readClockFx });
sample({ clock: readClockFx.doneData, target: countdownTicked });
sample({ clock: countdownTicked, target: $now });

sample({
  clock: otpCodeSubmitted,
  source: $otp,
  filter: (otp, code) => otp !== null && !otp.verified && code.length === 6,
  fn: (otp, code) => ({ challengeId: otp?.challengeId ?? "", code }),
  target: verifyOtpFx,
});
sample({
  clock: verifyOtpFx.done,
  source: $otp,
  filter: (otp, { params }) => otp?.challengeId === params.challengeId,
  fn: (otp) => (otp ? { ...otp, verified: true } : null),
  target: $otp,
});

sample({
  clock: accountSubmitted,
  source: $otp,
  filter: (otp, account) => otp !== null && otp.verified && otp.phone === account.phone,
  fn: (_, account) => account,
  target: $account,
});
sample({
  clock: accountSubmitted,
  source: $otp,
  filter: (otp, account) => otp !== null && otp.verified && otp.phone === account.phone,
  fn: () => "store" as const,
  target: $step,
});

// --- ② store → POST /auth/signup --------------------------------------------------------------------
sample({ clock: [storeDraftChanged, storeSubmitted], target: $storeDraft });
sample({
  clock: storeSubmitted,
  source: { account: $account, otp: $otp, terms: $termsVersion, pending: signupFx.pending },
  filter: ({ account, otp, terms, pending }, store) =>
    account !== null && otp?.verified === true && terms !== null && store.acceptTerms && !pending,
  fn: ({ account, otp, terms }, store) =>
    signupBody({
      // the filter above guarantees every value
      account: account ?? { phone: "", ownerName: "", password: null },
      store,
      challengeId: otp?.challengeId ?? "",
      termsVersion: terms?.version ?? "",
    }),
  target: signupFx,
});
$signupError.on(signupFx.failData, (_, error) => error).reset(signupFx, accountSubmitted, otpRequested);
$signupFailure.reset(signupFx, accountSubmitted, otpRequested);
sample({
  clock: signupFx.failData,
  source: $method,
  fn: (method, error) => classifySignupError(error, method),
  target: $signupFailure,
});

// The failure belongs to ①: back to it; a stale or taken phone needs a new code.
sample({
  clock: signupFx.failData,
  source: $method,
  filter: (method, error) => isAccountFailure(classifySignupError(error, method), error),
  fn: () => "account" as const,
  target: $step,
});
sample({
  clock: signupFx.failData,
  source: $method,
  filter: (method, error) => {
    const failure = classifySignupError(error, method);
    return failure === "otp_stale" || failure === "phone_taken";
  },
  fn: () => null,
  target: [$otp, $resendAvailableAt],
});
// Google pending identity expired → the phone path (a password is required now).
sample({
  clock: signupFx.failData,
  source: $method,
  filter: (method, error) => classifySignupError(error, method) === "google_expired",
  fn: () => "phone" as const,
  target: $method,
});
sample({
  clock: signupFx.failData,
  source: $method,
  filter: (method, error) => classifySignupError(error, method) === "terms_outdated",
  fn: () => undefined,
  target: termsReloadRequested,
});

sample({ clock: signupFx.doneData, target: $signup });
sample({
  clock: signupFx.done,
  source: $completed,
  fn: (completed) => addStep(addStep(completed, "account"), "store"),
  target: $completed,
});
sample({ clock: signupFx.done, fn: () => "products" as const, target: $step });
// The password is not kept once the account exists.
sample({
  clock: signupFx.done,
  source: $account,
  fn: (account) => (account ? { ...account, password: null } : null),
  target: $account,
});
sample({ clock: signupFx.done, fn: () => undefined, target: [resetCsrfFx, sessionCheckRequested] });
sample({
  clock: signupFx.done,
  fn: ({ params }) => ({
    event: "terms_accepted" as const,
    props: { version: params.accepted_terms_version },
  }),
  target: trackFx,
});
sample({
  clock: signupFx.done,
  filter: ({ params }) => params.ai_cross_border_consent === true,
  fn: () => ({ event: "consent.ai_cross_border_changed" as const, props: { accepted: "true" } }),
  target: trackFx,
});

// --- navigation ---------------------------------------------------------------------------------------
sample({
  clock: stepEditRequested,
  source: $step,
  filter: (step, target) => step === "store" && target === "account",
  fn: () => "account" as const,
  target: $step,
});

// ② → ①; after signup ①② are closed, so ③ has no «Orqaga».
sample({
  clock: backClicked,
  source: $step,
  filter: (step) => step !== "account" && step !== "products",
  fn: (step) => previousStep(step) ?? step,
  target: $step,
});

const advanced = sample({
  clock: nextClicked,
  source: $step,
  filter: (step) => step === "products" || step === "debts" || step === "ofd",
});
sample({ clock: advanced, source: $completed, fn: addStep, target: $completed });
sample({ clock: advanced, fn: (step) => nextStep(step) ?? step, target: $step });

const skipped = sample({
  clock: skipClicked,
  source: $step,
  filter: (step) => step === "debts" || step === "ofd" || step === "install",
});
sample({ clock: skipped, source: $skipped, fn: addStep, target: $skipped });
sample({
  clock: skipped,
  filter: (step) => step !== "install",
  fn: (step) => nextStep(step) ?? step,
  target: $step,
});
sample({
  clock: skipped,
  fn: (step) => ({ event: "onboarding_skipped_step" as const, props: { step } }),
  target: trackFx,
});

const finishedByClick = sample({ clock: finishClicked, source: $step, filter: (step) => step === "install" });
sample({ clock: finishedByClick, source: $completed, fn: addStep, target: $completed });
const finished = sample({
  clock: [finishedByClick, skipped.filter({ fn: (step) => step === "install" })],
});
sample({ clock: finished, fn: () => true, target: $finished });
sample({ clock: finished, fn: () => ({ event: "onboarding_completed" as const }), target: trackFx });

sample({
  clock: [advanced, finishedByClick],
  fn: (step) => ({ event: "onboarding_step_completed" as const, props: { step } }),
  target: trackFx,
});
sample({
  clock: signupFx.done,
  fn: () => ({ event: "onboarding_step_completed" as const, props: { step: "store" } }),
  target: trackFx,
});

// --- ③–⑤ local choices ------------------------------------------------------------------------------
sample({ clock: productsMethodSelected, target: $productsMethod });
sample({ clock: productsImported, target: $importedCount });
sample({ clock: connectNowToggled, target: $connectNow });

// --- ③b opening stock (optional; «Davom» never waits for it) -------------------------------------
sample({ clock: openingStockMethodSelected, target: $openingStockMethod });
$openingStockLines.on(openingStockSaved, (total, lines) => (total ?? 0) + lines);
// «Qo'lda»: a posted stock-opening document counts its lines.
sample({ clock: openingStockPostFx.doneData, fn: (doc) => doc.line_count, target: openingStockSaved });
