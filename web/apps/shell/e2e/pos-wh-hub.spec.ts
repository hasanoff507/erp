/**
 * Ombor hub (b3-pos-wh) — UX-09: a storekeeper (no `sales.create`, global F9 off on /pos/warehouse*) reaches
 * POS-11 through the «Narx/qoldiq» tile (key 5, `stock.view`), and Esc from POS-11 returns to the hub.
 */
import { expect, test } from "@playwright/test";

import { installSyncStub } from "./support/offline-stub.ts";
import { seedWarehousePos, whPull, whSession } from "./support/pos-wh-seed.ts";

test("UX-09 storekeeper hub: «Narx/qoldiq» tile (5) opens POS-11, Esc returns to the hub", async ({
  page,
}) => {
  const sync = await installSyncStub(page, { session: whSession(), pull: whPull() });
  await seedWarehousePos(page, sync, "/pos/warehouse");
  await expect(page.getByTestId("pos-warehouse")).toBeVisible();
  await expect(page.getByTestId("hub-tile-lookup")).toBeVisible();

  await page.keyboard.press("5");
  await expect(page).toHaveURL(/\/pos\/lookup$/);
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/pos\/warehouse$/);
});
