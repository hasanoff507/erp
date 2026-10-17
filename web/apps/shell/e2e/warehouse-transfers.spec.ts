import { expect, test, type Page } from "@playwright/test";

import { Stub, apiError, json, product, type Body } from "./warehouse-stub.ts";

/**
 * BO-03 «Ko'chirishlar» (07, 19 §13, US-M06-01…03, B2-T11) on the production build:
 * create → post (vehicle: e-TTN `pending_signature` → «E-TTN kutilmoqda») → send refused with
 * 409 ETTN_REQUIRED until the e-TTN is registered; the on-foot path sends right away (e-TTN
 * «Talab qilinmaydi»); the receiving branch accepts with a shortage (→ «Farq bilan»).
 */
const PERMISSIONS = ["stock.view", "transfer.create", "transfer.receive"];

function transfer(id: string, patch: Body = {}): Body {
  return {
    id,
    number: null,
    status: "draft",
    doc_date: "2026-10-16",
    branch_id: "b-1",
    from_branch_id: "b-1",
    to_branch_id: "b-2",
    from_warehouse_id: "w-1",
    to_warehouse_id: "w-2",
    transport_mode: "vehicle",
    vehicle_plate: null,
    driver_name: null,
    ettn_ref: null,
    ettn: null,
    is_overdue: false,
    comment: null,
    created_by: "u-1",
    created_at: "2026-10-16T05:00:00Z",
    posted_at: null,
    sent_at: null,
    sent_by: null,
    received_at: null,
    received_by: null,
    cancelled_at: null,
    cancel_reason: null,
    lines: [
      {
        id: "tl-1",
        line_no: 1,
        product_id: "p2",
        product_name: "Sut 2,5% 1 l",
        qty_sent: "5.000",
        qty_received: null,
        unit_cost: null,
        lot_allocations: [],
      },
    ],
    warnings: [],
    ...patch,
  };
}

interface State {
  transfers: Body[];
  /** 409 TRANSFER_COST_PENDING on receive (the sender's cost is not known yet). */
  costPending: boolean;
  /** e-TTN status served by GET /transfers/{id} (the fake operator registers it in the background). */
  ettn: string;
  /** Status the server checks on send (lags behind the GET in the race test). */
  ettnOnSend: string;
}

function stub(initial: Body[] = []) {
  const state: State = {
    transfers: initial,
    costPending: false,
    ettn: "pending_signature",
    ettnOnSend: "sending",
  };
  const s = new Stub(PERMISSIONS, [product("p2", "Sut 2,5% 1 l")]);
  const save = (t: Body) => {
    state.transfers = [t, ...state.transfers.filter((x) => x.id !== t.id)];
    return t;
  };
  const find = (id: string | undefined) => state.transfers.find((t) => t.id === id) ?? transfer(id ?? "");
  const withEttn = (t: Body) =>
    t.transport_mode === "vehicle" && t.status === "posted"
      ? {
          ...t,
          ettn: {
            id: "e-1",
            status: state.ettn,
            operator_doc_id: state.ettn === "registered" ? "TTN-77" : null,
          },
        }
      : t;

  s.on("GET", /^\/api\/v1\/stock-balances$/, ({ route, url }) =>
    json(route, 200, {
      items: url.searchParams.get("product_id")
        ? [
            {
              product_id: "p2",
              product_name: "Sut 2,5% 1 l",
              warehouse_id: "w-1",
              qty: "12.000",
              value: "0.00",
              avg_cost: null,
              min_stock: null,
              is_low: false,
              is_negative: false,
              updated_at: null,
            },
          ]
        : [],
      next_cursor: null,
    }),
  )
    .on("GET", /^\/api\/v1\/transfers$/, ({ route, url }) => {
      const status = url.searchParams.get("status");
      const items = state.transfers.map(withEttn).filter((t) => !status || t.status === status);
      return json(route, 200, { items, next_cursor: null });
    })
    .on("GET", /^\/api\/v1\/transfers\/([^/]+)$/, ({ route, match }) =>
      json(route, 200, withEttn(find(match[1]))),
    )
    .on("POST", /^\/api\/v1\/transfers$/, ({ route, body }) =>
      json(
        route,
        201,
        save(
          transfer("t-1", {
            transport_mode: body?.transport_mode,
            vehicle_plate: body?.vehicle_plate ?? null,
            lines: [
              { ...(transfer("x").lines as Body[])[0], qty_sent: (body?.lines as Body[])[0]?.qty_sent },
            ],
          }),
        ),
      ),
    )
    .on("POST", /^\/api\/v1\/transfers\/([^/]+)\/post$/, ({ route, match }) =>
      json(route, 200, withEttn(save({ ...find(match[1]), status: "posted", number: "KO-000090" }))),
    )
    .on("POST", /^\/api\/v1\/transfers\/([^/]+)\/send$/, ({ route, match }) => {
      const t = find(match[1]);
      if (t.transport_mode === "vehicle" && state.ettnOnSend !== "registered") {
        return apiError(route, 409, "ETTN_REQUIRED", "errors.ettn_required", {
          ettn_status: state.ettnOnSend,
        });
      }
      return json(
        route,
        200,
        save({
          ...withEttn(t),
          status: "sent",
          sent_at: "2026-10-16T10:00:00Z",
          lines: [{ ...(t.lines as Body[])[0], unit_cost: "11200.0000" }],
        }),
      );
    })
    .on("POST", /^\/api\/v1\/transfers\/([^/]+)\/receive$/, ({ route, match, body }) => {
      if (state.costPending) {
        return apiError(route, 409, "TRANSFER_COST_PENDING", "errors.transfer_cost_pending");
      }
      const t = find(match[1]);
      const qty = ((body?.lines as Body[])[0]?.qty_received as string) ?? "0";
      const line: Body = { ...(t.lines as Body[])[0], qty_received: qty };
      const status = qty === line.qty_sent ? "received" : "discrepancy";
      return json(route, 200, save({ ...t, status, received_at: "2026-10-16T12:00:00Z", lines: [line] }));
    });
  return { s, state };
}

async function createTransfer(page: Page, mode: "vehicle" | "on_foot") {
  await page.goto("/app/warehouse/stock");
  await page.getByRole("button", { name: "Ko'chirish", exact: true }).click();
  const sheet = page.getByRole("dialog", { name: "Ko'chirish" });
  await sheet.getByRole("combobox", { name: "Manzil ombor" }).click();
  await page.getByRole("option", { name: "Yunusobod-1 — Yunusobod ombori" }).click();
  if (mode === "vehicle") await sheet.getByLabel("Avtomobil raqami").fill("01a245bc");
  else await sheet.getByRole("button", { name: "Piyoda yoki jamoat transporti" }).click();
  await sheet.getByRole("button", { name: "Tovar qo'shish" }).click();
  await page.getByRole("searchbox", { name: "Tovar qidirish" }).fill("Sut");
  await page.getByRole("button", { name: /Sut 2,5% 1 l/ }).click();
  await expect(sheet.getByText("Manbada qoldiq: 12 dona")).toBeVisible();
  await sheet.getByLabel("Miqdor — Sut 2,5% 1 l").fill("5");
  await sheet.getByRole("button", { name: "O'tkazish" }).click();
  await expect(sheet).toBeHidden();
}

test("B2-T11: vehicle transfer — post → e-TTN pending → ETTN_REQUIRED → registered → send", async ({
  page,
}) => {
  const { s, state } = stub();
  await s.install(page);
  await createTransfer(page, "vehicle");

  const create = s.writesTo(/^\/api\/v1\/transfers$/)[0];
  expect(create?.body).toMatchObject({
    from_warehouse_id: "w-1",
    to_warehouse_id: "w-2",
    transport_mode: "vehicle",
    vehicle_plate: "01A245BC",
    lines: [{ product_id: "p2", qty_sent: "5.000" }],
  });
  expect(create?.idempotencyKey).toBeTruthy();
  expect(create?.csrf).toBe("csrf-e2e");

  // The list tab opens with the posted transfer; e-TTN waits for signing.
  const table = page.getByRole("table", { name: "Ko'chirishlar" });
  const row = table.getByRole("row").filter({ hasText: "KO-000090" });
  await expect(row).toContainText("O'tkazildi");
  await expect(row).toContainText("Imzo kutilmoqda");
  await expect(row).toContainText("Chilonzor-3 → Yunusobod-1");
  await row.click();
  const detail = page.getByRole("dialog", { name: "KO-000090" });
  await expect(detail.getByText(/E-TTN imzo va ro'yxatdan o'tishi kutilmoqda/)).toBeVisible();
  await expect(detail.getByRole("button", { name: "Jo'natish" })).toHaveCount(0);

  // The GET already says «registered» but the operator answer lags: send → 409 ETTN_REQUIRED.
  state.ettn = "registered";
  await detail.getByRole("button", { name: "Yangilash" }).click();
  await detail.getByRole("button", { name: "Jo'natish" }).click();
  await page
    .getByRole("alertdialog", { name: "Yukni jo'natasizmi?" })
    .getByRole("button", { name: "Jo'natish" })
    .click();
  await expect(
    detail.getByText(/E-TTN ro'yxatdan o'tmaguncha jo'natib bo'lmaydi \(holati: Yuborilmoqda\)/),
  ).toBeVisible();

  state.ettnOnSend = "registered";
  await detail.getByRole("button", { name: "Jo'natish" }).click();
  await page
    .getByRole("alertdialog", { name: "Yukni jo'natasizmi?" })
    .getByRole("button", { name: "Jo'natish" })
    .click();
  await expect(detail.getByText("Yo'lda")).toBeVisible();
  const sends = s.writesTo(/\/transfers\/t-1\/send$/);
  expect(sends).toHaveLength(2);
  expect(sends[0]?.idempotencyKey).not.toBe(sends[1]?.idempotencyKey);
});

test("B2-T11: on foot — no e-TTN, «Jo'natish» right after posting", async ({ page }) => {
  const { s } = stub();
  await s.install(page);
  await createTransfer(page, "on_foot");
  expect(s.writesTo(/^\/api\/v1\/transfers$/)[0]?.body).toMatchObject({
    transport_mode: "on_foot_or_public",
    vehicle_plate: null,
  });
  const row = page
    .getByRole("table", { name: "Ko'chirishlar" })
    .getByRole("row")
    .filter({ hasText: "KO-000090" });
  await expect(row).toContainText("Talab qilinmaydi");
  await row.getByRole("button", { name: "Qator amallari" }).click();
  await page.getByRole("menuitem", { name: "Jo'natish" }).click();
  await page
    .getByRole("alertdialog", { name: "Yukni jo'natasizmi?" })
    .getByRole("button", { name: "Jo'natish" })
    .click();
  await expect(row).toContainText("Yo'lda");
  await expect(row).toContainText(/56\s000/);
});

test("US-M06-02: the receiving branch accepts with a shortage → «Farq bilan»", async ({ page }) => {
  const incoming = transfer("t-9", {
    number: "KO-000088",
    status: "sent",
    from_branch_id: "b-2",
    to_branch_id: "b-1",
    from_warehouse_id: "w-2",
    to_warehouse_id: "w-1",
    is_overdue: true,
    sent_at: "2026-10-14T09:15:00Z",
    vehicle_plate: "01A245BC",
    ettn: { id: "e-9", status: "registered", operator_doc_id: "TTN-9" },
    lines: [
      {
        id: "tl-9",
        line_no: 1,
        product_id: "p2",
        product_name: "Shakar",
        qty_sent: "10.000",
        qty_received: null,
        unit_cost: "10400.0000",
        lot_allocations: [],
      },
    ],
  });
  const { s } = stub([incoming]);
  await s.install(page);
  await page.goto("/app/warehouse/stock?tab=transfers");
  // Tab badge: 1 in transit (overdue → red).
  await expect(page.getByRole("tab", { name: /Ko'chirishlar\s*1/ })).toBeVisible();
  const row = page
    .getByRole("table", { name: "Ko'chirishlar" })
    .getByRole("row")
    .filter({ hasText: "KO-000088" });
  await expect(row).toContainText("Kechikmoqda");
  await row.getByRole("button", { name: "Qator amallari" }).click();
  await page.getByRole("menuitem", { name: "Qabul qilish" }).click();

  const dialog = page.getByRole("dialog", { name: "Qabul qilish — KO-000088" });
  const qty = dialog.getByLabel("Qabul qilingan miqdor — Shakar");
  await expect(qty).toHaveValue("10");
  await qty.fill("12");
  await expect(dialog.getByText("0 dan yuborilgan miqdorgacha")).toBeVisible();
  await qty.fill("8");
  await expect(dialog.getByText("Jami kamomad: 2")).toBeVisible();
  await dialog.getByRole("button", { name: "Qabul qilish" }).click();
  await expect(
    page.getByText("Ko'chirish KO-000088 kamomad bilan qabul qilindi", { exact: true }),
  ).toBeVisible();
  await expect(row).toContainText("Farq bilan");
  expect(s.writesTo(/\/transfers\/t-9\/receive$/)[0]?.body).toEqual({
    lines: [{ transfer_line_id: "tl-9", qty_received: "8.000" }],
  });
});

test("receive refused with 409 TRANSFER_COST_PENDING — the reason is shown in the dialog", async ({
  page,
}) => {
  const incoming = transfer("t-7", {
    number: "KO-000087",
    status: "sent",
    from_branch_id: "b-2",
    to_branch_id: "b-1",
    from_warehouse_id: "w-2",
    to_warehouse_id: "w-1",
    transport_mode: "on_foot_or_public",
    sent_at: "2026-10-15T09:15:00Z",
  });
  const { s, state } = stub([incoming]);
  state.costPending = true;
  await s.install(page);
  await page.goto("/app/warehouse/stock?tab=transfers");
  const row = page
    .getByRole("table", { name: "Ko'chirishlar", exact: true })
    .getByRole("row")
    .filter({ hasText: "KO-000087" });
  await row.getByRole("button", { name: "Qator amallari" }).click();
  await page.getByRole("menuitem", { name: "Qabul qilish" }).click();
  const dialog = page.getByRole("dialog", { name: "Qabul qilish — KO-000087" });
  await dialog.getByRole("button", { name: "Qabul qilish" }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "Jo'natuvchi omborda tovar tannarxi hali aniqlanmagan",
  );
  await expect(dialog).toBeVisible();
  expect(s.writesTo(/\/transfers\/t-7\/receive$/)).toHaveLength(1);
});

test("WEB-13: «Ko'chirishlar va e-TTN» under «Qoldiq» — branch rows, receive, «Barcha ko'chirishlar»", async ({
  page,
}) => {
  const incoming = transfer("t-9", {
    number: "KO-000088",
    status: "sent",
    from_branch_id: "b-2",
    to_branch_id: "b-1",
    from_warehouse_id: "w-2",
    to_warehouse_id: "w-1",
    transport_mode: "on_foot_or_public",
    sent_at: "2026-10-14T09:15:00Z",
  });
  const shortage = transfer("t-8", {
    number: "KO-000086",
    status: "discrepancy",
    doc_date: "2026-10-12",
    lines: [{ ...(transfer("x").lines as Body[])[0], qty_received: "4.000", unit_cost: "11200.0000" }],
  });
  const foreign = transfer("t-5", { number: "KO-000050", from_branch_id: "b-2", to_branch_id: "b-3" });
  const { s } = stub([incoming, shortage, foreign]);
  await s.install(page);
  await page.goto("/app/warehouse/stock");

  const block = page.getByRole("region", { name: "Ko'chirishlar va e-TTN" });
  const table = block.getByRole("table", { name: "Oxirgi ko'chirishlar" });
  await expect(table.getByRole("row").filter({ hasText: "KO-000088" })).toContainText(
    "Yunusobod-1 → Chilonzor-3",
  );
  await expect(table).not.toContainText("KO-000050");
  const digestQuery = s.queries.find((q) => q.path === "/api/v1/transfers" && q.query.has("from"));
  expect(digestQuery?.query.get("from")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  // Only «Qabul qilish» / «Farqni ko'rish» — no signing / manual registration (Bosqich 5).
  await expect(block.getByRole("button", { name: /imzolash|ro'yxatga olish/i })).toHaveCount(0);
  await block.getByRole("button", { name: "KO-000086 — farqni ko'rish" }).click();
  await expect(page.getByRole("dialog", { name: "KO-000086" })).toContainText("Farq bilan");
  await page.keyboard.press("Escape");

  await block.getByRole("button", { name: "KO-000088 — qabul qilish" }).click();
  const dialog = page.getByRole("dialog", { name: "Qabul qilish — KO-000088" });
  await dialog.getByRole("button", { name: "Qabul qilish" }).click();
  await expect(page.getByText("Ko'chirish KO-000088 qabul qilindi", { exact: true })).toBeVisible();

  await block.getByRole("button", { name: "Barcha ko'chirishlar" }).click();
  await expect(page.getByRole("tab", { name: /Ko'chirishlar/, selected: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "Ko'chirishlar", exact: true })).toBeVisible();
});
