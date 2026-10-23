import { describe, expect, it } from "vitest";

import {
  isOnboardingReason,
  loginErrorReason,
  MAX_NEXT_LENGTH,
  safeNextPath,
  safeTenantId,
} from "./index.ts";

describe("BO-01 login helpers", () => {
  it("accepts only in-app next paths", () => {
    expect(safeNextPath("/app/debts?x=1")).toBe("/app/debts?x=1");
    expect(safeNextPath("/")).toBe("/");
    expect(safeNextPath("//evil.example")).toBeNull();
    expect(safeNextPath("/\\evil.example")).toBeNull();
    expect(safeNextPath("https://evil.example")).toBeNull();
    expect(safeNextPath("app/debts")).toBeNull();
    expect(safeNextPath("/login?error=x")).toBeNull();
    expect(safeNextPath("")).toBeNull();
    expect(safeNextPath(null)).toBeNull();
  });

  it("drops next longer than the backend return_to limit (2048)", () => {
    const max = `/app/${"a".repeat(MAX_NEXT_LENGTH - 5)}`;
    expect(max).toHaveLength(MAX_NEXT_LENGTH);
    expect(safeNextPath(max)).toBe(max);
    expect(safeNextPath(`${max}b`)).toBeNull();
  });

  it("forwards tenant_id only when it is a UUID", () => {
    expect(safeTenantId("0192a0f0-0000-7000-8000-0000000000aa")).toBe("0192a0f0-0000-7000-8000-0000000000aa");
    expect(safeTenantId("0192A0F0-0000-7000-8000-0000000000AA")).toBe("0192A0F0-0000-7000-8000-0000000000AA");
    expect(safeTenantId("t-1")).toBeNull();
    expect(safeTenantId("0192a0f0-0000-7000-8000-0000000000aa&return_to=//evil")).toBeNull();
    expect(safeTenantId(" 0192a0f0-0000-7000-8000-0000000000aa")).toBeNull();
    expect(safeTenantId("")).toBeNull();
    expect(safeTenantId(null)).toBeNull();
  });

  it("maps callback reasons to message keys; unknown reasons never leak", () => {
    expect(loginErrorReason("state_mismatch")).toBe("state_mismatch");
    expect(loginErrorReason("authorization_denied")).toBe("authorization_denied");
    expect(loginErrorReason("<script>")).toBe("default");
    expect(loginErrorReason("subscription_restricted")).toBeNull();
    expect(loginErrorReason(null)).toBeNull();
  });

  it("maps the Google callback reasons (14 §2.2) to the onboarding texts", () => {
    for (const reason of ["google_email_not_verified", "tenant_required"] as const) {
      expect(loginErrorReason(reason)).toBe(reason);
      expect(isOnboardingReason(reason)).toBe(true);
    }
    // Google unavailable / failed has its own BO-01 text (auth namespace).
    expect(loginErrorReason("google_auth_failed")).toBe("google_auth_failed");
    expect(isOnboardingReason("google_auth_failed")).toBe(false);
    expect(isOnboardingReason("state_mismatch")).toBe(false);
  });
});
