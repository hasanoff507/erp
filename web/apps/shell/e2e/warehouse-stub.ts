/**
 * Shared backend stub for the BO-03 / BO-04 e2e specs (warehouse-*.spec.ts, purchases.spec.ts):
 * session with two branches (Chilonzor-3 chosen), warehouses, units, categories, product cards, and a
 * small router `on(method, pattern, handler)` for the screen's own endpoints. Every write is recorded
 * with its Idempotency-Key / X-CSRF-Token headers.
 */
import type { Page, Request, Route } from "@playwright/test";

export type Body = Record<string, unknown>;

export const BRANCHES = [
  { id: "b-1", name: "Chilonzor-3" },
  { id: "b-2", name: "Yunusobod-1" },
];

export const WAREHOUSES = [
  { id: "w-1", branch_id: "b-1", name: "Asosiy ombor", type: "store", inventory_account: "2920", version: 1 },
  {
    id: "w-2",
    branch_id: "b-2",
    name: "Yunusobod ombori",
    type: "store",
    inventory_account: "2920",
    version: 1,
  },
];

export function session(permissions: string[]): Body {
  return {
    user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
    tenant: { id: "t-1", name: "Baraka do'koni" },
    branches: BRANCHES,
    roles: ["owner"],
    permissions,
    scope: [...new Set(permissions.map((p) => p.split(".")[0] ?? ""))],
    client_id: "web-bff",
    sub_status: "active",
    access_expires_at: 0,
  };
}

export function product(id: string, name: string, patch: Body = {}): Body {
  return {
    id,
    name,
    name_ru: null,
    category_id: "c-1",
    unit_code: "pcs",
    mxik_code: null,
    package_code: null,
    vat_rate: "12.00",
    vat_exemption_code: null,
    is_marked: false,
    marking_group_code: null,
    is_weighed: false,
    min_stock: null,
    archived_at: null,
    version: 1,
    barcodes: [
      {
        id: `bc-${id}`,
        barcode: `47800123400${id.replace(/\D/g, "").padStart(2, "0")}`,
        kind: "ean13",
        units_per_barcode: "1.000",
      },
    ],
    current_price: null,
    current_cost: null,
    markup_pct: null,
    ...patch,
  };
}

export function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

export function apiError(route: Route, status: number, code: string, messageKey: string, params: Body = {}) {
  return json(route, status, { error: { code, message_key: messageKey, params, details: [] } });
}

export interface Write {
  method: string;
  path: string;
  body: Body | null;
  query: URLSearchParams;
  idempotencyKey: string | undefined;
  csrf: string | undefined;
}

type Handler = (ctx: {
  route: Route;
  request: Request;
  url: URL;
  match: RegExpExecArray;
  body: Body | null;
}) => Promise<void> | void;

export class Stub {
  readonly writes: Write[] = [];
  readonly queries: { path: string; query: URLSearchParams }[] = [];
  private readonly routes: { method: string; pattern: RegExp; handler: Handler }[] = [];

  constructor(
    private readonly permissions: string[],
    readonly products: Body[] = [],
  ) {}

  on(method: string, pattern: RegExp, handler: Handler): this {
    this.routes.push({ method, pattern, handler });
    return this;
  }

  writesTo(path: RegExp): Write[] {
    return this.writes.filter((w) => path.test(w.path));
  }

  async install(page: Page): Promise<void> {
    await page.addInitScript(() => window.localStorage.setItem("erp.branch", "b-1"));
    await page.route("**/auth/session", (route) => json(route, 200, session(this.permissions)));
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname;
      const method = request.method();
      if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
      const raw = request.postData();
      const body = raw ? (JSON.parse(raw) as Body | null) : null;
      if (method === "GET") this.queries.push({ path, query: url.searchParams });
      else {
        this.writes.push({
          method,
          path,
          body,
          query: url.searchParams,
          idempotencyKey: request.headers()["idempotency-key"],
          csrf: request.headers()["x-csrf-token"],
        });
      }
      for (const r of this.routes) {
        const match = r.method === method ? r.pattern.exec(path) : null;
        if (match) return r.handler({ route, request, url, match, body });
      }
      if (path === "/api/v1/warehouses") return json(route, 200, { items: WAREHOUSES });
      if (path === "/api/v1/units") {
        return json(route, 200, {
          items: [
            { code: "pcs", is_fractional: false },
            { code: "kg", is_fractional: true },
          ],
        });
      }
      if (path === "/api/v1/product-categories") {
        return json(route, 200, {
          items: [{ id: "c-1", name: "Bakaleya", parent_id: null, archived_at: null, version: 1 }],
          total: 1,
          page: 1,
          size: 200,
        });
      }
      const card = /^\/api\/v1\/products\/([^/]+)$/.exec(path);
      if (card && method === "GET") {
        const p = this.products.find((x) => x.id === card[1]);
        return p ? json(route, 200, p) : apiError(route, 404, "NOT_FOUND", "errors.not_found");
      }
      if (path === "/api/v1/products" && method === "GET") {
        const q = (url.searchParams.get("search") ?? "").toLowerCase();
        const items = this.products.filter((p) => String(p.name).toLowerCase().includes(q));
        return json(route, 200, { items, total: items.length, page: 1, size: 10 });
      }
      // Lists that are not part of a test answer empty (badges, KPI helpers).
      if (method === "GET") return json(route, 200, { items: [], next_cursor: null });
      return apiError(route, 404, "NOT_FOUND", "errors.not_found");
    });
  }
}
