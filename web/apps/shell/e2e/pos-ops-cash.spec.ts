/**
 * POS-14 cash in/out and POS-07 → POS-15 → Z shift close (b3-pos-ops): QT-M16-01 (within the limit, no
 * approval), QT-PERM-05 / QT-M16-02 (50 001 → Manager PIN, `approval.mode=local_pin`), QT-M01-07 (shortage →
 * note required, ONE `shift.closed`), QT-M01-06 (exact count → variance 0, Z-report with the card split),
 * close blocked by an unresolved card attempt (CARD_OUTCOME_UNKNOWN). Hotkeys: digits / Enter / Esc.
 */
import { expect, test, type Page } from "@playwright/test";

import { installSyncStub, STUB_DEVICE, type StubEvent, type SyncStub } from "./support/offline-stub.ts";
import { MANAGER, OPS_CASHIER, OPS_MANAGER, OPS_SHIFT, idbPut, opsPull, seedOps } from "./support/pos-ops.ts";
import { posBffSession } from "./support/pos-seed.ts";

const events = (sync: SyncStub, type: string): StubEvent[] =>
  sync.pushRequests.flatMap((r) => r.events).filter((e) => e.type === type);

const zReport = (counted: string, variance: string) => ({
  expected_cash: "500000.00",
  counted_cash: counted,
  variance,
  totals_by_method: {
    cash: "0.00",
    card: "0.00",
    uzqr: "0.00",
    click: "0.00",
    payme: "0.00",
    uzum: "0.00",
    debt: "0.00",
  },
  card_split: { integrated: "1143500.00", manual: "400000.00" },
  card_settlements: [],
  vat_total: "0.00",
  discount_total: "0.00",
  returns_total: "0.00",
  sales_count: 0,
  returns_count: 0,
});

async function typeAmount(page: Page, digits: string) {
  for (const d of digits) await page.keyboard.press(d);
}

test.describe("POS-14 kassa puli", () => {
  test("QT-M16-01: 40 000 «Boshqa» withdrawal within the limit — no approval", async ({ page }) => {
    const sync = await installSyncStub(page, { session: posBffSession(), pull: opsPull() });
    await seedOps(page, sync, "/pos/cash-movement");
    await expect(page.getByTestId("pos-cash-movement")).toBeVisible();
    await typeAmount(page, "40000");
    await expect(page.getByTestId("movement-amount")).toContainText(/40\s000/);
    await page.getByTestId("reason-other").click();
    await page.getByTestId("movement-comment").fill("Suv uchun");
    await page.getByTestId("movement-submit").click();
    await expect(page.getByTestId("movement-done")).toBeVisible();
    await expect.poll(() => events(sync, "cash_movement.created").length).toBe(1);
    const e = events(sync, "cash_movement.created")[0];
    expect(e?.actor_user_id).toBe(OPS_CASHIER);
    expect(e?.payload).toMatchObject({
      shift_id: OPS_SHIFT,
      direction: "out",
      reason: "other",
      account: null,
      amount: "40000.00",
      comment: "Suv uchun",
      approval: null,
    });
    await expect(page.getByTestId("movement-list")).toContainText(/40\s000/);
  });

  test("QT-PERM-05 / QT-M16-02: 50 001 needs the Manager's PIN (local_pin approval)", async ({ page }) => {
    const sync = await installSyncStub(page, { session: posBffSession(), pull: opsPull() });
    await seedOps(page, sync, "/pos/cash-movement");
    await expect(page.getByTestId("pos-cash-movement")).toBeVisible();
    await typeAmount(page, "50001");
    await expect(page.getByTestId("movement-amount")).toContainText(/50\s001/);
    await page.getByTestId("reason-collection").click();
    await page.getByTestId("movement-submit").click();
    await expect(page.getByTestId("manager-approval")).toBeVisible();
    expect(events(sync, "cash_movement.created")).toHaveLength(0);
    // the cashier cannot approve herself — only the manager is offered
    await expect(page.getByTestId("manager-approval").locator("select")).toContainText(MANAGER.name);
    await page.getByTestId("approver-pin").fill("0000");
    await page.getByTestId("approver-pin").press("Enter");
    await expect(page.getByTestId("manager-approval")).toContainText("PIN noto'g'ri");
    await page.getByTestId("approver-pin").fill("1234");
    await page.getByTestId("approver-pin").press("Enter");
    await expect(page.getByTestId("movement-done")).toBeVisible();
    await expect.poll(() => events(sync, "cash_movement.created").length).toBe(1);
    expect(events(sync, "cash_movement.created")[0]?.payload).toMatchObject({
      direction: "out",
      reason: "collection",
      amount: "50001.00",
      approval: {
        mode: "local_pin",
        approved_by: OPS_MANAGER,
        pin_verified_locally: true,
        approval_request_id: null,
      },
    });
  });
});

test.describe("POS-07 / POS-15 smena yopish", () => {
  test("QT-M01-07: 480 000 counted vs 500 000 expected → note required → ONE shift.closed → Z", async ({
    page,
  }) => {
    const sync = await installSyncStub(page, {
      session: posBffSession(),
      pull: opsPull(),
      onEvent: (e) =>
        e.type === "shift.closed"
          ? { server: { id: OPS_SHIFT, shift_no: 214, z_report: zReport("480000.00", "-20000.00") } }
          : null,
    });
    await seedOps(page, sync, "/pos/shift/close", { openingCash: "500000.00" });
    await expect(page.getByTestId("expected-cash")).toContainText(/500\s000/);
    await page.keyboard.press("Enter");
    await page.getByRole("button", { name: "Ha, yopish" }).click();
    await expect(page).toHaveURL(/\/pos\/shift\/cash-count$/);
    await expect(page.getByTestId("count-expected")).toContainText(/500\s000/);
    await page.getByTestId("den-200000").fill("2");
    await page.getByTestId("den-50000").fill("1");
    await page.getByTestId("den-20000").fill("1");
    await page.getByTestId("den-10000").fill("1");
    await expect(page.getByTestId("counted-cash")).toContainText(/480\s000/);
    await expect(page.getByTestId("count-variance")).toContainText(/20\s000/);
    await expect(page.getByTestId("count-variance")).toContainText("kamomad");
    // without a note the count is not saved
    await page.getByTestId("count-continue").click();
    await expect(page.getByText("Farq izohsiz saqlanmaydi").first()).toBeVisible();
    expect(events(sync, "shift.closed")).toHaveLength(0);
    await page.getByTestId("variance-note").fill("Kamomad — tekshiriladi");
    await page.getByTestId("count-continue").click();

    await expect(page.getByTestId("pos-z-report")).toBeVisible({ timeout: 15_000 });
    await expect.poll(() => events(sync, "shift.closed").length).toBe(1);
    expect(events(sync, "shift.closed")[0]?.payload).toEqual({
      shift_id: OPS_SHIFT,
      counted_cash: "480000.00",
      counted_card_total: "0.00",
      card_settlements: [],
      variance_note: "Kamomad — tekshiriladi",
    });
    await expect(page.getByTestId("z-variance")).toContainText(/20\s000/);
    await expect(page.getByTestId("z-card-integrated")).toContainText(/1\s143\s500/);
    await expect(page.getByTestId("z-card-manual")).toContainText(/400\s000/);
    await expect(page.getByTestId("z-source")).toContainText("server");
  });

  test("QT-M01-06: exact count → variance 0, no note needed", async ({ page }) => {
    const sync = await installSyncStub(page, {
      session: posBffSession(),
      pull: opsPull(),
      onEvent: (e) =>
        e.type === "shift.closed"
          ? { server: { id: OPS_SHIFT, shift_no: 214, z_report: zReport("500000.00", "0.00") } }
          : null,
    });
    await seedOps(page, sync, "/pos/shift/close", { openingCash: "500000.00" });
    await page.getByTestId("close-shift").click();
    await page.getByRole("button", { name: "Ha, yopish" }).click();
    await page.getByTestId("counted-cash-input").fill("500000");
    await expect(page.getByTestId("count-variance")).toContainText("Mos");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("pos-z-report")).toBeVisible({ timeout: 15_000 });
    await expect.poll(() => events(sync, "shift.closed").length).toBe(1);
    expect(events(sync, "shift.closed")[0]?.payload).toMatchObject({
      counted_cash: "500000.00",
      variance_note: null,
    });
  });

  test("SYNC-01: right after closing, POS-01 opens a NEW shift instead of re-adopting the closed one", async ({
    page,
  }) => {
    const shiftSnapshot = {
      shift: {
        digest: "sh-open",
        cash_register_id: STUB_DEVICE.cash_register_id,
        open_shift: {
          id: OPS_SHIFT,
          shift_no: 214,
          status: "open",
          device_id: STUB_DEVICE.id,
          opened_by: OPS_CASHIER,
          opened_at: new Date(Date.now() - 3_600_000).toISOString(),
          opening_cash: "500000.00",
        },
        last_shift_no: 214,
      },
    };
    const sync = await installSyncStub(page, {
      session: posBffSession(),
      pull: opsPull(undefined, shiftSnapshot),
      onEvent: (e) =>
        e.type === "shift.closed"
          ? { server: { id: OPS_SHIFT, shift_no: 214, z_report: zReport("500000.00", "0.00") } }
          : null,
    });
    await seedOps(page, sync, "/pos/shift/close", {
      openingCash: "500000.00",
      pull: opsPull(undefined, shiftSnapshot),
    });
    await page.getByTestId("close-shift").click();
    await page.getByRole("button", { name: "Ha, yopish" }).click();
    await page.getByTestId("counted-cash-input").fill("500000");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("pos-z-report")).toBeVisible({ timeout: 15_000 });
    // the pull snapshot still says «open» — POS-01 must not adopt it
    await page.goto("/pos/login");
    await expect(page.getByTestId("opening-cash")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("open-shift").click();
    await expect.poll(() => events(sync, "shift.opened").length).toBe(1);
    const opened = events(sync, "shift.opened")[0];
    expect(opened?.payload).toMatchObject({ shift_no: 215 });
    expect(opened?.payload.id).not.toBe(OPS_SHIFT);
  });

  test("an unresolved card attempt blocks the close (CARD_OUTCOME_UNKNOWN)", async ({ page }) => {
    const sync = await installSyncStub(page, { session: posBffSession(), pull: opsPull() });
    await seedOps(page, sync, "/pos/login", { openingCash: "0.00" });
    await idbPut(page, "erp-pos", "card_attempts", {
      attempt_id: "0190a000-0000-7000-8000-0000000000ca",
      card_terminal_id: "0190a000-0000-7000-8000-0000000000t9",
      local_id: null,
      kind: "purchase",
      amount: "12000.00",
      client_event_id: null,
      status: "unknown",
      started_at: new Date().toISOString(),
    });
    await page.goto("/pos/shift/close");
    await expect(page.getByTestId("close-blocked-card")).toBeVisible();
    await expect(page.getByTestId("close-shift")).toBeDisabled();
    expect(events(sync, "shift.closed")).toHaveLength(0);
  });
});
