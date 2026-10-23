import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * BO-14 Bosqich 3 parts (B3-SCR-BO-14) on the production build: «Fiskal» — registers' fiscal module
 * state and unsent receipts with «Qayta urinish» (18 §14.2, Idempotency-Key); «Xavfsizlik» — «Sinxron
 * istisnolari» with «Ko'rib chiqildi» + mandatory note (20 #40g); BO-12 «Terminalsiz karta» policy is
 * still saved through PATCH /tenant/settings (B1, qaror #71). Backend stubbed per test.
 */
const session = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["owner"],
  permissions: ["settings.tenant", "integrations.retry", "settings.branches", "reports.sales.view"],
  scope: ["settings", "integrations", "reports"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

type Body = Record<string, unknown>;

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

const tenantSettings = {
  name: "Baraka do'koni",
  legal_form: "llc",
  go_live_date: "2026-10-01",
  accepted_terms_version: "2026-01",
  accepted_terms_at: "2026-10-01T10:00:00Z",
  version: 3,
  settings: {
    bank_account: null,
    bank_mfo: null,
    supplier_overpay_policy: "warn",
    vat_diff_tolerance_amount: "1000.00",
    marking_precheck: "warn",
    discount_posting: "gross_9050",
    owner_withdrawal_account: "4890",
    payment_org_commission_account: "9430",
    turnover_tax_account: "9430",
    negative_stock_policy: "allow",
    ai_training_consent: false,
    ai_cross_border_enabled: false,
    card_manual_fallback: "manager_approval",
    fiscal_policy: { debt_receipt_split: "single", credit_sale_receipt: "none" },
  },
  tax_regime: { current: "vat", history: [{ regime: "vat", valid_from: "2026-10-01" }] },
  integrations: {
    ofd: { status: "connected" },
    faktura_uz: { status: "not_connected", connected_at: null },
    crpt: { status: "not_connected", key_last4: null },
    click: { status: "not_connected", connected_at: null },
    payme: { status: "not_connected", connected_at: null },
    uzum: { status: "not_connected", connected_at: null },
    uzqr: { status: "not_connected", connected_at: null, cash_register_ids: [] },
  },
};

function receipt(id: string, status: string, seq: number): Body {
  return {
    id,
    sale_id: "s-1",
    debt_payment_id: null,
    return_id: null,
    kind: "sale",
    status,
    receipt_seq: seq,
    fm_terminal_id: null,
    fm_receipt_seq: null,
    fiscal_sign: null,
    qr_url: null,
    payment_form: "cash",
    delivery: "printed",
    fiscal_at: null,
    ofd_acked_at: null,
    sent_at: null,
    offline_since: "2026-10-16T08:00:00Z",
    attempts: 3,
    cash_register_id: "cr-1",
    shift_id: "sh-1",
    created_at: "2026-10-16T08:00:00Z",
  };
}

function register(id: string, name: string, fm: string, unacked: string | null): Body {
  return {
    id,
    branch_id: "b-1",
    name,
    kind: "web",
    fiscal_module_id: null,
    txkm_contract_ref: null,
    fiscal_agent_id: null,
    fiscal_local_device_id: null,
    ofd_status: "active",
    fm_state: fm,
    last_unacked_receipt_at: unacked,
    fm_receipts_pending: null,
    tax_registered_at: null,
    archived_at: null,
    version: 1,
  };
}

function exception(id: string, kind: string, patch: Body = {}): Body {
  return {
    id,
    kind,
    device_id: "d-1",
    branch_id: "b-1",
    client_event_id: "e-1",
    doc_type: "sales",
    doc_id: "s-1",
    details: { secret_raw: "SHOULD-NOT-RENDER" },
    created_at: "2026-10-16T09:00:00Z",
    reviewed_at: null,
    reviewed_by: null,
    review_note: null,
    ...patch,
  };
}

async function stubBackend(page: Page) {
  const retries: { id: string; idempotencyKey: string | undefined }[] = [];
  const reviews: { id: string; body: Body }[] = [];
  const receiptQueries: (string | null)[] = [];
  let receipts = [receipt("f-1", "failed", 154), receipt("f-2", "pending", 155)];
  let exceptions = [exception("x-1", "price_mismatch"), exception("x-2", "late_in_closed_period")];

  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/auth/terms", (route) => json(route, 200, { items: [] }));
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/tenant/settings" && method === "GET") return json(route, 200, tenantSettings);
    if (path === "/api/v1/valuation-settings") {
      return json(route, 200, { costing_method: "aveco", pending_change: null, version: 1 });
    }
    if (path === "/api/v1/cash-registers") {
      return json(route, 200, {
        items: [
          register("cr-1", "Kassa 1", "ok", "2026-10-16T08:00:00Z"),
          register("cr-2", "Kassa 2", "locked", null),
        ],
      });
    }
    if (path === "/api/v1/fiscal-receipts" && method === "GET") {
      const status = url.searchParams.get("status");
      receiptQueries.push(status);
      return json(route, 200, {
        items: status ? receipts.filter((r) => r.status === status) : receipts,
        next_cursor: null,
      });
    }
    const retry = /^\/api\/v1\/fiscal-receipts\/(f-\d)\/retry$/.exec(path);
    if (retry && method === "POST") {
      const id = retry[1] ?? "";
      retries.push({ id, idempotencyKey: req.headers()["idempotency-key"] });
      receipts = receipts.map((r) => (r.id === id ? { ...r, status: "pending" } : r));
      return json(route, 200, { status: "requeued" });
    }
    if (path === "/api/v1/sync-exceptions" && method === "GET") {
      const reviewed = url.searchParams.get("reviewed");
      const items =
        reviewed === null
          ? exceptions
          : exceptions.filter((x) => (x.reviewed_at !== null) === (reviewed === "true"));
      return json(route, 200, { items, next_cursor: null });
    }
    const review = /^\/api\/v1\/sync-exceptions\/(x-\d)\/review$/.exec(path);
    if (review && method === "POST") {
      const id = review[1] ?? "";
      const body = req.postDataJSON() as Body;
      reviews.push({ id, body });
      const done = {
        id,
        reviewed_at: "2026-10-17T09:00:00Z",
        reviewed_by: "u-1",
        review_note: body.review_note,
      };
      exceptions = exceptions.map((x) => (x.id === id ? { ...x, ...done } : x));
      return json(route, 200, done);
    }
    if (path === "/api/v1/recost-jobs") return json(route, 200, { items: [], next_cursor: null });
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });
  return { retries, reviews, receiptQueries };
}

test("B3-SCR-BO-14 «Fiskal»: fiscal module state and «Qayta urinish» of an unsent receipt", async ({
  page,
}) => {
  const backend = await stubBackend(page);
  await page.goto("/app/settings/tenant?tab=fiscal");

  const card = page.getByRole("region", { name: "OFD ga yuborilmagan cheklar" });
  await expect(card).toContainText("Kassalar fiskal moduli: 2 ta, OFD tasdig'i kutilayotgani: 1 ta");
  await expect(card).toContainText("Bloklangan");
  expect(backend.receiptQueries[0]).toBe("failed");

  const table = card.getByRole("table", { name: "Fiskal cheklar" });
  const row = table.getByRole("row").filter({ hasText: "Sotuv #154" });
  await expect(row).toContainText("Kassa 1");
  await expect(row).toContainText("Yuborilmadi");
  await row.getByRole("button", { name: "Qayta urinish — Sotuv #154" }).click();
  await expect(row).toContainText("Navbatga qo'yildi");
  await expect(row.getByRole("button")).toHaveCount(0);
  expect(backend.retries).toHaveLength(1);
  expect(backend.retries[0]?.id).toBe("f-1");
  expect(backend.retries[0]?.idempotencyKey).toBeTruthy();

  // «Barcha holatlar» → no status filter.
  await card.getByRole("combobox", { name: "Holat" }).click();
  await page.getByRole("option", { name: "Barcha holatlar" }).click();
  await expect.poll(() => backend.receiptQueries.at(-1)).toBeNull();
  await expect(table.getByRole("row").filter({ hasText: "Sotuv #155" })).toContainText("Kutilmoqda");
});

test("B3-SCR-BO-14 «Sinxron istisnolari»: «Ko'rib chiqildi» needs a note; raw details are never shown", async ({
  page,
}) => {
  const backend = await stubBackend(page);
  await page.goto("/app/settings/tenant?tab=security");

  const card = page.getByRole("region", { name: "Sinxron istisnolari" });
  const table = card.getByRole("table", { name: "Sinxron istisnolari" });
  await expect(table.getByRole("row")).toHaveCount(3);
  await expect(card).not.toContainText("SHOULD-NOT-RENDER");
  const row = table.getByRole("row").filter({ hasText: "Narx farqi" });
  await expect(row).toContainText("Sotuv");
  await expect(row).toContainText("Chilonzor-3");

  await row.getByRole("button", { name: "Ko'rib chiqildi — Narx farqi" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Istisnoni ko'rib chiqildi deb belgilash" });
  await dialog.getByRole("button", { name: "Ko'rib chiqildi" }).click();
  await expect(dialog.getByText("Izoh majburiy (500 belgigacha)")).toBeVisible();
  expect(backend.reviews).toHaveLength(0);

  await dialog.getByLabel("Izoh").fill("Narx kassada kech yangilangan");
  await dialog.getByRole("button", { name: "Ko'rib chiqildi" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(table.getByRole("row").filter({ hasText: "Narx farqi" })).toHaveCount(0);
  expect(backend.reviews).toEqual([{ id: "x-1", body: { review_note: "Narx kassada kech yangilangan" } }]);

  await card.getByRole("combobox", { name: "Ko'rib chiqish" }).click();
  await page.getByRole("option", { name: "Ko'rib chiqilgan" }).click();
  await expect(table.getByRole("row").filter({ hasText: "Narx farqi" })).toContainText(
    "Narx kassada kech yangilangan",
  );
});
