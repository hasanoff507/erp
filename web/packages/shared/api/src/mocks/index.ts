/**
 * MSW handlers for unit tests (32 §6.2: "msw — API mock, orval-generated functions are called,
 * not the real backend"). Shapes follow the backend OpenAPI (SessionInfo, CsrfToken, RevokeAllResult)
 * and the error envelope (17 §7.1). Test-only: never imported by application code.
 */
import { http, HttpResponse } from "msw";

import type { SessionInfo } from "@shared/models/generated";

export const mockSession: SessionInfo = {
  user: {
    id: "0192a0f0-0000-7000-8000-000000000001",
    full_name: "Akmal Karimov",
    phone_masked: "+998 90 *** ** 67",
  },
  tenant: { id: "0192a0f0-0000-7000-8000-0000000000aa", name: "Baraka do'koni" },
  branches: [
    { id: "0192a0f0-0000-7000-8000-0000000000b1", name: "Chilonzor-3" },
    { id: "0192a0f0-0000-7000-8000-0000000000b2", name: "Yunusobod-1" },
  ],
  roles: ["owner"],
  permissions: ["ai.chat.use", "reports.finance.view", "reports.sales.view", "sales.create", "stock.view"],
  scope: ["ai", "reports", "sales", "stock"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 1_792_000_000,
};

export function errorEnvelope(code: string, messageKey: string, params?: Record<string, unknown>) {
  return {
    error: { code, message_key: messageKey, params: params ?? {}, details: [], request_id: "test-request" },
  };
}

export type MockSessionState = "anonymous" | "active" | "restricted" | "no_membership";

export interface AuthMockState {
  session: MockSessionState;
  /** Headers of the last write request, for interceptor assertions. */
  lastWriteHeaders: Headers | null;
  /** When true the next write answers 403 CSRF_INVALID once (retry test). */
  rejectCsrfOnce: boolean;
}

export function createAuthState(): AuthMockState {
  return { session: "anonymous", lastWriteHeaders: null, rejectCsrfOnce: false };
}

/** Stateful handlers for the BFF auth endpoints, rooted at `base` (e.g. "http://api.test"). */
export function createAuthHandlers(base: string, state: AuthMockState = createAuthState()) {
  const write = (request: Request) => {
    state.lastWriteHeaders = request.headers;
    if (request.headers.get("x-csrf-token") !== "csrf-test-token" || state.rejectCsrfOnce) {
      state.rejectCsrfOnce = false;
      return HttpResponse.json(errorEnvelope("CSRF_INVALID", "errors.csrf_invalid"), { status: 403 });
    }
    return null;
  };

  return [
    http.get(`${base}/health`, () => HttpResponse.json({ status: "ok", checks: {} })),
    http.get(`${base}/api/v1/auth/csrf`, () => HttpResponse.json({ csrf_token: "csrf-test-token" })),
    http.get(`${base}/auth/session`, () => {
      if (state.session === "active") return HttpResponse.json(mockSession);
      if (state.session === "no_membership") {
        return HttpResponse.json(errorEnvelope("PERMISSION_DENIED", "errors.permission_denied"), {
          status: 403,
        });
      }
      if (state.session === "restricted") {
        return HttpResponse.json(
          errorEnvelope("SUBSCRIPTION_RESTRICTED", "errors.subscription_restricted", {
            pay_url: "https://pay.example/checkout/1",
            amount_due: "99000.00",
          }),
          { status: 403 },
        );
      }
      return HttpResponse.json(errorEnvelope("UNAUTHORIZED", "errors.unauthorized"), { status: 401 });
    }),
    http.post(`${base}/auth/logout`, ({ request }) => {
      const rejected = write(request);
      if (rejected) return rejected;
      state.session = "anonymous";
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(`${base}/auth/sessions/revoke-all`, ({ request }) => {
      const rejected = write(request);
      if (rejected) return rejected;
      state.session = "anonymous";
      return HttpResponse.json({ sessions_revoked: 3 });
    }),
  ];
}
