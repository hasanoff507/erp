/**
 * Backend stub for the w-reports e2e specs (rep-*.spec.ts): a session with two branches (the topbar
 * branch is set through `erp.branch`, "all" = «Barcha filiallar»), a small `on(method, pattern)` router,
 * GET query log, write log (Idempotency-Key / CSRF) and a CSP-violation collector (24 §4.4).
 */
import type { Page, Request, Route } from "@playwright/test";

export type Body = Record<string, unknown>;

export const BRANCHES = [
  { id: "b-1", name: "Chilonzor-3" },
  { id: "b-2", name: "Yunusobod-1" },
];

export function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

type Handler = (ctx: { route: Route; request: Request; url: URL; body: Body | null }) => Promise<void>;

export class RepStub {
  readonly queries: { path: string; query: URLSearchParams }[] = [];
  readonly writes: { method: string; path: string; body: Body | null; idempotencyKey?: string }[] = [];
  private readonly routes: { method: string; pattern: RegExp; handler: Handler }[] = [];

  constructor(
    private readonly permissions: string[],
    private readonly branch: string = "all",
  ) {}

  on(method: string, pattern: RegExp, handler: Handler): this {
    this.routes.push({ method, pattern, handler });
    return this;
  }

  queriesOf(path: string): URLSearchParams[] {
    return this.queries.filter((q) => q.path === path).map((q) => q.query);
  }

  async install(page: Page): Promise<void> {
    const branch = this.branch;
    await page.addInitScript((b) => window.localStorage.setItem("erp.branch", b), branch);
    await page.route("**/auth/session", (route) =>
      json(route, 200, {
        user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
        tenant: { id: "t-1", name: "Baraka do'koni" },
        branches: BRANCHES,
        roles: ["owner"],
        permissions: this.permissions,
        scope: [...new Set(this.permissions.map((p) => p.split(".")[0] ?? ""))],
        client_id: "web-bff",
        sub_status: "active",
        access_expires_at: 0,
      }),
    );
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname;
      const method = request.method();
      if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
      const raw = request.postData();
      const body = raw ? (JSON.parse(raw) as Body | null) : null;
      if (method === "GET") this.queries.push({ path, query: url.searchParams });
      else this.writes.push({ method, path, body, idempotencyKey: request.headers()["idempotency-key"] });
      for (const r of this.routes) {
        if (r.method === method && r.pattern.test(path)) return r.handler({ route, request, url, body });
      }
      if (method === "GET") return json(route, 200, { items: [], next_cursor: null });
      return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
    });
  }
}

/** Strict CSP (24 §4.4): any violation reported by the browser is collected. */
export function collectCspViolations(page: Page): string[] {
  const violations: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && /Content Security Policy/i.test(msg.text())) violations.push(msg.text());
  });
  page.on("pageerror", (err) => {
    if (/Content Security Policy/i.test(err.message)) violations.push(err.message);
  });
  return violations;
}

const NBSP = " ";
/** Money/number text as rendered (NBSP group separators). */
export const nb = (text: string) => text.replace(/ /g, NBSP);

export function alert(
  type: string,
  severity: string,
  count: number,
  amount: string | null,
  route: string,
): Body {
  return { type, message_key: `reports.alerts.${type}`, severity, count, amount, route };
}

export function salesRow(key: string, total: string, receipts = 10, label: string | null = null): Body {
  return {
    group_key: key,
    group_label: label,
    total_sales: total,
    gross_sales: total,
    returns_total: "0.00",
    receipt_count: receipts,
    avg_receipt: "50000.00",
  };
}
