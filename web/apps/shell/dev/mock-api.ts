/**
 * Dev-only stub of the BFF endpoints (`pnpm dev:mock`, ERP_API_MOCK=1) so the shell can be clicked
 * through without the backend. Mirrors packages/shared/api/openapi.json (backend schema).
 * Never part of the build (Vite `configureServer` only).
 *
 *   GET  /auth/login/start?return_to=…   → sets the session cookie, 302 to return_to (the real backend
 *                                          shows the AS login page in between, 14 §2.1)
 *   GET  /auth/login/start?return_to=…&mock=restricted → 302 /login?error=subscription_restricted
 *   GET  /auth/login/start?mock=denied   → 302 /login?error=authorization_denied
 */
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";

const COOKIE = "erp_mock_sid";
const CSRF = "dev-csrf";

const session = {
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
  permissions: [
    "accounting.post",
    "ai.chat.use",
    "bank_settlements.manage",
    "debts.payment.accept",
    "discount.approve",
    "expenses.create",
    "labels.print",
    "onec.view",
    "prices.edit",
    "purchases.create",
    "reports.finance.view",
    "reports.sales.view",
    "sales.create",
    "settings.tenant",
    "stock.view",
    "tax.compare.review",
  ],
  scope: [
    "accounting",
    "ai",
    "bank_settlements",
    "debts",
    "discount",
    "expenses",
    "labels",
    "onec",
    "prices",
    "purchases",
    "reports",
    "sales",
    "settings",
    "stock",
    "tax",
  ],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

function error(code: string, messageKey: string, params: Record<string, unknown> = {}) {
  return { error: { code, message_key: messageKey, params, details: [], request_id: "dev-mock" } };
}

function send(res: ServerResponse, status: number, body?: unknown, headers: Record<string, string> = {}) {
  res.statusCode = status;
  for (const [k, v] of Object.entries(headers)) res.setHeader(k, v);
  if (body === undefined) {
    res.end();
    return;
  }
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(body));
}

const redirect = (res: ServerResponse, location: string, cookie?: string) =>
  send(res, 302, undefined, { Location: location, ...(cookie ? { "Set-Cookie": cookie } : {}) });

const hasSession = (req: IncomingMessage) => (req.headers.cookie ?? "").includes(`${COOKIE}=1`);

/** Same rule as the backend `safe_return_to`. */
const safeReturnTo = (value: string | null) =>
  !value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\") ? "/" : value;

export function mockApi(): Plugin {
  return {
    name: "erp-dev-mock-api",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = new URL(req.url ?? "/", "http://dev.local");
        const path = url.pathname;
        const method = req.method ?? "GET";
        const isWrite = method !== "GET" && method !== "HEAD";

        if (method === "GET" && (path === "/health" || path === "/health/live" || path === "/health/ready")) {
          return send(res, 200, { status: "ok", checks: {} });
        }
        if (method === "GET" && path === "/api/v1/auth/csrf") return send(res, 200, { csrf_token: CSRF });
        if (method === "GET" && path === "/auth/login/start") {
          const mock = url.searchParams.get("mock");
          if (mock === "restricted") return redirect(res, "/login?error=subscription_restricted");
          if (mock === "denied") return redirect(res, "/login?error=authorization_denied");
          return redirect(
            res,
            safeReturnTo(url.searchParams.get("return_to")),
            `${COOKIE}=1; Path=/; HttpOnly; SameSite=Lax`,
          );
        }
        if (path === "/auth/session" && method === "GET") {
          return hasSession(req)
            ? send(res, 200, session, { "Cache-Control": "no-store" })
            : send(res, 401, error("UNAUTHORIZED", "errors.unauthorized"));
        }
        if (isWrite && path === "/bff/switch-tenant") {
          // 14 §9: the dev mock has a single tenant → a switch elsewhere has no membership (403).
          if (req.headers["x-csrf-token"] !== CSRF) {
            return send(res, 403, error("CSRF_INVALID", "errors.csrf_invalid"));
          }
          if (!hasSession(req)) return send(res, 401, error("UNAUTHORIZED", "errors.unauthorized"));
          return send(res, 403, error("PERMISSION_DENIED", "errors.permission_denied"));
        }
        if (isWrite && (path === "/auth/logout" || path === "/auth/sessions/revoke-all")) {
          if (req.headers["x-csrf-token"] !== CSRF) {
            return send(res, 403, error("CSRF_INVALID", "errors.csrf_invalid"));
          }
          const clear = `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax`;
          return path === "/auth/logout"
            ? send(res, 204, undefined, { "Set-Cookie": clear })
            : send(res, 200, { sessions_revoked: 2 }, { "Set-Cookie": clear });
        }
        next();
      });
    },
  };
}
