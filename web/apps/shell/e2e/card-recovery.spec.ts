/**
 * SYNC-03 (b3-card): an APPROVED card purchase that no sale took (tab closed / reload before «To'lash») comes
 * back after a reload in the card recovery dialog; voiding it (or, when the void fails, sending it as an
 * orphan) empties `card_attempts`, so logout is no longer blocked (16 §2.1, §12).
 */
import { expect, test, type Page } from "@playwright/test";

import { idbPut } from "./support/pos-ops.ts";
import { installSyncStub, STUB_DEVICE } from "./support/offline-stub.ts";
import {
  FAKE_TERMINAL,
  posBffSession,
  posPull,
  seedReadyPos,
  SHIFT_ID,
  TERMINAL_ID,
} from "./support/pos-seed.ts";

function attemptCount(page: Page): Promise<number> {
  return page.evaluate(
    () =>
      new Promise<number>((resolve) => {
        const open = indexedDB.open("erp-pos");
        open.onsuccess = () => {
          const req = open.result.transaction("card_attempts").objectStore("card_attempts").count();
          req.onsuccess = () => {
            open.result.close();
            resolve(req.result);
          };
        };
      }),
  );
}

test("SYNC-03: dangling approved card purchase → recovery dialog → void/orphan → card_attempts empty", async ({
  page,
}) => {
  const recorded: Record<string, unknown>[] = [];
  await page.route("**/api/v1/card-terminal-transactions**", async (route) => {
    recorded.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ status: "approved" }),
    });
  });
  const pull = posPull({ cardTerminals: [FAKE_TERMINAL] });
  const sync = await installSyncStub(page, { session: posBffSession(), pull });
  await seedReadyPos(page, sync, { pull });

  const attemptId = "0190a000-0000-7000-8000-00000000a001";
  await idbPut(page, "erp-pos", "card_attempts", {
    attempt_id: attemptId,
    card_terminal_id: TERMINAL_ID,
    local_id: "fake-1",
    kind: "purchase",
    amount: "4000.00",
    client_event_id: "0190a000-0000-7000-8000-00000000e001",
    status: "approved",
    started_at: new Date().toISOString(),
    original_attempt_id: null,
    resolved_by: "auto",
    cash_register_id: STUB_DEVICE.cash_register_id,
    shift_id: SHIFT_ID,
    result: {
      attempt_id: attemptId,
      card_terminal_id: TERMINAL_ID,
      kind: "purchase",
      original_attempt_id: null,
      status: "approved",
      amount: "4000.00",
      approval_code: "A1B2C3",
      rrn: "612345678901",
      stan: null,
      card_mask: "8600****1234",
      card_scheme: "uzcard",
      card_type: "unknown",
      card_type_source: "bin_table",
      entry_mode: "contactless",
      tid: "T0000001",
      mid: null,
      acquirer: null,
      tx_at: null,
      resolved_by: "auto",
      decline_code: null,
      decline_message: null,
      slip_text: null,
    },
  });
  expect(await attemptCount(page)).toBe(1);

  await page.reload();
  const dialog = page.getByTestId("card-recovery-dialog");
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  await expect(dialog).toContainText("Yakunlanmagan karta to'lovi");
  await expect(dialog.getByTestId("card-dangling-attach")).toBeDisabled(); // no receipt of 4 000 so'm open
  await expect(dialog.locator("input")).toHaveCount(0); // PCI
  await dialog.getByTestId("card-dangling-void").click();

  // the in-browser fake has no journal for this attempt → void fails → orphan → sent to the server
  await expect.poll(() => attemptCount(page), { timeout: 15_000 }).toBe(0);
  expect(recorded.some((b) => b.id === attemptId && b.kind === "purchase")).toBe(true);
  expect(recorded.some((b) => b.kind === "void")).toBe(true);
});
