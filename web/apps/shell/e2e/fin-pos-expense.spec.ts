/**
 * POS-14 «Xarajat» (B4-SCR-POS-14 B4 part; 18 §13.2; US-M15-01; QT-M15-01 web part) on the production
 * build: categories cached while online, then OFFLINE — a 35 000 «Transport» expense within the cashier's
 * `cash.withdraw` limit → ONE `expense.created` in the outbox (pushed when the network returns), «Kassadagi
 * naqd» drops by the amount; 60 000 needs the Manager's PIN (`approval.mode=local_pin`, kind
 * `cash_withdrawal_over_limit`). Keyboard: digits / Enter.
 */
import { expect, test, type Page } from "@playwright/test";

import { installSyncStub, type StubEvent, type SyncStub } from "./support/offline-stub.ts";
import { OPS_CASHIER, OPS_MANAGER, OPS_SHIFT, opsPull, seedOps } from "./support/pos-ops.ts";
import { posBffSession } from "./support/pos-seed.ts";

const CATEGORIES = [
  {
    id: "c-tr",
    code: null,
    name: "Transport",
    default_account: "9410",
    source_ref: null,
    is_system: false,
    archived_at: null,
    version: 1,
  },
  {
    id: "c-old",
    code: null,
    name: "Eski toifa",
    default_account: "9430",
    source_ref: null,
    is_system: false,
    archived_at: "2026-01-01T00:00:00Z",
    version: 2,
  },
  {
    id: "c-tax",
    code: "tax",
    name: "Soliqlar",
    default_account: "6410",
    source_ref: null,
    is_system: true,
    archived_at: null,
    version: 1,
  },
];

const expenses = (sync: SyncStub): StubEvent[] =>
  sync.pushRequests.flatMap((r) => r.events).filter((e) => e.type === "expense.created");

async function typeAmount(page: Page, digits: string) {
  for (const d of digits) await page.keyboard.press(d);
}

async function openExpenseMode(page: Page, sync: SyncStub) {
  await page.route("**/api/v1/expense-categories**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: CATEGORIES }),
    }),
  );
  await seedOps(page, sync, "/pos/cash-movement", { openingCash: "500000.00" });
  await expect(page.getByTestId("pos-cash-movement")).toBeVisible();
  await page.getByRole("group", { name: "Yo'nalish" }).getByRole("button", { name: "Xarajat" }).click();
  await expect(page.getByTestId("pos-expense")).toBeVisible();
  // online: the categories are read and cached (archived ones are not offered)
  await expect(page.getByTestId("expense-category-c-tr")).toBeVisible();
  await expect(page.getByTestId("expense-category-c-old")).toHaveCount(0);
}

test("B4-SCR-POS-14: offline cash expense → one expense.created; cash in drawer drops", async ({ page }) => {
  const sync = await installSyncStub(page, { session: posBffSession(), pull: opsPull() });
  await openExpenseMode(page, sync);

  await sync.setOffline(true);
  await page.reload();
  await page.getByRole("group", { name: "Yo'nalish" }).getByRole("button", { name: "Xarajat" }).click();
  await expect(page.getByTestId("pos-expense")).toContainText("qurilmadagi nusxadan");
  await typeAmount(page, "35000");
  await expect(page.getByTestId("expense-amount")).toContainText(/35\s000/);
  await page.getByTestId("expense-category-c-tr").click();
  await page.getByTestId("expense-comment").fill("Taksi — yetkazib berish");
  await page.getByTestId("expense-comment").blur();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("expense-done")).toBeVisible();
  await expect(page.getByTestId("movement-list")).toContainText(/35\s000/);
  await expect(page.getByTestId("movement-list")).toContainText("Xarajat");
  await expect(page.getByTestId("cash-now")).toContainText(/465\s000/);
  expect(expenses(sync)).toHaveLength(0);

  await sync.setOffline(false);
  await expect.poll(() => expenses(sync).length, { timeout: 20_000 }).toBeGreaterThanOrEqual(1);
  const e = expenses(sync)[0];
  expect(e?.actor_user_id).toBe(OPS_CASHIER);
  expect(e?.payload).toMatchObject({
    shift_id: OPS_SHIFT,
    category_id: "c-tr",
    amount: "35000.00",
    comment: "Taksi — yetkazib berish",
    tax_type: null,
    approval: null,
  });
  expect(Object.keys(e?.payload ?? {}).sort()).toEqual(
    [
      "amount",
      "approval",
      "branch_id",
      "cash_register_id",
      "category_id",
      "comment",
      "doc_date",
      "id",
      "shift_id",
      "tax_type",
    ].sort(),
  );
  sync.expectEachCommittedOnce();
});

test("POS-14 Xarajat: 60 000 over the 50 000 limit needs the Manager's PIN (local_pin)", async ({ page }) => {
  const sync = await installSyncStub(page, { session: posBffSession(), pull: opsPull() });
  await openExpenseMode(page, sync);
  await typeAmount(page, "60000");
  await page.getByTestId("expense-category-c-tr").click();
  await page.getByTestId("expense-submit").click();
  await expect(page.getByTestId("manager-approval")).toBeVisible();
  expect(expenses(sync)).toHaveLength(0);
  await page.getByTestId("approver-pin").fill("1234");
  await page.getByTestId("approver-pin").press("Enter");
  await expect(page.getByTestId("expense-done")).toBeVisible();
  await expect.poll(() => expenses(sync).length).toBe(1);
  expect(expenses(sync)[0]?.payload).toMatchObject({
    amount: "60000.00",
    approval: { mode: "local_pin", approved_by: OPS_MANAGER, pin_verified_locally: true },
  });
});
