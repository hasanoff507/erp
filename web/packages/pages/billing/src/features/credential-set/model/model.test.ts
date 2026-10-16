import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";

import {
  challengeFromLink,
  createCredentialSetModel,
  verifyBody,
  type CredentialFlowKind,
  type CredentialValues,
  type VerifyParams,
} from "./index.ts";

const CHALLENGE = "0192a0f0-0000-7000-8000-0000000000cc";

function setup(
  kinds: ("password" | "pin")[] | null,
  setResult: () => Promise<void> = () => Promise.resolve(),
  kind: CredentialFlowKind = "recovery",
) {
  const model = createCredentialSetModel(kind);
  const verified: VerifyParams[] = [];
  const requested: string[] = [];
  const saved: ({ token: string } & CredentialValues)[] = [];
  const scope = fork({
    handlers: [
      [
        model.requestOtpFx,
        (phone: string) => {
          requested.push(phone);
          return Promise.resolve({
            challenge_id: CHALLENGE,
            channel_used: "telegram" as const,
            expires_at: "x",
          });
        },
      ],
      [
        model.verifyOtpFx,
        (params: VerifyParams) => {
          verified.push(params);
          return params.code === "123456"
            ? Promise.resolve({
                challenge_id: CHALLENGE,
                purpose: "recovery" as const,
                verified: true,
                credential_token: "tok-0123456789abcdef",
                credential_kinds: kinds,
              })
            : Promise.reject(
                new ApiError({ status: 400, code: "OTP_INVALID", messageKey: "errors.otp_invalid" }),
              );
        },
      ],
      [
        model.setCredentialsFx,
        (params: { token: string } & CredentialValues) => {
          saved.push(params);
          return setResult();
        },
      ],
    ],
  });
  return { model, scope, requested, saved, verified };
}

describe("credential-set flow (/recover, /invite)", () => {
  it("phone → code → password → done", async () => {
    const { model, scope, requested, saved } = setup(["password"]);
    await allSettled(model.pageMounted, { scope, params: { challengeId: null } });
    expect(scope.getState(model.$stage)).toBe("phone");

    await allSettled(model.phoneSubmitted, { scope, params: "+998901234567" });
    expect(requested).toEqual(["+998901234567"]);
    expect(scope.getState(model.$stage)).toBe("code");

    await allSettled(model.codeSubmitted, { scope, params: "111111" });
    expect(scope.getState(model.$error)?.code).toBe("OTP_INVALID");
    expect(scope.getState(model.$stage)).toBe("code");

    await allSettled(model.codeSubmitted, { scope, params: "123456" });
    expect(scope.getState(model.$stage)).toBe("credentials");
    expect(scope.getState(model.$session)?.kinds).toEqual(["password"]);

    await allSettled(model.credentialsSubmitted, { scope, params: { password: "new-secret-1" } });
    expect(saved).toEqual([{ token: "tok-0123456789abcdef", password: "new-secret-1" }]);
    expect(scope.getState(model.$stage)).toBe("done");
    expect(scope.getState(model.$session)).toBeNull();
  });

  it("invite link: starts at the code; PIN allowed when the server says so", async () => {
    const { model, scope, requested } = setup(["password", "pin"]);
    await allSettled(model.pageMounted, { scope, params: { challengeId: CHALLENGE } });
    expect(scope.getState(model.$stage)).toBe("code");
    expect(scope.getState(model.$challenge)?.phone).toBeNull();
    await allSettled(model.codeSubmitted, { scope, params: "123456" });
    expect(scope.getState(model.$session)?.kinds).toEqual(["password", "pin"]);
    expect(requested).toEqual([]);
  });

  it("an expired credential session (401) restarts from the phone", async () => {
    const { model, scope } = setup(["password"], () =>
      Promise.reject(new ApiError({ status: 401, code: "UNAUTHORIZED", messageKey: "errors.unauthorized" })),
    );
    await allSettled(model.pageMounted, { scope, params: { challengeId: null } });
    await allSettled(model.phoneSubmitted, { scope, params: "+998901234567" });
    await allSettled(model.codeSubmitted, { scope, params: "123456" });
    await allSettled(model.credentialsSubmitted, { scope, params: { password: "new-secret-1" } });
    expect(scope.getState(model.$stage)).toBe("phone");
    expect(scope.getState(model.$sessionExpired)).toBe(true);
    expect(scope.getState(model.$error)).toBeNull();
  });

  it("a 422 keeps the form with the error", async () => {
    const { model, scope } = setup(["password"], () =>
      Promise.reject(
        new ApiError({
          status: 422,
          code: "VALIDATION_ERROR",
          messageKey: "errors.validation",
          details: [{ field: "password", messageKey: "validation.password_length" }],
        }),
      ),
    );
    await allSettled(model.pageMounted, { scope, params: { challengeId: null } });
    await allSettled(model.phoneSubmitted, { scope, params: "+998901234567" });
    await allSettled(model.codeSubmitted, { scope, params: "123456" });
    await allSettled(model.credentialsSubmitted, { scope, params: { password: "x" } });
    expect(scope.getState(model.$stage)).toBe("credentials");
    expect(scope.getState(model.$error)?.details[0]?.field).toBe("password");
  });

  it("/invite without a link: phone + code type + code → verify by phone and purpose", async () => {
    const { model, scope, requested, verified } = setup(["pin"], undefined, "invite");
    await allSettled(model.pageMounted, { scope, params: { challengeId: null } });
    expect(scope.getState(model.$stage)).toBe("invite");
    await allSettled(model.inviteCodeSubmitted, {
      scope,
      params: { phone: "+998901234567", purpose: "pin_reset", code: "123456" },
    });
    expect(verified).toEqual([{ phone: "+998901234567", purpose: "pin_reset", code: "123456" }]);
    expect(requested).toEqual([]);
    expect(scope.getState(model.$stage)).toBe("credentials");
    expect(scope.getState(model.$session)?.kinds).toEqual(["pin"]);
    // A restart returns to the invite form, not to a recovery phone step.
    await allSettled(model.restarted, { scope });
    expect(scope.getState(model.$stage)).toBe("invite");
  });

  it("/invite for an existing user: invite_accepted without a credential_token → accepted", async () => {
    const model = createCredentialSetModel("invite");
    const scope = fork({
      handlers: [
        [
          model.verifyOtpFx,
          () =>
            Promise.resolve({
              challenge_id: CHALLENGE,
              purpose: "invite" as const,
              verified: true,
              credential_token: null,
              credential_kinds: null,
              invite_accepted: true,
            }),
        ],
      ],
    });
    await allSettled(model.pageMounted, { scope, params: { challengeId: null } });
    await allSettled(model.inviteCodeSubmitted, {
      scope,
      params: { phone: "+998901234567", purpose: "invite", code: "123456" },
    });
    expect(scope.getState(model.$stage)).toBe("accepted");
    expect(scope.getState(model.$session)).toBeNull();
    expect(scope.getState(model.$error)).toBeNull();
  });

  it("a verified code with neither a credential_token nor invite_accepted keeps the form", async () => {
    const model = createCredentialSetModel("invite");
    const scope = fork({
      handlers: [
        [
          model.verifyOtpFx,
          () => Promise.resolve({ challenge_id: CHALLENGE, purpose: "signup" as const, verified: true }),
        ],
      ],
    });
    await allSettled(model.pageMounted, { scope, params: { challengeId: CHALLENGE } });
    await allSettled(model.codeSubmitted, { scope, params: "123456" });
    expect(scope.getState(model.$stage)).toBe("code");
  });

  it("429 RATE_LIMITED on verify stays on the form with the error", async () => {
    const model = createCredentialSetModel("invite");
    const scope = fork({
      handlers: [
        [
          model.verifyOtpFx,
          () =>
            Promise.reject(
              new ApiError({
                status: 429,
                code: "RATE_LIMITED",
                messageKey: "errors.rate_limited",
                params: { retry_after_s: 120 },
              }),
            ),
        ],
      ],
    });
    await allSettled(model.pageMounted, { scope, params: { challengeId: null } });
    await allSettled(model.inviteCodeSubmitted, {
      scope,
      params: { phone: "+998901234567", purpose: "invite", code: "123456" },
    });
    expect(scope.getState(model.$stage)).toBe("invite");
    expect(scope.getState(model.$error)?.code).toBe("RATE_LIMITED");
    expect(scope.getState(model.$error)?.params.retry_after_s).toBe(120);
  });

  it("sends exactly one OtpVerifyIn form", () => {
    expect(verifyBody({ challengeId: "c", code: "1" })).toEqual({ challenge_id: "c", code: "1" });
    expect(verifyBody({ phone: "+998901234567", purpose: "invite", code: "1" })).toEqual({
      phone: "+998901234567",
      purpose: "invite",
      code: "1",
    });
  });

  it("accepts only a UUID challenge from the link", () => {
    expect(challengeFromLink(CHALLENGE)).toBe(CHALLENGE);
    expect(challengeFromLink("abc")).toBeNull();
    expect(challengeFromLink(null)).toBeNull();
  });
});
