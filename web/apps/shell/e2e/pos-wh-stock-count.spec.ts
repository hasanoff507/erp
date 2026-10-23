/**
 * POS-10 Inventarizatsiya (b3-pos-wh) — QT-M05-05: scanning without internet writes
 * `stock_count.line_recorded` events locally; they sync when the network returns; the final
 * «Sanashni yakunlash» (`submit-for-review`) is online only.
 */
import { expect, test } from "@playwright/test";

import { installSyncStub } from "./support/offline-stub.ts";
import { CASHIER_ID } from "./support/pos-seed.ts";
import { json, scanCode, seedWarehousePos, whPull, whSession } from "./support/pos-wh-seed.ts";

const COUNT = {
  id: "c-1", number: "INV-01-2026-000007", status: "counting", doc_date: "2026-10-17", branch_id: "b-1",
  warehouse_id: "w-1", started_at: "2026-10-17T05:00:00Z", responsible_user_id: null, comment: null,
  line_count: 2, counted_count: 0, uncounted_count: 2, created_by: "u-1", created_at: null, posted_at: null,
  cancelled_at: null, cancel_reason: null,
  lines: [
    { id: "l-1", line_no: 1, product_id: "p-bread", product_name: "Non Patir", snapshot_qty: "10.000",
      expected: "10.000", counted: null, counted_at: null, diff: null, amount: null },
    { id: "l-2", line_no: 2, product_id: "p-milk", product_name: "Sut 1 l", snapshot_qty: "4.000",
      expected: "4.000", counted: null, counted_at: null, diff: null, amount: null },
  ],
}; // prettier-ignore

test("QT-M05-05 offline count lines are recorded locally and synced once; finishing is online", async ({
  page,
}) => {
  const sync = await installSyncStub(page, { session: whSession(), pull: whPull() });
  let submitted = 0;
  const actors: (string | null)[] = [];
  await page.route("**/api/v1/stock-counts**", (route) => {
    actors.push(route.request().headers()["x-actor-user-id"] ?? null);
    const url = route.request().url();
    if (url.endsWith("/submit-for-review")) {
      submitted += 1;
      return json(route, { ...COUNT, status: "review" });
    }
    if (/stock-counts\/c-1$/.test(url)) return json(route, COUNT);
    return json(route, { items: [{ ...COUNT, lines: [] }], next_cursor: null });
  });
  await seedWarehousePos(page, sync, "/pos/warehouse/stocktake");
  await expect(page.getByTestId("count-table")).toBeVisible();
  await expect(page.getByTestId("count-row")).toHaveCount(2);

  await sync.setOffline(true);
  await scanCode(page, "4780000000011");
  await scanCode(page, "4780000000011");
  await scanCode(page, "4780000000028");
  await expect(page.getByTestId("count-progress")).toContainText("2 / 2");
  await expect(page.getByTestId("count-current")).toContainText("Sut 1 l");
  // finishing needs internet
  await expect(page.getByTestId("count-finish")).toBeDisabled();
  expect(sync.pushRequests.flatMap((r) => r.events).length).toBe(0);

  await sync.setOffline(false);
  await expect.poll(() => sync.committed.length, { timeout: 20_000 }).toBe(3);
  const events = sync.pushRequests
    .flatMap((r) => r.events)
    .filter((e) => e.type === "stock_count.line_recorded");
  expect(events.map((e) => [e.payload.product_id, e.payload.counted])).toEqual([
    ["p-bread", "1.000"],
    ["p-bread", "2.000"],
    ["p-milk", "1.000"],
  ]);
  expect(events.every((e) => e.payload.count_id === "c-1" && typeof e.payload.recorded_at === "string")).toBe(
    true,
  );
  sync.expectEachCommittedOnce();

  await page.keyboard.press("F9");
  await page.getByRole("button", { name: "Sanashni yakunlash" }).last().click();
  await expect.poll(() => submitted).toBe(1);
  // SEC-04 (F-4): every REST call of the device-bound POS — reads too — names the PIN actor
  expect(actors.length).toBeGreaterThan(1);
  expect(new Set(actors)).toEqual(new Set([CASHIER_ID]));
});
