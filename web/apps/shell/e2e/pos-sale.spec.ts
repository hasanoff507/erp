/**
 * Web POS sale flow (b3-pos-sale): POS-02 sale panel, POS-03 payment, POS-04 receipt, POS-11 lookup,
 * POS-12 sync status — against the production build with page.route stubs (offline-stub.ts) and a seeded
 * device / cashier / shift (pos-seed.ts). Hotkeys per 07 (F1/F2/F4/F9/F12, +/-, Delete, Enter, Esc).
 */
import { expect, test, type Page } from "@playwright/test";

import { installSyncStub, type SyncStub } from "./support/offline-stub.ts";
import {
  FAKE_TERMINAL,
  PIN_1234_HASH,
  posBffSession,
  posPull,
  posSaleReady,
  scan,
  seedReadyPos,
  whenLines,
} from "./support/pos-seed.ts";

async function stubRest(page: Page) {
  await page.route("**/api/v1/card-terminal-transactions**", (route) =>
    route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ status: "approved" }),
    }),
  );
}

function saleEvents(sync: SyncStub) {
  return sync.pushRequests.flatMap((r) => r.events).filter((e) => e.type === "sale.created");
}

test.describe("POS-02 sale panel", () => {
  test("QT-NFR-01 scan → line < 100 ms; QT-M09-06 weight label; hotkeys +/-/Delete; QT-M01-11 void", async ({
    page,
  }) => {
    const sync = await installSyncStub(page, { session: posBffSession(), pull: posPull() });
    await seedReadyPos(page, sync);

    // warm path first (first IndexedDB read of the tab), then QT-NFR-01: a scanner burst → a NEW receipt line,
    // measured inside the page (no server involved)
    await scan(page, "4780000000028");
    await expect(page.getByTestId("receipt-line")).toHaveCount(1);
    await page.getByTestId("void-receipt").click();
    await page.getByRole("button", { name: /Ha, bekor qilish/ }).click();
    await expect(page.getByTestId("receipt-line")).toHaveCount(0);
    await page.getByTestId("barcode-field").focus();
    const waitLine = whenLines(page, 1);
    const enterAt = await scan(page, "4780000000011");
    const shownAt = await waitLine;
    expect(shownAt - enterAt).toBeLessThan(100);
    await expect(page.getByTestId("receipt-line")).toHaveCount(1);
    await expect(page.getByTestId("receipt-total")).toContainText(/4\s000/);

    // the same barcode again merges (+1); "+" from the empty scanner field adds one more
    await scan(page, "4780000000011");
    await expect(page.getByTestId("line-qty").first()).toHaveText("2");
    await page.getByTestId("barcode-field").focus();
    await page.keyboard.press("+");
    await expect(page.getByTestId("line-qty").first()).toHaveText("3");
    await page.keyboard.press("-");
    await expect(page.getByTestId("line-qty").first()).toHaveText("2");

    // QT-M09-06: EAN-13 "22" weight label of PLU 12345 → 1,250 kg × 95 000 = 118 750
    await scan(page, "2212345012503");
    await expect(page.getByTestId("receipt-line")).toHaveCount(2);
    await expect(page.getByTestId("line-total").nth(1)).toHaveText(/118\s750/);
    // QT-M09-03: price is read-only — the line has no price input
    await expect(page.getByTestId("receipt-line").locator("input")).toHaveCount(0);
    // VAT shown on the receipt (US-M10-01)
    await expect(page.getByTestId("vat-row")).toContainText("12");

    // Delete voids the selected line after the confirmation (sale.draft_voided, audit only)
    await page.keyboard.press("Delete");
    await page.getByRole("button", { name: /Ha, bekor qilish/ }).click();
    await expect(page.getByTestId("receipt-line")).toHaveCount(1);

    // QT-M01-11: BEKOR on the whole receipt → sale.draft_voided with voided_lines = null
    await page.getByTestId("void-receipt").click();
    await page.getByRole("button", { name: /Ha, bekor qilish/ }).click();
    await expect(page.getByTestId("receipt-line")).toHaveCount(0);
    await expect
      .poll(
        () => sync.pushRequests.flatMap((r) => r.events).filter((e) => e.type === "sale.draft_voided").length,
      )
      .toBe(3);
    const voids = sync.pushRequests.flatMap((r) => r.events).filter((e) => e.type === "sale.draft_voided");
    expect(voids[2]?.payload).toMatchObject({ voided_lines: null });
    expect(saleEvents(sync)).toHaveLength(0);
  });

  test("F9 opens POS-11 (view only), F12 opens POS-12, Esc returns", async ({ page }) => {
    const sync = await installSyncStub(page, { session: posBffSession(), pull: posPull() });
    await seedReadyPos(page, sync);
    await page.keyboard.press("F9");
    await expect(page).toHaveURL(/\/pos\/lookup$/);
    await page.getByTestId("lookup-query").fill("Sut");
    await page.getByTestId("lookup-row").first().click();
    await expect(page.getByTestId("lookup-price")).toContainText(/13\s500/);
    await expect(page.getByTestId("lookup-card").locator("input")).toHaveCount(0);
    await page.keyboard.press("Escape");
    await expect(page).toHaveURL(/\/pos\/sale$/);
    await posSaleReady(page);
    await page.keyboard.press("F12");
    await expect(page).toHaveURL(/\/pos\/sync$/);
    await expect(page.getByTestId("sync-status")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page).toHaveURL(/\/pos\/sale$/);
    await posSaleReady(page);
  });

  test("QT-OFFLINE48-03 (e2e): 48 h without OFD acks blocks the sale locally", async ({ page }) => {
    const oldest = new Date(Date.now() - 49 * 3_600_000).toISOString();
    const pull = posPull({
      fiscal: [
        {
          entity: "cash_register",
          id: "0190a000-0000-7000-8000-00000000c001",
          fm_state: "ok",
          last_unacked_receipt_at: oldest,
          deleted: false,
        },
      ],
    });
    const sync = await installSyncStub(page, { session: posBffSession(), pull });
    await seedReadyPos(page, sync, { pull });
    await expect(page.getByTestId("fiscal-blocked")).toBeVisible();
    await expect(page.getByTestId("ladder-chip")).toBeVisible();
    await expect(page.getByTestId("pay-button")).toBeDisabled();
    await expect(page.getByTestId("barcode-field")).toBeDisabled();
    // non-fiscal operations still work: POS-12 shows the blocked state and «Qayta ulanishga urinish»
    await page.keyboard.press("F12");
    await expect(page.getByTestId("ladder-level")).toHaveText(/Bloklangan/);
    await expect(page.getByTestId("sync-retry")).toBeEnabled();
  });
});

test.describe("POS-03 / POS-04", () => {
  test("cash sale with change → receipt; QT-M01-12 reprint writes receipt.reprinted (NUSXA)", async ({
    page,
  }) => {
    const sync = await installSyncStub(page, { session: posBffSession(), pull: posPull() });
    await stubRest(page);
    await page.route("**/api/v1/fiscal-receipts?**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              id: "0190a000-0000-7000-8000-0000000000f1",
              sale_id: null,
              kind: "sale",
              status: "fiscalized",
              receipt_seq: 1,
              fm_terminal_id: "FM-1",
              fm_receipt_seq: 77,
              fiscal_sign: "123456789012",
              qr_url: "https://ofd.soliq.uz/check?t=1",
              ofd_acked_at: null,
              created_at: new Date().toISOString(),
            },
          ],
          next_cursor: null,
        }),
      }),
    );
    await seedReadyPos(page, sync);
    await scan(page, "4780000000028");
    await expect(page.getByTestId("receipt-line")).toHaveCount(1);

    await page.keyboard.press("F4");
    await expect(page.getByTestId("payment-dialog")).toBeVisible();
    await page.getByTestId("method-cash").click();
    await page.getByTestId("cash-received").fill("20000");
    await expect(page.getByTestId("cash-change")).toContainText(/6\s500/);
    await page.getByTestId("payment-confirm").click();

    await expect(page.getByTestId("receipt-dialog")).toBeVisible();
    await expect(page.getByTestId("receipt-preview")).toContainText("Sut 1 l");
    await expect.poll(() => saleEvents(sync).length).toBe(1);
    const sale = saleEvents(sync)[0];
    expect(sale?.payload).toMatchObject({
      receipt_seq: 1,
      is_offline: false,
      payments: [{ method: "cash", amount: "13500.00" }],
      lines: [
        {
          product_id: "p-milk",
          qty: "1.000",
          price: "13500.0000",
          vat_rate: "12.00",
          line_total: "13500.00",
          vat_amount: "1446.43",
        },
      ],
    });

    // fiscal receipt known (REST fallback) → reprint enabled; Ctrl+P prints «NUSXA» and audits it
    await expect(page.getByTestId("fiscal-status")).toContainText("Fiskallashtirildi");
    await expect(page.getByTestId("reprint")).toBeEnabled();
    await page.getByTestId("reprint").click();
    await expect
      .poll(
        () => sync.pushRequests.flatMap((r) => r.events).filter((e) => e.type === "receipt.reprinted").length,
      )
      .toBe(1);
    const reprint = sync.pushRequests.flatMap((r) => r.events).find((e) => e.type === "receipt.reprinted");
    expect(reprint?.payload).toMatchObject({
      fiscal_receipt_id: "0190a000-0000-7000-8000-0000000000f1",
      sale_id: sale?.payload.id,
    });

    // Enter → new receipt (POS-02) — from the dialog body (Enter on the focused reprint button reprints, UX-02)
    await page.getByTestId("receipt-dialog").locator("h2").first().click();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/pos\/sale$/);
    await posSaleReady(page);
    await expect(page.getByTestId("receipt-line")).toHaveCount(0);
  });

  test("QT-M01-35: integrated card with the Fake terminal — 3 s → approved → receipt, no card input", async ({
    page,
  }) => {
    const pull = posPull({ cardTerminals: [FAKE_TERMINAL] });
    const sync = await installSyncStub(page, { session: posBffSession(), pull });
    await stubRest(page);
    await seedReadyPos(page, sync, { pull });
    await scan(page, "4780000000011");
    await expect(page.getByTestId("receipt-line")).toHaveCount(1);
    await page.keyboard.press("F4");
    await page.getByTestId("method-card").click();

    // waiting: the dialog cannot be closed with Esc, no field accepts card data
    await expect(page.getByText(/Summa terminalga yuborildi|Bank javobi kutilmoqda/).first()).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("payment-dialog")).toBeVisible();
    await expect(page.getByTestId("payment-dialog").locator("input:not([type=checkbox])")).toHaveCount(0);
    await expect(page.locator('input[autocomplete^="cc-"]')).toHaveCount(0);

    // approved → fiscal (server side) → sale.created → POS-04 automatically
    await expect(page.getByTestId("receipt-dialog")).toBeVisible({ timeout: 15_000 });
    await expect.poll(() => saleEvents(sync).length).toBe(1);
    const pay = (saleEvents(sync)[0]?.payload.payments as Record<string, unknown>[])[0];
    expect(pay).toMatchObject({ method: "card", card_entry_mode: "integrated", amount: "4000.00" });
    expect(pay?.card_result).toMatchObject({
      status: "approved",
      kind: "purchase",
      card_terminal_id: FAKE_TERMINAL.id,
    });
    expect(Object.keys(pay ?? {})).not.toContain("card_mask");
  });
});

test.describe("B3-DoD-01 offline", () => {
  test("offline sales (cash + manual card) are kept, then pushed and committed exactly once; QT-NFR-02 < 1 s", async ({
    page,
  }) => {
    const sync = await installSyncStub(page, { session: posBffSession(), pull: posPull() });
    await stubRest(page);
    await seedReadyPos(page, sync);
    await sync.setOffline(true);
    await expect(page.getByTestId("sync-chip")).toContainText(/Offlayn/);

    const sell = async (code: string, method: "cash" | "card") => {
      await scan(page, code);
      await expect(page.getByTestId("receipt-line")).toHaveCount(1);
      await page.keyboard.press("F4");
      await page.getByTestId(`method-${method}`).click();
      if (method === "card") {
        // no terminal bound to this register → «Karta terminalsiz qabul qilindi» (standalone, amount only)
        await page.getByRole("button", { name: /terminalsiz qabul qilindi/i }).click();
      }
      await expect(page.getByTestId("payment-confirm")).toBeEnabled();
      // QT-NFR-02: confirm → receipt on screen, measured inside the page (no driver round-trips)
      const ms = await page.evaluate(
        () =>
          new Promise<number>((resolve) => {
            const button = document.querySelector<HTMLButtonElement>('[data-testid="payment-confirm"]');
            const started = performance.now();
            const done = () => document.querySelector('[data-testid="receipt-dialog"]') !== null;
            const mo = new MutationObserver(() => {
              if (done()) {
                mo.disconnect();
                resolve(performance.now() - started);
              }
            });
            mo.observe(document.body, { childList: true, subtree: true });
            button?.click();
          }),
      );
      expect(ms).toBeLessThan(1_000);
      await expect(page.getByTestId("receipt-dialog")).toBeVisible();
      await expect(page.getByTestId("receipt-dialog")).toContainText(/Offlayn/);
      await page.getByTestId("new-receipt").click();
      await posSaleReady(page);
      await expect(page.getByTestId("receipt-line")).toHaveCount(0);
    };

    await sell("4780000000011", "cash");
    await sell("4780000000028", "card");
    await sell("4780000000011", "cash");
    expect(saleEvents(sync)).toHaveLength(0);
    await expect(page.getByTestId("sync-chip")).toContainText("3");

    await sync.setOffline(false);
    await expect.poll(() => saleEvents(sync).length, { timeout: 20_000 }).toBeGreaterThanOrEqual(3);
    const ids = [...new Set(saleEvents(sync).map((e) => e.client_event_id))];
    expect(ids).toHaveLength(3);
    await expect.poll(() => sync.committed.filter((id) => ids.includes(id)).length).toBe(3);
    sync.expectEachCommittedOnce();
    for (const e of saleEvents(sync)) {
      expect(e.payload).toMatchObject({ is_offline: true });
      expect(typeof e.payload.offline_since).toBe("string");
    }
    const card = saleEvents(sync).find(
      (e) => (e.payload.payments as { method: string }[])[0]?.method === "card",
    );
    expect((card?.payload.payments as Record<string, unknown>[])[0]).toEqual({
      method: "card",
      amount: "13500.00",
      card_entry_mode: "manual",
      manual_reason: "standalone_terminal",
      card_manual_approval: null,
    });
    await expect(page.getByTestId("sync-chip")).toContainText(/Onlayn · OFD sinxron/);
  });
});

test.describe("B3-DoD-01 offline reload", () => {
  test("sell online, go offline, reload, keep selling; back online → each sale pushed once", async ({
    page,
  }) => {
    const sync = await installSyncStub(page, { session: posBffSession(), pull: posPull() });
    await stubRest(page);
    await seedReadyPos(page, sync);

    const sellCash = async (code: string) => {
      await scan(page, code);
      await expect(page.getByTestId("receipt-line")).toHaveCount(1);
      await page.keyboard.press("F4");
      await page.getByTestId("method-cash").click();
      await page.getByTestId("payment-confirm").click();
      await expect(page.getByTestId("receipt-dialog")).toBeVisible();
      await page.getByTestId("new-receipt").click();
      await posSaleReady(page);
      await expect(page.getByTestId("receipt-line")).toHaveCount(0);
    };

    await sellCash("4780000000011");
    await expect.poll(() => sync.committed.length).toBeGreaterThanOrEqual(1);
    // the service worker (PWA app shell) must be installed and control the page before the offline reload
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready;
    });
    await page.reload();
    await posSaleReady(page);
    await expect
      .poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null), { timeout: 15_000 })
      .toBe(true);

    await sync.setOffline(true);
    await page.reload();
    await expect(page.getByTestId("barcode-field")).toBeVisible({ timeout: 15_000 });
    await posSaleReady(page);
    await expect(page.getByTestId("sync-chip")).toContainText(/Offlayn/);
    await sellCash("4780000000028");
    await sellCash("4780000000011");
    await expect(page.getByTestId("sync-chip")).toContainText("2");

    await sync.setOffline(false);
    await expect
      .poll(() => new Set(saleEvents(sync).map((e) => e.client_event_id)).size, { timeout: 30_000 })
      .toBe(3);
    const ids = [...new Set(saleEvents(sync).map((e) => e.client_event_id))];
    await expect
      .poll(() => sync.committed.filter((id) => ids.includes(id)).length, { timeout: 30_000 })
      .toBe(3);
    sync.expectEachCommittedOnce();
    expect(
      new Set(
        saleEvents(sync)
          .filter((e) => e.payload.is_offline === true)
          .map((e) => e.client_event_id),
      ).size,
    ).toBe(2);
  });
});

test.describe("POS keyboard and touch (review UX-01 … UX-06, UX-09)", () => {
  test("UX-01 Esc closes POS-03 / POS-04 through the dialog; UX-02 Enter on a focused button clicks it", async ({
    page,
  }) => {
    const sync = await installSyncStub(page, { session: posBffSession(), pull: posPull() });
    await stubRest(page);
    await seedReadyPos(page, sync);
    await scan(page, "4780000000011");
    await expect(page.getByTestId("receipt-line")).toHaveCount(1);

    await page.keyboard.press("F4");
    await page.getByTestId("method-cash").click();
    await page.keyboard.press("Escape");
    await expect(page).toHaveURL(/\/pos\/sale$/);
    await posSaleReady(page);
    await expect(page.getByTestId("payment-dialog")).toHaveCount(0);

    // mixed: focus «Qo'shish» and press Enter → the part is added (the button's own activation, not TASDIQLASH)
    await page.keyboard.press("F4");
    await page.getByTestId("method-mixed").click();
    await page.getByTestId("mixed-amount").fill("1000");
    await page.getByTestId("mixed-add").focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("mixed-parts").locator("li")).toHaveCount(1);
    expect(saleEvents(sync)).toHaveLength(0);
    await page.keyboard.press("Escape");
    await expect(page).toHaveURL(/\/pos\/sale$/);
    await posSaleReady(page);

    // receipt: Esc = «Yangi chek»
    await page.keyboard.press("F4");
    await page.getByTestId("method-cash").click();
    await page.getByTestId("payment-confirm").click();
    await expect(page.getByTestId("receipt-dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page).toHaveURL(/\/pos\/sale$/);
    await posSaleReady(page);
    await expect(page.getByTestId("receipt-dialog")).toHaveCount(0);
  });

  test("UX-03 no global key under an open dialog; UX-04 F-keys never reach the browser; UX-09 Esc returns", async ({
    page,
  }) => {
    const sync = await installSyncStub(page, { session: posBffSession(), pull: posPull() });
    await seedReadyPos(page, sync);
    await scan(page, "4780000000011");
    await expect(page.getByTestId("receipt-line")).toHaveCount(1);
    await page.keyboard.press("F2");
    await expect(page.getByTestId("discount-input")).toBeVisible();
    await page.keyboard.press("F8");
    await expect(page).toHaveURL(/\/pos\/sale$/);
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("discount-input")).toHaveCount(0);
    await posSaleReady(page);

    // POS-11 → POS-12 → Esc → POS-11 → Esc → POS-02 (back to where the cashier came from)
    await page.keyboard.press("F9");
    await expect(page).toHaveURL(/\/pos\/lookup$/);
    // UX-04: on /pos every F-key has its browser default prevented (F1 help, F3 find, F5 reload …)
    const prevented = await page.evaluate(() =>
      ["F1", "F3", "F5", "F7", "F10", "F11"].map((key) => {
        const ev = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
        document.body.dispatchEvent(ev);
        return ev.defaultPrevented;
      }),
    );
    expect(prevented).toEqual([true, true, true, true, true, true]);
    await page.keyboard.press("F12");
    await expect(page).toHaveURL(/\/pos\/sync$/);
    await page.keyboard.press("Escape");
    await expect(page).toHaveURL(/\/pos\/lookup$/);
    await page.keyboard.press("Escape");
    await expect(page).toHaveURL(/\/pos\/sale$/);
    await posSaleReady(page);
  });

  test("UX-06 touch density: every visible control on POS-02 / POS-03 is at least 48 px tall", async ({
    page,
  }) => {
    const sync = await installSyncStub(page, { session: posBffSession(), pull: posPull() });
    await seedReadyPos(page, sync);
    await scan(page, "4780000000011");
    await expect(page.getByTestId("receipt-line")).toHaveCount(1);
    const tooSmall = () =>
      page.evaluate(() =>
        [
          ...document.querySelectorAll<HTMLElement>(
            "button, input:not([type=checkbox]):not([type=radio]), select",
          ),
        ]
          .filter((el) => {
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
          })
          .filter((el) => el.getBoundingClientRect().height < 47.5)
          .map(
            (el) =>
              `${el.tagName}:${el.getAttribute("data-testid") ?? el.textContent?.trim().slice(0, 20) ?? ""}`,
          ),
      );
    expect(await tooSmall()).toEqual([]);
    await page.keyboard.press("F4");
    await page.getByTestId("method-cash").click();
    expect(await tooSmall()).toEqual([]);
  });

  test("UX-05 offline cold start without a cashier opens POS-01; the local PIN signs in", async ({
    page,
  }) => {
    const pull = posPull({ pinHash: PIN_1234_HASH });
    const sync = await installSyncStub(page, { session: posBffSession(), pull });
    await seedReadyPos(page, sync, { pull });
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready;
    });
    await page.reload();
    await expect
      .poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null), { timeout: 15_000 })
      .toBe(true);
    // the tab is closed (no cashier in sessionStorage) and the internet is down
    await page.evaluate(() => sessionStorage.removeItem("erp.pos.cashier"));
    await sync.setOffline(true);
    await page.goto("/pos");
    await expect(page).toHaveURL(/\/pos\/login/, { timeout: 15_000 });
    await expect(page.getByTestId("staff-list")).toContainText("Dilnoza Rahimova", { timeout: 15_000 });
    await page.keyboard.press("1");
    await page.keyboard.type("1234");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("signed-in-cashier").or(page.getByTestId("barcode-field"))).toBeVisible();
  });
});
