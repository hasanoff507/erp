import { expect, test } from "@playwright/test";

import { installSyncStub, type StubEvent, type SyncStub } from "./support/offline-stub.ts";
import { posBffSession, posPull, scan, seedReadyPos } from "./support/pos-seed.ts";

/**
 * POS-06 «Nasiyaga sotish» (07; 18 §4.1, §11.1; 16 §5) — US-M08-01/05, QT-M08-08: offline, F5 → a new customer
 * by name + phone (`counterparty.created`) → no limit, no check → «Nasiyaga rasmiylashtirish»: `sale.created`
 * with a debt payment and no receipt number (qaror #30); both events go out in seq order once online.
 * Over the limit offline: the sale is not blocked, the cashier confirms it (the server flags it).
 */
function events(sync: SyncStub, type: string): StubEvent[] {
  const seen = new Map<string, StubEvent>();
  for (const r of sync.pushRequests)
    for (const e of r.events) if (e.type === type) seen.set(e.client_event_id, e);
  return [...seen.values()];
}

const LIMITED = {
  id: "0190a000-0000-7000-8000-0000000000k7",
  kind: "person",
  name: "Rustam Nazarov",
  phone: "+998934561208",
  stir: null,
  credit_limit: "5000.00",
  standing_discount_pct: null,
  receivable_balance: "3000.00",
  debt_due_date: null,
  archived_at: null,
  version: 1,
  updated_at: "2026-10-15T05:00:00Z",
  open_debt_docs: [],
  deleted: false,
};

test("QT-M08-08 offline: F5 → «+ Yangi mijoz» (ism + telefon) → nasiya, no receipt; pushed in order", async ({
  page,
}) => {
  const sync = await installSyncStub(page, { session: posBffSession(), pull: posPull() });
  await seedReadyPos(page, sync);
  await sync.setOffline(true);

  await scan(page, "4780000000011");
  await expect(page.getByTestId("receipt-line")).toHaveCount(1);
  await page.keyboard.press("F5");
  const dialog = page.getByTestId("credit-dialog");
  await expect(dialog).toBeVisible();
  // the customer picker opens by itself; «+ Yangi mijoz» → name + phone (2–3 s, offline)
  await page.getByTestId("quick-customer").click();
  await page.getByTestId("quick-name").fill("Malika Yusupova");
  await page.getByTestId("quick-phone").fill("977114022");
  await page.getByTestId("quick-save").click();
  await expect(dialog.getByTestId("debt-customer-name")).toHaveText("Malika Yusupova");
  // a new customer has no limit → no check at all
  await expect(dialog.getByTestId("debt-no-limit")).toBeVisible();
  await expect(dialog.getByTestId("credit-total")).toHaveText(/4\s000/);
  await expect(dialog).toContainText("Fiskal chek hozir chiqmaydi.");
  await dialog.getByTestId("due-7").click();
  await dialog.getByTestId("credit-confirm").click();
  await expect(
    page.getByText("Nasiyaga yozildi. Fiskal chek qarz to'langanda chiqadi.").first(),
  ).toBeVisible();
  await expect(page.getByTestId("receipt-line")).toHaveCount(0);
  expect(events(sync, "sale.created")).toHaveLength(0);

  await sync.setOffline(false);
  await expect.poll(() => events(sync, "sale.created").length, { timeout: 20_000 }).toBe(1);
  const [cp] = events(sync, "counterparty.created");
  const [sale] = events(sync, "sale.created");
  expect(cp?.payload).toMatchObject({ kind: "person", name: "Malika Yusupova", phone: "+998977114022" });
  expect(cp && sale && cp.seq < sale.seq).toBe(true);
  expect(sale?.payload).toMatchObject({
    counterparty_id: cp?.payload.id,
    receipt_seq: null,
    is_offline: true,
    payments: [{ method: "debt", amount: "4000.00", debt_approval: null }],
  });
  const due = (sale?.payload.payments as Record<string, unknown>[])[0]?.due_date;
  expect(typeof due).toBe("string");
  sync.expectEachCommittedOnce();
});

test("16 §5 offline over the limit: not blocked, the cashier confirms; the sale goes with the flag-worthy debt", async ({
  page,
}) => {
  const pull = { ...posPull(), customers: [LIMITED] };
  const sync = await installSyncStub(page, { session: posBffSession(), pull });
  await seedReadyPos(page, sync, { pull });
  await sync.setOffline(true);

  await scan(page, "4780000000011");
  await expect(page.getByTestId("receipt-line")).toHaveCount(1);
  await page.getByTestId("debt-button").click();
  const dialog = page.getByTestId("credit-dialog");
  await page.getByTestId("customer-search").fill("rustam");
  await page.getByTestId("customer-option").first().click();
  await expect(dialog.getByTestId("debt-current")).toHaveText(/3\s000/);
  await expect(dialog.getByTestId("debt-after")).toHaveText(/7\s000/);
  await expect(dialog.getByTestId("credit-confirm")).toBeDisabled();
  await dialog.getByTestId("debt-offline-confirm").click();
  await expect(dialog.getByTestId("credit-confirm")).toBeEnabled();
  await dialog.getByTestId("credit-confirm").click();
  await expect(
    page.getByText("Nasiyaga yozildi. Fiskal chek qarz to'langanda chiqadi.").first(),
  ).toBeVisible();

  await sync.setOffline(false);
  await expect.poll(() => events(sync, "sale.created").length, { timeout: 20_000 }).toBe(1);
  expect(events(sync, "sale.created")[0]?.payload).toMatchObject({
    counterparty_id: LIMITED.id,
    is_offline: true,
    payments: [{ method: "debt", amount: "4000.00" }],
  });
});
