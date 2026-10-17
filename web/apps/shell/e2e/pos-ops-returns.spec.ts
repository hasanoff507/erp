/**
 * POS-05 returns (b3-pos-ops): receipt found online (`GET /sales?number=` → `/sales/{id}`), one line returned
 * for cash within the cashier's limit (QT-M02-03; VAT shown, US-M02-03), over the limit → Manager PIN
 * (QT-M02-04, `return_over_limit`), no receipt → always Manager/Owner PIN (QT-M02-02, `return_no_receipt`),
 * marked goods offline blocked (16 §7). `return.created` payload exactly per 18 §7.1. Hotkeys Enter / Esc.
 */
import { expect, test, type Page } from "@playwright/test";

import { installSyncStub, STUB_DEVICE, type StubEvent, type SyncStub } from "./support/offline-stub.ts";
import { OPS_CASHIER, OPS_MANAGER, OPS_SHIFT, idbPut, json, opsPull, seedOps } from "./support/pos-ops.ts";
import { posBffSession } from "./support/pos-seed.ts";

const SALE_ID = "0190a000-0000-7000-8000-0000000005a1";

const line = (
  id: string,
  product: string,
  name: string,
  qty: string,
  price: string,
  total: string,
  marking: string | null = null,
) => ({
  id,
  sale_line_id: id,
  line_no: 1,
  product_id: product,
  product_name: name,
  unit_code: "dona",
  qty,
  returned_qty: "0.000",
  price,
  discount_amount: "0.00",
  discount_pct: null,
  discount_source: null,
  discount_rule_id: null,
  vat_rate: "12.00",
  vat_exemption_code: null,
  vat_amount: "0.00",
  line_total: total,
  marking_code: marking,
  settled_amount: "0.00",
});

function sale(lines: ReturnType<typeof line>[], total: string) {
  return {
    id: SALE_ID,
    number: "K-01-2026-000471",
    temp_number: null,
    doc_date: "2026-10-15",
    status: "posted",
    branch_id: STUB_DEVICE.branch_id,
    shift_id: "0190a000-0000-7000-8000-0000000005a0",
    cash_register_id: STUB_DEVICE.cash_register_id,
    counterparty_id: null,
    total_amount: total,
    is_offline: false,
    debt_limit_exceeded: false,
    created_by: "u-1",
    created_at: "2026-10-15T13:20:00Z",
    posted_at: "2026-10-15T13:20:01Z",
    device_id: STUB_DEVICE.id,
    comment: null,
    lines,
    payments: [
      {
        id: "pay-1",
        method: "cash",
        amount: total,
        card_entry_mode: null,
        manual_reason: null,
        card_type: null,
        card_mask: null,
        rrn: null,
        approval_code: null,
        card_scheme: null,
        terminal_ref: null,
        qr_type: null,
        provider_tx_id: null,
        due_date: null,
      },
    ],
    fiscal_receipts: [],
  };
}

const actorHeaders: (string | undefined)[] = [];

async function stubSale(page: Page, body: ReturnType<typeof sale>) {
  await page.route("**/api/v1/sales?**", (route) => {
    actorHeaders.push(route.request().headers()["x-actor-user-id"]);
    return route.fulfill(
      json({
        items: [
          {
            id: body.id,
            number: body.number,
            temp_number: null,
            doc_date: body.doc_date,
            status: "posted",
            total_amount: body.total_amount,
            payments_summary: [],
            counterparty_id: null,
            is_offline: false,
            has_returns: false,
            shift_id: body.shift_id,
            cash_register_id: body.cash_register_id,
            branch_id: body.branch_id,
            created_at: body.created_at,
          },
        ],
        next_cursor: null,
      }),
    );
  });
  await page.route(`**/api/v1/sales/${body.id}`, (route) => route.fulfill(json(body)));
}

const returns = (sync: SyncStub): StubEvent[] =>
  sync.pushRequests.flatMap((r) => r.events).filter((e) => e.type === "return.created");

async function findReceipt(page: Page) {
  await expect(page.getByTestId("pos-returns")).toBeVisible();
  await page.getByTestId("receipt-query").fill("K-01-2026-000471");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("receipt-card")).toContainText("K-01-2026-000471");
}

test("QT-M02-03 + US-M02-03: one Coca-Cola back for cash within the limit — no approval, VAT shown", async ({
  page,
}) => {
  const sync = await installSyncStub(page, { session: posBffSession(), pull: opsPull() });
  await stubSale(
    page,
    sale([line("sl-1", "p-milk", "Coca-Cola 1.5L", "3.000", "12000.0000", "36000.00")], "36000.00"),
  );
  await seedOps(page, sync, "/pos/returns");
  await findReceipt(page);
  await page.getByTestId("return-line-0").getByRole("checkbox").first().click();
  await page.getByTestId("return-qty-0").fill("1.000");
  await page.getByTestId("return-reason-defective").click();
  await expect(page.getByTestId("return-total")).toContainText(/12\s000/);
  await expect(page.getByTestId("return-vat")).toContainText(/1\s285,71/);
  await page.getByTestId("return-submit").click();
  await expect(page.getByTestId("return-done")).toBeVisible();
  // POS REST calls name the PIN-verified cashier (device-auth.md §4)
  expect(actorHeaders.at(-1)).toBe(OPS_CASHIER);
  await expect.poll(() => returns(sync).length).toBe(1);
  const payload = returns(sync)[0]?.payload ?? {};
  expect(Object.keys(payload).sort()).toEqual(
    [
      "approval",
      "branch_id",
      "cash_register_id",
      "counterparty_id",
      "fiscal_result",
      "id",
      "is_offline",
      "lines",
      "reason",
      "receipt_seq",
      "refund_card",
      "refund_method",
      "sale_id",
      "shift_id",
    ].sort(),
  );
  expect(payload).toMatchObject({
    sale_id: SALE_ID,
    shift_id: OPS_SHIFT,
    cash_register_id: STUB_DEVICE.cash_register_id,
    receipt_seq: 1,
    fiscal_result: null,
    is_offline: false,
    reason: "defective",
    refund_method: "cash",
    refund_card: null,
    approval: null,
    lines: [
      {
        sale_line_id: "sl-1",
        product_id: "p-milk",
        qty: "1.000",
        price: "12000.0000",
        vat_rate: "12.00",
        vat_exemption_code: null,
        marking_code: null,
        restock: true,
      },
    ],
  });
});

test("QT-M02-04: 150 000 above the cashier's limit → Manager PIN (return_over_limit)", async ({ page }) => {
  const sync = await installSyncStub(page, { session: posBffSession(), pull: opsPull() });
  await stubSale(
    page,
    sale([line("sl-9", "p-milk", "Televizor", "1.000", "150000.0000", "150000.00")], "150000.00"),
  );
  await seedOps(page, sync, "/pos/returns");
  await findReceipt(page);
  await page.getByTestId("return-line-0").getByRole("checkbox").first().click();
  await page.getByTestId("return-reason-wrong_item").click();
  await page.getByTestId("return-submit").click();
  await expect(page.getByTestId("manager-approval")).toBeVisible();
  expect(returns(sync)).toHaveLength(0);
  await page.getByTestId("approver-pin").fill("1234");
  await page.getByTestId("approver-pin").press("Enter");
  await expect(page.getByTestId("return-done")).toBeVisible();
  await expect.poll(() => returns(sync).length).toBe(1);
  expect(returns(sync)[0]?.payload).toMatchObject({
    sale_id: SALE_ID,
    approval: {
      mode: "local_pin",
      approved_by: OPS_MANAGER,
      pin_verified_locally: true,
      approval_request_id: null,
    },
  });
});

test("QT-M02-02: return without a receipt always needs the Manager/Owner PIN (return_no_receipt)", async ({
  page,
}) => {
  const sync = await installSyncStub(page, { session: posBffSession(), pull: opsPull() });
  await seedOps(page, sync, "/pos/returns");
  await expect(page.getByTestId("pos-returns")).toBeVisible();
  await page.getByTestId("no-receipt").click();
  await page.getByTestId("product-query").fill("Non");
  await page.getByRole("button", { name: "Non Patir" }).click();
  await expect(page.getByTestId("return-total")).toContainText(/4\s000/);
  await page.getByTestId("return-reason-other").click();
  await page.getByTestId("return-submit").click();
  await expect(page.getByTestId("manager-approval")).toBeVisible();
  await expect(page.getByTestId("manager-approval")).toBeVisible();
  await page.getByTestId("approver-pin").fill("1234");
  await page.getByTestId("approver-pin").press("Enter");
  await expect(page.getByTestId("return-done")).toBeVisible();
  await expect.poll(() => returns(sync).length).toBe(1);
  expect(returns(sync)[0]?.payload).toMatchObject({
    sale_id: null,
    reason: "other",
    approval: { mode: "local_pin", approved_by: OPS_MANAGER },
    lines: [{ sale_line_id: null, product_id: "p-bread", qty: "1.000", price: "4000.0000", restock: true }],
  });
});

test("16 §7: offline, a marked line from the local history is blocked; the rest can be returned", async ({
  page,
}) => {
  const sync = await installSyncStub(page, { session: posBffSession(), pull: opsPull() });
  await seedOps(page, sync, "/pos/login");
  await idbPut(page, "erp-pos", "sales_history", {
    id: SALE_ID,
    kind: "sale",
    total: "61000.00",
    number: null,
    customer_id: null,
    client_event_id: "0190a000-0000-7000-8000-0000000005c1",
    created_at: new Date(Date.now() - 600_000).toISOString(),
    cash_register_id: STUB_DEVICE.cash_register_id,
    shift_id: OPS_SHIFT,
    receipt_seq: 3,
    summary: {
      temp_number: "D1-17",
      lines: [
        {
          id: "sl-a",
          product_id: "p-milk",
          name: "Sut 1 l",
          unit_code: "dona",
          qty: "1.000",
          price: "12000.0000",
          line_total: "12000.00",
          vat_rate: "12.00",
          vat_exemption_code: null,
          marking_code: null,
        },
        {
          id: "sl-b",
          product_id: "p-bread",
          name: "Sigaret",
          unit_code: "dona",
          qty: "1.000",
          price: "49000.0000",
          line_total: "49000.00",
          vat_rate: "12.00",
          vat_exemption_code: null,
          marking_code: "010460000000000021abc",
        },
      ],
      payments: [{ method: "cash", amount: "61000.00", card_entry_mode: null }],
    },
  });
  await page.goto("/pos/returns");
  await expect(page.getByTestId("pos-returns")).toBeVisible();
  await sync.setOffline(true);
  await page.getByTestId("receipt-query").fill("D1-17");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("receipt-card")).toContainText("Qurilma tarixi");
  await expect(page.getByTestId("return-line-1").getByRole("checkbox").first()).toBeDisabled();
  await expect(page.getByTestId("return-line-1")).toContainText("Qaytarish uchun internet kerak");
  await page.getByTestId("return-line-0").getByRole("checkbox").first().click();
  await page.getByTestId("return-reason-customer_changed_mind").click();
  await page.getByTestId("return-submit").click();
  await expect(page.getByTestId("return-done")).toBeVisible();
  // the event waits in the outbox (offline) and goes out once online
  await sync.setOffline(false);
  await expect.poll(() => returns(sync).length, { timeout: 20_000 }).toBe(1);
  expect(returns(sync)[0]?.payload).toMatchObject({
    sale_id: SALE_ID,
    is_offline: true,
    lines: [{ sale_line_id: "sl-a", marking_code: null }],
  });
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/pos\/sale/);
});

test("UX-07: at the 46 h level a return with a money part shows the modal first; «Tushundim» sends it", async ({
  page,
}) => {
  const oldest = new Date(Date.now() - 47 * 3_600_000).toISOString();
  const pull = opsPull(undefined, {
    fiscal: [
      {
        entity: "cash_register",
        id: STUB_DEVICE.cash_register_id,
        fm_state: "ok",
        last_unacked_receipt_at: oldest,
        fm_receipts_pending: 1,
        deleted: false,
      },
    ],
  });
  const sync = await installSyncStub(page, { session: posBffSession(), pull });
  await stubSale(
    page,
    sale([line("sl-1", "p-milk", "Sut 1 l", "1.000", "12000.0000", "12000.00")], "12000.00"),
  );
  await seedOps(page, sync, "/pos/returns", { pull });
  await findReceipt(page);
  await page.getByTestId("return-line-0").getByRole("checkbox").first().click();
  await page.getByTestId("return-reason-defective").click();
  await page.getByTestId("return-submit").click();
  await expect(page.getByTestId("ladder-46-modal")).toBeVisible();
  expect(returns(sync)).toHaveLength(0);
  await page.getByTestId("ladder-46-ok").click();
  await expect(page.getByTestId("return-done")).toBeVisible();
  await expect.poll(() => returns(sync).length).toBe(1);
});
