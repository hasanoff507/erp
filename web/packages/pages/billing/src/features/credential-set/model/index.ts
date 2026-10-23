/**
 * Credential-set flow (14 §4.2, backend auth/api/signup.py + application/credentials.py) shared by
 * `/recover` (BO-01 «Parolni unutdim») and `/invite` («Taklif kodi bor»):
 *
 *   phone → POST /auth/otp/request {purpose: "recovery"} → code → POST /auth/otp/verify
 *   → {credential_token, credential_kinds} → POST /auth/credentials {credential_token, password?, pin?}
 *   → 204 → normal login (no tokens are ever returned here).
 *
 * Invite / owner-forced reset codes (`invite`, `admin_reset`, `pin_reset`) are sent by the server
 * (BO-11); `/invite` verifies them with `POST /auth/otp/verify {phone, purpose, code}` (the latest
 * open challenge for that phone + purpose) or, from a link, `{challenge_id, code}`. The password /
 * PIN form follows `credential_kinds`.
 *
 * An `invite` for a phone that already has a password/PIN activates the membership without a
 * credential session (`invite_accepted: true`, `credential_token` = null, 14 §4.2) → stage
 * `accepted`: the user signs in with their existing password. `429 RATE_LIMITED` (+ `retry_after_s`)
 * on verify stays on the form as `$error` (14 §12).
 *
 * A factory: each page owns an independent instance (module-level, created once).
 */
import { combine, createEffect, createEvent, createStore, sample } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";
import type { OtpRequestOut, OtpVerifyIn, OtpVerifyOut } from "@shared/models";


export type CredentialFlowKind = "recovery" | "invite";
/**
 * `invite` = phone + code type + code on one form (/invite without a link); `accepted` = an existing
 * user's invite was accepted without a credential session (sign in with the existing password).
 */
export type CredentialStage = "phone" | "code" | "invite" | "credentials" | "done" | "accepted";
/** «Kod turi»: who sent the code (BO-11): invitation, owner password reset, owner PIN reset. */
export type InviteCodePurpose = "invite" | "admin_reset" | "pin_reset";
export const INVITE_CODE_PURPOSES: readonly InviteCodePurpose[] = ["invite", "admin_reset", "pin_reset"];

export type VerifyParams =
  { challengeId: string; code: string } | { phone: string; purpose: InviteCodePurpose; code: string };

/** Exactly one form of OtpVerifyIn (a mix is 422 server-side). */
export function verifyBody(params: VerifyParams): OtpVerifyIn {
  return "challengeId" in params
    ? { challenge_id: params.challengeId, code: params.code }
    : { phone: params.phone, purpose: params.purpose, code: params.code };
}
export type CredentialKind = "password" | "pin";

export interface CredentialChallenge {
  challengeId: string;
  /** E.164, `null` when the challenge came from an invite link. */
  phone: string | null;
  channel: OtpRequestOut["channel_used"] | null;
  telegramNotLinked: boolean;
}

export interface CredentialSession {
  token: string;
  kinds: readonly CredentialKind[];
}

export interface CredentialValues {
  password?: string;
  pin?: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** `?challenge_id=` from an invite link — only a UUID is accepted. */
export function challengeFromLink(value: string | null): string | null {
  return value && UUID.test(value) ? value : null;
}

/** What `/auth/otp/verify` allows; defaults to password (recovery). */
export function allowedKinds(result: OtpVerifyOut): CredentialKind[] {
  const kinds = result.credential_kinds ?? [];
  return kinds.length > 0 ? [...kinds] : ["password"];
}

function hasCredentialToken(result: OtpVerifyOut): boolean {
  return typeof result.credential_token === "string" && result.credential_token !== "";
}

export function createCredentialSetModel(kind: CredentialFlowKind) {
  const pageMounted = createEvent<{ challengeId: string | null }>();
  const phoneSubmitted = createEvent<string>();
  const resendRequested = createEvent();
  const codeSubmitted = createEvent<string>();
  /** /invite without a link: phone (E.164) + code type + the 6 digits from the message. */
  const inviteCodeSubmitted = createEvent<{ phone: string; purpose: InviteCodePurpose; code: string }>();
  const credentialsSubmitted = createEvent<CredentialValues>();
  const restarted = createEvent();

  const requestOtpFx = createEffect<string, OtpRequestOut, ApiError>(async (phone) => {
    try {
      return await api.auth.otpRequest({ phone, purpose: "recovery" }, { erpPublic: true });
    } catch (error) {
      throw toApiError(error);
    }
  });
  const verifyOtpFx = createEffect<VerifyParams, OtpVerifyOut, ApiError>(async (params) => {
    try {
      return await api.auth.otpVerify(verifyBody(params), { erpPublic: true });
    } catch (error) {
      throw toApiError(error);
    }
  });
  const setCredentialsFx = createEffect<{ token: string } & CredentialValues, void, ApiError>(
    async ({ token, password, pin }) => {
      try {
        await api.auth.credentialsSet(
          { credential_token: token, ...(password ? { password } : {}), ...(pin ? { pin } : {}) },
          { erpPublic: true },
        );
      } catch (error) {
        throw toApiError(error);
      }
    },
  );

  const startStage: CredentialStage = kind === "invite" ? "invite" : "phone";
  const $stage = createStore<CredentialStage>(startStage);
  const $challenge = createStore<CredentialChallenge | null>(null);
  const $session = createStore<CredentialSession | null>(null);
  const $error = createStore<ApiError | null>(null);
  /** The credential session expired / was used (401) — the flow restarted from the phone. */
  const $sessionExpired = createStore(false);
  const $pending = combine(
    requestOtpFx.pending,
    verifyOtpFx.pending,
    setCredentialsFx.pending,
    (a, b, c) => a || b || c,
  );

  // Mount: an invite link carries the challenge (the user only types the code); otherwise the phone.
  sample({
    clock: pageMounted,
    fn: ({ challengeId }): CredentialChallenge | null =>
      challengeId === null ? null : { challengeId, phone: null, channel: null, telegramNotLinked: false },
    target: $challenge,
  });
  sample({
    clock: pageMounted,
    fn: ({ challengeId }): CredentialStage => (challengeId === null ? startStage : "code"),
    target: $stage,
  });
  sample({ clock: pageMounted, fn: () => null, target: $session });

  sample({ clock: phoneSubmitted, target: requestOtpFx });
  sample({
    clock: inviteCodeSubmitted,
    filter: ({ code }) => code.length === 6,
    target: verifyOtpFx,
  });
  sample({
    clock: resendRequested,
    source: $challenge,
    filter: (challenge) => challenge?.phone != null,
    fn: (challenge) => challenge?.phone ?? "",
    target: requestOtpFx,
  });
  sample({
    clock: requestOtpFx.done,
    fn: ({ params, result }): CredentialChallenge => ({
      challengeId: result.challenge_id,
      phone: params,
      channel: result.channel_used,
      telegramNotLinked: (result.warnings ?? []).some((w) => w.code === "TELEGRAM_NOT_LINKED"),
    }),
    target: $challenge,
  });
  sample({ clock: requestOtpFx.done, fn: () => "code" as const, target: $stage });

  sample({
    clock: codeSubmitted,
    source: $challenge,
    filter: (challenge, code) => challenge !== null && code.length === 6,
    fn: (challenge, code) => ({ challengeId: challenge?.challengeId ?? "", code }),
    target: verifyOtpFx,
  });
  // signup/data_export codes never open a credential session; treat that as a wrong code.
  const verified = sample({
    clock: verifyOtpFx.doneData,
    filter: hasCredentialToken,
  });
  // An existing user's invite: membership active, credentials unchanged → sign in as usual (14 §4.2).
  sample({
    clock: verifyOtpFx.doneData,
    filter: (result) => result.invite_accepted === true && !hasCredentialToken(result),
    fn: () => "accepted" as const,
    target: $stage,
  });
  sample({
    clock: verified,
    fn: (result): CredentialSession => ({
      token: result.credential_token ?? "",
      kinds: allowedKinds(result),
    }),
    target: $session,
  });
  sample({ clock: verified, fn: () => "credentials" as const, target: $stage });

  sample({
    clock: credentialsSubmitted,
    source: $session,
    filter: (session) => session !== null,
    fn: (session, values) => ({ token: session?.token ?? "", ...values }),
    target: setCredentialsFx,
  });
  sample({ clock: setCredentialsFx.done, fn: () => "done" as const, target: $stage });
  sample({ clock: setCredentialsFx.done, fn: () => null, target: $session });

  // 401 credential_token_invalid: expired (ERP_CREDENTIAL_TOKEN_TTL_S) or already used → start over.
  const expired = sample({ clock: setCredentialsFx.failData, filter: (error) => error.status === 401 });
  sample({ clock: [expired, restarted], fn: () => startStage, target: $stage });
  sample({ clock: [expired, restarted], fn: () => null, target: [$challenge, $session] });
  $sessionExpired.on(expired, () => true).reset(requestOtpFx, restarted, pageMounted);

  $error
    .on([requestOtpFx.failData, verifyOtpFx.failData], (_, error) => error)
    .on(setCredentialsFx.failData, (_, error) => (error.status === 401 ? null : error))
    .reset(requestOtpFx, verifyOtpFx, setCredentialsFx, restarted, pageMounted);

  return {
    kind,
    pageMounted,
    phoneSubmitted,
    resendRequested,
    codeSubmitted,
    inviteCodeSubmitted,
    credentialsSubmitted,
    restarted,
    $stage,
    $challenge,
    $session,
    $error,
    $sessionExpired,
    $pending,
    requestOtpFx,
    verifyOtpFx,
    setCredentialsFx,
  };
}

export type CredentialSetModel = ReturnType<typeof createCredentialSetModel>;
