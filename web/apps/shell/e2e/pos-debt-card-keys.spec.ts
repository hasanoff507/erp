import { expect, test, type Page } from "@playwright/test";

import { installSyncStub, type Body } from "./support/offline-stub.ts";
import {
  CASHIER_ID,
  CASHIER_PERMISSIONS,
  FAKE_TERMINAL,
  posBffSession,
  posPull,
  seedReadyPos,
} from "./support/pos-seed.ts";

/**
 * WEB-02 (R3): POS-13 «Qarz daftari» holds the global POS keys while a card attempt is in progress, as POS-05
 * does (UX-03) — F6 / F8 / F9 / F12 must not leave `/pos/debts` and orphan the terminal attempt.
 * The Fake terminal answers an amount ending in 003 so'm with a timeout whose status cannot be resolved, so the
 * card panel stays locked (`unknown`) for the whole check.
 */
const CUSTOMER = "0190a000-0000-7000-8000-0000000000k7";
const SALE_A = "0190a000-0000-7000-8000-0000000000a7";

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
      open_amount: "500000.00",
      lines: [
        {
          sale_line_id: "0190a000-0000-7000-8000-0000000000l7",
          line_no: 1,
          product_id: "p-bread",
          name: "Non Patir",
          name_ru: null,
          mxik_code: null,
          package_code: null,
          unit_code: "dona",
          barcode: null,
          qty: "10.000",
          price: "50000.0000",
          line_total: "500000.00",
          vat_rate: "12.00",
          vat_exemption_code: null,
          settled_amount: "0.00",
          returned_qty: "0.000",
          returned_amount: "0.00",
          marking_code: null,
        },
      ],
    },
  ],
};

async function grantPaymentRight(page: Page): Promise<void> {
  await page.evaluate((id) => {
    const raw = sessionStorage.getItem("erp.pos.cashier");
    const cashier = raw ? (JSON.parse(raw) as { permissions: string[] }) : null;
    if (!cashier) throw new Error("no cashier");
    cashier.permissions = [...cashier.permissions, "debts.payment.accept"];
    sessionStorage.setItem("erp.pos.cashier", JSON.stringify({ ...cashier, userId: id }));
  }, CASHIER_ID);
}

test("web02_fkeys_locked_during_debt_card_attempt", async ({ page }) => {
  const pull = {
    ...posPull({
      staffPermissions: [...CASHIER_PERMISSIONS, "debts.payment.accept"],
      cardTerminals: [FAKE_TERMINAL],
    }),
    customers: [CUSTOMER_ROW],
  };
  const sync = await installSyncStub(page, { session: posBffSession(), pull });
  await page.route("**/api/v1/counterparties/*/debt-ledger**", (route) =>
    route.fulfill({ status: 503, contentType: "application/json", body: "{}" }),
  );
  await page.route("**/api/v1/card-terminal-transactions**", (route) =>
    route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ status: "pending" }) }),
  );
  await seedReadyPos(page, sync, { pull });
  await grantPaymentRight(page);
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-pos-keys", "on");

  await page.keyboard.press("F7");
  await expect(page.getByTestId("debt-book")).toBeVisible();
  await expect(page).toHaveURL(/\/pos\/debts/);
  await page.getByTestId("debt-search").fill("botir");
  await page.getByTestId("debt-search").press("Enter");
  await expect(page.getByTestId("book-name")).toHaveText("Botir Aliyev");

  // 350 003 so'm (Fake: …003 → timeout, unresolvable) by integrated card
  await page.getByTestId("debt-amount").fill("350003");
  await page.getByTestId("pay-method-card").click();
  await page.getByTestId("debt-card-start").click();
  // the card panel is locked: the method switch is disabled while the attempt is in progress
  await expect(page.getByTestId("pay-method-cash")).toBeDisabled();

  for (const key of ["F6", "F8", "F9", "F12"]) {
    await page.locator("body").press(key);
    await expect(page).toHaveURL(/\/pos\/debts/);
    await expect(page.getByTestId("debt-book")).toBeVisible();
  }
  await expect(page.getByTestId("pay-method-cash")).toBeDisabled();
});
