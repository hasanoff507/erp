/**
 * POS-09 Ko'chirish (b3-pos-wh) — QT-M06-04: an internal transfer created OFFLINE is written to the outbox,
 * reaches the server once when the network returns (dedupe by client_event_id), and the e-TTN warning of a
 * vehicle transfer is shown; receiving an incoming transfer offline (`transfer.received`).
 */
import { expect, test } from "@playwright/test";

import { installSyncStub, type StubEvent } from "./support/offline-stub.ts";
import { json, scanCode, seedWarehousePos, whPull, whSession } from "./support/pos-wh-seed.ts";

const INCOMING = {
  id: "t-in-1", number: "KO-02-2026-000003", status: "sent", doc_date: "2026-10-16", branch_id: "b-2",
  from_branch_id: "b-2", to_branch_id: "b-1", from_warehouse_id: "w-2", to_warehouse_id: "w-1",
  transport_mode: "on_foot_or_public", vehicle_plate: null, driver_name: null, ettn_ref: null, ettn: null,
  is_overdue: false, comment: null, created_by: "u-2", created_at: null, posted_at: null, sent_at: null,
  sent_by: null, received_at: null, received_by: null, cancelled_at: null, cancel_reason: null, warnings: [],
  lines: [{ id: "tl-1", line_no: 1, product_id: "p-milk", product_name: "Sut 1 l", qty_sent: "5.000",
    qty_received: null, unit_cost: "9000.0000", lot_allocations: [] }],
}; // prettier-ignore

const transferEvents = (events: StubEvent[], type: string) => events.filter((e) => e.type === type);

test("QT-M06-04 offline transfer is synced exactly once (ETTN_REQUIRED warning shown)", async ({ page }) => {
  const sync = await installSyncStub(page, {
    session: whSession(),
    pull: whPull(),
    onEvent: (e) =>
      e.type === "transfer.sent"
        ? {
            server: { id: e.payload.id, number: "KO-01-2026-000011", status: "posted" },
            warnings: ["ETTN_REQUIRED"],
          }
        : null,
  });
  await page.route("**/api/v1/transfers**", (route) => json(route, { items: [INCOMING], next_cursor: null }));
  await seedWarehousePos(page, sync, "/pos/warehouse/transfer");
  await expect(page.getByTestId("pos-transfers")).toBeVisible();
  await expect(page.getByTestId("transfer-from")).toHaveText("Chilonzor ombori");

  await sync.setOffline(true);
  await scanCode(page, "4780000000011");
  await scanCode(page, "4780000000011");
  await expect(page.getByTestId("transfer-line")).toHaveCount(1);
  await expect(page.getByTestId("transfer-totals")).toContainText("2");
  await page.getByLabel("Manzil ombor").selectOption("w-2");
  await page.getByLabel("Avtomobil raqami").fill("01A123BC");
  await page.keyboard.press("F9");
  await expect(page.getByTestId("transfer-notice")).toBeVisible();
  // nothing reached the server while offline
  expect(
    transferEvents(
      sync.pushRequests.flatMap((r) => r.events),
      "transfer.sent",
    ),
  ).toHaveLength(0);

  await sync.setOffline(false);
  await expect.poll(() => sync.committed.length, { timeout: 20_000 }).toBeGreaterThan(0);
  const sent = transferEvents(
    sync.pushRequests.flatMap((r) => r.events),
    "transfer.sent",
  );
  expect(sent[0]?.payload).toMatchObject({
    from_warehouse_id: "w-1",
    to_warehouse_id: "w-2",
    transport_mode: "vehicle",
    vehicle_plate: "01A123BC",
    lines: [{ product_id: "p-bread", qty_sent: "2.000" }],
  });
  sync.expectEachCommittedOnce();

  // «Jo'natmalar» shows the server answer: posted + e-TTN required
  await page.getByRole("tab", { name: "Jo'natmalar" }).click();
  await expect(page.getByTestId("transfer-history")).toContainText("KO-01-2026-000011");
  await expect(page.getByTestId("transfer-history")).toContainText("E-TTN kerak");
});

test("offline receive of an incoming transfer → transfer.received once", async ({ page }) => {
  const sync = await installSyncStub(page, { session: whSession(), pull: whPull() });
  await page.route("**/api/v1/transfers**", (route) => json(route, { items: [INCOMING], next_cursor: null }));
  await seedWarehousePos(page, sync, "/pos/warehouse/transfer");
  await page.getByRole("tab", { name: "Qabul qilish" }).click();
  await expect(page.getByTestId("incoming-transfer")).toHaveCount(1);

  await sync.setOffline(true);
  await page.getByTestId("incoming-transfer").click();
  await page.getByLabel("Qabul qilingan — Sut 1 l").fill("4.5");
  await page.getByTestId("transfer-receive").click();
  await expect(page.getByTestId("transfer-notice")).toBeVisible();
  await expect(page.getByTestId("incoming-transfer")).toHaveCount(0);

  await sync.setOffline(false);
  await expect.poll(() => sync.committed.length, { timeout: 20_000 }).toBe(1);
  const received = transferEvents(
    sync.pushRequests.flatMap((r) => r.events),
    "transfer.received",
  );
  expect(received[0]?.payload).toEqual({
    transfer_id: "t-in-1",
    lines: [{ transfer_line_id: "tl-1", qty_received: "4.500" }],
  });
  sync.expectEachCommittedOnce();
});
