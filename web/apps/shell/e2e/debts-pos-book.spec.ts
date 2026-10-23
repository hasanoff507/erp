import { expect, test, type Page } from "@playwright/test";

import { installSyncStub, type Body, type StubEvent, type SyncStub } from "./support/offline-stub.ts";
import { CASHIER_ID, CASHIER_PERMISSIONS, posBffSession, posPull, seedReadyPos } from "./support/pos-seed.ts";

/**
 * POS-13 «Qarz daftari» (07; 18 §12.2; 16 §1, §5; qaror #45, #67) — QT-M08-16 / QT-M08-17 device halves:
 * offline, F7 → the customer → 350 000 cash: the screen shows A closed fully and B partly (rest 150 000), the
 * `debt_settlement` receipt prints; a second offline payment allocates only what is left and its excess is
 * accepted with a warning (unallocated, Kt 6310). Online both `debt_payment.created` go out with the device
 * allocations, receipt lines (Σ = amount) and consecutive receipt numbers.
 */
const CUSTOMER = "0190a000-0000-7000-8000-0000000000k1";
const SALE_A = "0190a000-0000-7000-8000-0000000000a1";
const SALE_B = "0190a000-0000-7000-8000-0000000000b2";

const line = (id: string, product: string, name: string, total: string): Body => ({
  sale_line_id: id,
  line_no: 1,
  product_id: product,
  name,
  name_ru: null,
  mxik_code: null,
  package_code: null,
  unit_code: "dona",
  barcode: null,
  qty: "10.000",
  price: "1000.0000",
  line_total: total,
  vat_rate: "12.00",
  vat_exemption_code: null,
  settled_amount: "0.00",
  returned_qty: "0.000",
  returned_amount: "0.00",
  marking_code: null,
});

const CUSTOMER_ROW: Body = {
  id: CUSTOMER,
  kind: "person",
  name: "Botir Aliyev",
  phone: "+998901234567",
  stir: null,
  credit_limit: "1000000.00",
  standing_discount_pct: null,
  receivable_balance: "500000.00",
  debt_due_date: "2026-10-20",
  archived_at: null,
  version: 3,
  updated_at: "2026-10-15T05:00:00Z",
  deleted: false,
  open_debt_docs: [
    {
      doc_type: "sales",
      doc_id: SALE_A,
      number: "S-000301",
      doc_date: "2026-10-01",
      due_date: "2026-10-05",
      open_amount: "300000.00",
      lines: [line("0190a000-0000-7000-8000-0000000000l1", "p-bread", "Non Patir", "300000.00")],
    },
    {
      doc_type: "sales",
      doc_id: SALE_B,
      number: "S-000355",
      doc_date: "2026-10-03",
      due_date: "2026-10-09",
      open_amount: "200000.00",
      lines: [
        line("0190a000-0000-7000-8000-0000000000l2", "p-milk", "Sut 1 l", "120000.00"),
        { ...line("0190a000-0000-7000-8000-0000000000l3", "p-bread", "Non Patir", "80000.00"), line_no: 2 },
      ],
    },
  ],
};

function payments(sync: SyncStub): StubEvent[] {
  const seen = new Map<string, StubEvent>();
  for (const r of sync.pushRequests)
    for (const e of r.events) if (e.type === "debt_payment.created") seen.set(e.client_event_id, e);
  return [...seen.values()].sort((a, b) => a.seq - b.seq);
}

/** The seeded cashier may also take debt payments (`debts.payment.accept`, 18 §12.2). */
async function grantPaymentRight(page: Page): Promise<void> {
  await page.evaluate((id) => {
    const raw = sessionStorage.getItem("erp.pos.cashier");
    const cashier = raw ? (JSON.parse(raw) as { permissions: string[] }) : null;
    if (!cashier) throw new Error("no cashier");
    cashier.permissions = [...cashier.permissions, "debts.payment.accept"];
    sessionStorage.setItem("erp.pos.cashier", JSON.stringify({ ...cashier, userId: id }));
  }, CASHIER_ID);
}

test("QT-M08-16/17 offline: allocation lines, receipt, second payment over the rest → overpay warning", async ({
  page,
}) => {
  const pull = {
    ...posPull({ staffPermissions: [...CASHIER_PERMISSIONS, "debts.payment.accept"] }),
    customers: [CUSTOMER_ROW],
  };
  const sync = await installSyncStub(page, { session: posBffSession(), pull });
  await page.route("**/api/v1/counterparties/*/debt-ledger**", (route) =>
    route.fulfill({ status: 503, contentType: "application/json", body: "{}" }),
  );
  await seedReadyPos(page, sync, { pull });
  await grantPaymentRight(page);
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-pos-keys", "on");
  await sync.setOffline(true);

  await page.keyboard.press("F7");
  const book = page.getByTestId("debt-book");
  await expect(book).toBeVisible();
  await expect(page.getByTestId("debtors-total")).toContainText(/500\s000/);
  await page.getByTestId("debt-search").fill("botir");
  await page.getByTestId("debt-search").press("Enter");
  await expect(page.getByTestId("book-name")).toHaveText("Botir Aliyev");
  await expect(page.getByTestId("book-balance")).toHaveText(/500\s000/);
  await expect(page.getByTestId("book-open-docs")).toContainText("S-000301");

  // 350 000: A (earlier due) fully, B partly — rest 150 000; the receipt line note
  await page.getByTestId("debt-amount").fill("350000");
  const rows = page.getByTestId("allocation-row");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText("S-000301");
  await expect(rows.nth(0).getByTestId("allocation-state")).toHaveText("to'liq yopiladi");
  await expect(rows.nth(1).getByTestId("allocation-state")).toHaveText(/qisman · qoldiq 150\s000/);
  await expect(page.getByTestId("debt-after-payment")).toHaveText(/150\s000/);
  await page.getByTestId("debt-accept").click();
  const receipt = page.getByTestId("debt-receipt");
  await expect(receipt).toBeVisible();
  await expect(receipt.getByTestId("receipt-preview")).toContainText("QARZ TO'LOVI");
  await expect(receipt.getByTestId("receipt-preview")).toContainText("Non Patir");
  await expect(receipt.getByTestId("debt-receipt-status")).toHaveText("Chek chop etildi");
  await page.keyboard.press("Enter");
  await expect(receipt).toBeHidden();

  // the pending payment is not taken off the debt yet, but its documents are — 200 000 > 150 000 left
  await expect(page.getByText(/Yuborilmagan to'lovlar/)).toBeVisible();
  await page.getByTestId("debt-amount").fill("200000");
  await expect(page.getByTestId("allocation-row")).toHaveCount(1);
  await expect(page.getByTestId("allocation-state")).toHaveText("to'liq yopiladi");
  await expect(page.getByTestId("debt-overpay")).toContainText(/50\s000/);
  await page.getByTestId("debt-accept").click();
  await expect(page.getByTestId("debt-receipt")).toBeVisible();
  await page.getByTestId("debt-receipt-close").click();
  expect(payments(sync)).toHaveLength(0);

  await sync.setOffline(false);
  await expect.poll(() => payments(sync).length, { timeout: 20_000 }).toBe(2);
  const [first, second] = payments(sync);
  expect(first?.actor_user_id).toBe(CASHIER_ID);
  expect(first?.payload).toMatchObject({
    counterparty_id: CUSTOMER,
    amount: "350000.00",
    method: "cash",
    is_offline: true,
    allocations: [
      { target_doc_type: "sales", target_doc_id: SALE_A, amount: "300000.00" },
      { target_doc_type: "sales", target_doc_id: SALE_B, amount: "50000.00" },
    ],
  });
  const lines1 = first?.payload.fiscal_lines as { amount: string; sale_id: string | null }[];
  expect(lines1.map((l) => l.amount)).toEqual(["300000.00", "30000.00", "20000.00"]);
  expect(second?.payload).toMatchObject({
    amount: "200000.00",
    allocations: [{ target_doc_type: "sales", target_doc_id: SALE_B, amount: "150000.00" }],
  });
  const lines2 = second?.payload.fiscal_lines as {
    amount: string;
    sale_id: string | null;
    vat_rate: string;
  }[];
  expect(lines2.map((l) => l.amount)).toEqual(["90000.00", "60000.00", "50000.00"]);
  expect(lines2[2]).toMatchObject({ sale_id: null, vat_rate: "0.00" });
  const seqs = [first?.payload.receipt_seq, second?.payload.receipt_seq] as number[];
  expect(seqs[1]).toBe((seqs[0] ?? 0) + 1);
  sync.expectEachCommittedOnce();
});

test("qaror #45 online: a payment above the debt is refused on the device (change is given in cash)", async ({
  page,
}) => {
  const pull = {
    ...posPull({ staffPermissions: [...CASHIER_PERMISSIONS, "debts.payment.accept"] }),
    customers: [CUSTOMER_ROW],
  };
  const sync = await installSyncStub(page, { session: posBffSession(), pull });
  await page.route("**/api/v1/counterparties/*/debt-ledger**", (route) =>
    route.fulfill({ status: 503, contentType: "application/json", body: "{}" }),
  );
  await seedReadyPos(page, sync, { pull });
  await grantPaymentRight(page);
  await page.goto("/pos/debts");
  await page.getByTestId("debtor-row").first().click();
  await page.getByTestId("debt-amount").fill("600000");
  await expect(page.getByTestId("debt-exceeds")).toContainText(/500\s000/);
  await expect(page.getByTestId("debt-accept")).toBeDisabled();
});
