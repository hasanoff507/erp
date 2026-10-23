/**
 * Bosqich 3 review fixes (review/ACCEPTED.md): SYNC-01, SYNC-02 (F-1), SYNC-08, SYNC-09, SYNC-11,
 * SYNC-12, SEC-07, SEC-09, ACC-01 (device part, F-2).
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { META } from "../db/meta.ts";
import { deviceIdentity, identityMatchesSession } from "../device-settings.ts";
import { computeFiscalLadder, refreshFiscalLadder } from "../fiscal/ladder.ts";
import { backgroundIdle } from "../lib/background.ts";
import { lastClockReset, observeServerTime } from "../lib/clock.ts";
import { SYNC_PUSH_LOCK, withLock } from "../lib/locks.ts";
import { logout, wipePosForLogout } from "../lifecycle/logout.ts";
import { enqueueEvent } from "../outbox/enqueue.ts";
import { outbox } from "../outbox/queries.ts";
import { verifyLocalPin } from "../pin/local-pin.ts";
import { cardAttempts } from "../repos/card-attempts.ts";
import { shift } from "../repos/reference.ts";
import { configureOffline, posDb } from "../runtime.ts";
import { rejected } from "../testing/fake-sync-server.ts";
import { CASHIER, DEVICE, SHIFT_ID, setupOffline, teardownOffline, type TestEnv } from "../testing/setup.ts";
import { LOCK_RETRY_MS, nextPushAt, runPush, startSyncEngine, syncIdle } from "./engine.ts";
import { pushNow } from "./push.ts";

const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;
const REGISTER = DEVICE.cashRegisterId ?? "";
const V1234 = "pbkdf2_sha256$1000$AAECAwQFBgcICQoLDA0ODw==$IkDqKiJ1SjxGEDVu+OTXrPJa8qw9LRGGbel6i3gSxSw=";

const fiscalSale = (id: string, extra: Record<string, unknown> = {}) =>
  enqueueEvent(
    "sale.created",
    { id, shift_id: SHIFT_ID, ...extra },
    { actorUserId: CASHIER, receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID } },
  );

let env: TestEnv;
beforeEach(async () => {
  env = await setupOffline();
});
afterEach(teardownOffline);

describe("SYNC-02 / F-1: a non-retryable rejection without fiscal_result leaves the 48 h timer", () => {
  it("rejected without fiscal_result → fiscal_unacked 0, escalated, still unsynced and visible", async () => {
    const a = await fiscalSale("a");
    env.server.handler = (e) => rejected(e, "VALIDATION_ERROR", false);
    await pushNow();
    const row = await outbox.get(a.clientEventId);
    expect(row).toMatchObject({ status: "rejected", fiscal_unacked: 0, escalated: 1, unsynced: 1 });
    expect((await outbox.summary()).escalated).toBe(1);
  });

  it("an FM-signed event (fiscal_result present) keeps counting", async () => {
    const a = await fiscalSale("a", { fiscal_result: { fm_receipt_seq: 7, fiscal_sign: "x" } });
    env.server.handler = (e) => rejected(e, "RECEIPT_SEQ_CONFLICT", false);
    await pushNow();
    expect(await outbox.get(a.clientEventId)).toMatchObject({ fiscal_unacked: 1, escalated: 1 });
  });

  it("a 49 h old rejected sale without fiscal_result leaves the ladder at ok; a later accepted retry counts again", async () => {
    const a = await fiscalSale("a");
    env.server.handler = (e) => rejected(e, "VALIDATION_ERROR", false);
    await pushNow();
    env.clock.advance(49 * HOUR);
    expect((await computeFiscalLadder()).level).toBe("ok");
    await outbox.retry(a.clientEventId);
    expect((await outbox.get(a.clientEventId))?.escalated).toBe(0);
    env.server.handler = () => null;
    await pushNow();
    expect(await outbox.get(a.clientEventId)).toMatchObject({ status: "accepted", fiscal_unacked: 1 });
    expect((await computeFiscalLadder()).level).toBe("blocked48");
  });
});

describe("ACC-01 / F-2: shift.closed is held behind earlier events of the shift", () => {
  it("a retryably rejected return holds the close; the close goes once the return is accepted", async () => {
    const ret = await enqueueEvent(
      "return.created",
      { id: "r1", shift_id: SHIFT_ID },
      { actorUserId: CASHIER, receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID } },
    );
    const close = await enqueueEvent("shift.closed", { shift_id: SHIFT_ID }, { actorUserId: CASHIER });
    env.server.handler = (e) =>
      e.client_event_id === ret.clientEventId ? rejected(e, "SALE_NOT_FOUND", true) : null;
    await pushNow();
    expect(env.server.pushRequests[0]?.events.map((e) => e.client_event_id)).toEqual([ret.clientEventId]);
    expect((await outbox.get(close.clientEventId))?.status).toBe("pending");
    expect(await outbox.heldShiftCloses()).toEqual([
      { clientEventId: close.clientEventId, shiftId: SHIFT_ID, waitingFor: [ret.clientEventId] },
    ]);

    env.server.handler = () => null;
    env.clock.advance(10 * 60_000);
    await pushNow();
    expect(env.server.committed).toEqual([ret.clientEventId, close.clientEventId]);
    expect(await outbox.heldShiftCloses()).toEqual([]);
  });

  it("an escalated (non-retryable) earlier row no longer holds the close; other shifts never do", async () => {
    const bad = await enqueueEvent("cash_movement.created", { shift_id: SHIFT_ID }, { actorUserId: CASHIER });
    await enqueueEvent("cash_movement.created", { shift_id: "other-shift" }, { actorUserId: CASHIER });
    env.server.handler = (e) =>
      e.client_event_id === bad.clientEventId ? rejected(e, "VALIDATION_ERROR", false) : null;
    await pushNow();
    const close = await enqueueEvent("shift.closed", { shift_id: SHIFT_ID }, { actorUserId: CASHIER });
    await pushNow();
    expect((await outbox.get(close.clientEventId))?.status).toBe("accepted");
  });
});

describe("SYNC-08: trusted clock for fiscal created_at; server time resets a runaway clock", () => {
  it("(a) local clock +1 year once, then server time observed → a new receipt is ok", async () => {
    const real = env.clock.now;
    env.clock.now = real + 365 * DAY;
    await refreshFiscalLadder(); // the runaway time becomes the trusted maximum
    env.clock.now = real;
    await observeServerTime(real);
    expect(await lastClockReset()).toMatchObject({ to: real });
    await fiscalSale("a");
    expect((await computeFiscalLadder()).level).toBe("ok");
  });

  it("(b) local clock 2 days behind the server → created_at uses the trusted time, level ok", async () => {
    await observeServerTime(env.clock.now + 2 * DAY);
    const a = await fiscalSale("a");
    expect(a.createdAt).toBe(new Date(env.clock.now + 2 * DAY).toISOString());
    expect((await computeFiscalLadder()).level).toBe("ok");
  });

  it("(c) clock moved back without server contact → the timer does not shrink", async () => {
    await fiscalSale("a");
    env.clock.advance(49 * HOUR);
    await refreshFiscalLadder(); // trusted time = local now
    env.clock.advance(-10 * HOUR); // clock moved back, no server contact
    expect((await computeFiscalLadder()).level).toBe("blocked48");
  });
});

describe("SYNC-09: second receipt number in the same lock", () => {
  it("count 2 → consecutive receipt_seq / credit_receipt_seq; target credit_receipt_seq for a debt-only sale", async () => {
    const both = await enqueueEvent(
      "sale.created",
      { id: "s1", shift_id: SHIFT_ID },
      { actorUserId: CASHIER, receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID, count: 2 } },
    );
    expect([both.receiptSeq, both.creditReceiptSeq]).toEqual([1, 2]);
    const row = await outbox.get(both.clientEventId);
    expect(row?.payload).toMatchObject({ receipt_seq: 1, credit_receipt_seq: 2 });

    const creditOnly = await enqueueEvent(
      "sale.created",
      { id: "s2", shift_id: SHIFT_ID, receipt_seq: null },
      {
        actorUserId: CASHIER,
        receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID, target: "credit_receipt_seq" },
      },
    );
    expect([creditOnly.receiptSeq, creditOnly.creditReceiptSeq]).toEqual([null, 3]);
    expect((await outbox.get(creditOnly.clientEventId))?.payload).toMatchObject({
      receipt_seq: null,
      credit_receipt_seq: 3,
    });
    expect((await outbox.get(creditOnly.clientEventId))?.fiscal).toBe(true);

    await logout({ confirmUnsynced: true }); // counters persist across the wipe
    configureOffline({ dbNames: env.names });
    expect((await fiscalSale("s3")).receiptSeq).toBe(4);
  });
});

describe("SYNC-11: a tab that cannot take the push lock retries soon", () => {
  it("lock held by another tab → push rescheduled within ~1 s", async () => {
    startSyncEngine();
    await backgroundIdle();
    await syncIdle();
    let release!: () => void;
    const held = withLock(SYNC_PUSH_LOCK, () => new Promise<void>((r) => (release = r)));
    await enqueueEvent("sale.created", { id: "s1" }, { actorUserId: CASHIER });
    await runPush();
    expect(nextPushAt()).toBe(env.clock.now + LOCK_RETRY_MS);
    release();
    await held;
  });
});

describe("SYNC-12: export carries card attempts without card data", () => {
  it("card_attempts are exported, deny-listed keys stripped", async () => {
    await cardAttempts.put({
      attempt_id: "a1",
      card_terminal_id: "t1",
      kind: "purchase",
      amount: "1000.00",
      client_event_id: null,
      status: "unknown",
      started_at: new Date(env.clock.now).toISOString(),
      result: { card_mask: "8600****1234", rrn: "123456789012" },
    });
    // a row written around the guard (old client) must not leak through the export
    await posDb().card_attempts.update("a1", { pan: "8600123412341234" });
    const exported = await outbox.export();
    expect(exported.card_attempts).toHaveLength(1);
    expect(exported.card_attempts[0]).toMatchObject({
      attempt_id: "a1",
      result: { card_mask: "8600****1234" },
    });
    expect(JSON.stringify(exported.card_attempts)).not.toContain("8600123412341234");
  });
});

describe("SEC-09: PIN lockout survives logout and counts parallel failures", () => {
  it("5 failures → locked, logout + new session → still locked; parallel failures both count", async () => {
    const staff = {
      user_id: CASHIER,
      full_name: "K",
      role_codes: [],
      branch_ids: [],
      active: true,
      must_change_pin: false,
      pin_local_hash: V1234,
      permissions: [],
    };
    await posDb().permissions.put(staff);
    await Promise.all([verifyLocalPin(CASHIER, "0000"), verifyLocalPin(CASHIER, "0001")]);
    expect((await verifyLocalPin(CASHIER, "0002")).ok).toBe(false);
    const third = await verifyLocalPin(CASHIER, "0003");
    expect(third).toEqual({ ok: false, reason: "invalid", attemptsLeft: 1 });
    expect((await verifyLocalPin(CASHIER, "0004")).ok).toBe(false); // 5th → locked

    await logout({ confirmUnsynced: true });
    configureOffline({ dbNames: env.names });
    await posDb().permissions.put(staff);
    expect(await verifyLocalPin(CASHIER, "1234")).toMatchObject({ ok: false, reason: "locked" });
  });
});

describe("SYNC-01: a locally closed shift is not re-adopted from the pulled snapshot", () => {
  it("markServerClosed clears open_shift; closedLocallyIds lists closed and unsynced-closing shifts", async () => {
    await posDb().meta.put({
      key: META.serverShift,
      value: { cash_register_id: REGISTER, open_shift: { id: SHIFT_ID, shift_no: 3 }, last_shift_no: 3 },
    });
    await shift.markServerClosed("another");
    expect((await shift.server())?.open_shift?.id).toBe(SHIFT_ID);
    await shift.markServerClosed(SHIFT_ID);
    expect((await shift.server())?.open_shift).toBeNull();
    expect((await shift.server())?.last_shift_no).toBe(3);

    await shift.save({
      id: "old",
      cash_register_id: REGISTER,
      shift_no: 2,
      opened_at: "x",
      opened_by: CASHIER,
      status: "closed",
    });
    await enqueueEvent("shift.closed", { shift_id: SHIFT_ID }, { actorUserId: CASHIER });
    expect([...(await shift.closedLocallyIds())].sort()).toEqual(["old", SHIFT_ID].sort());
  });
});

describe("SEC-07: cached POS data bound to the session", () => {
  it("identity must match session device and tenant; BO logout on a device browser wipes erp-pos", async () => {
    const ok = { tenant: { id: DEVICE.tenantId }, device: { id: DEVICE.deviceId } };
    expect(identityMatchesSession(DEVICE, ok)).toBe(true);
    expect(identityMatchesSession(DEVICE, { ...ok, tenant: { id: "other" } })).toBe(false);
    expect(identityMatchesSession(DEVICE, { ...ok, device: null })).toBe(false);
    expect(identityMatchesSession(null, ok)).toBe(false);
    expect(await deviceIdentity.matchesSession(ok)).toBe(true);

    await enqueueEvent("sale.created", { id: "s1" }, { actorUserId: CASHIER });
    expect(await wipePosForLogout(false)).toEqual({ kind: "needs_confirm", pending: 1, rejected: 0 });
    expect(await posDb().outbox.count()).toBe(1); // nothing wiped without the confirmation
    expect(await wipePosForLogout(true)).toEqual({ kind: "wiped" });
    configureOffline({ dbNames: env.names });
    expect(await posDb().outbox.count()).toBe(0);
    expect(await deviceIdentity.get()).toEqual(DEVICE); // erp-device kept
    await cardAttempts.put({
      attempt_id: "a9",
      card_terminal_id: "t1",
      kind: "purchase",
      amount: "1.00",
      client_event_id: null,
      status: "pending",
      started_at: "2026-10-14T00:00:00Z",
    });
    expect(await wipePosForLogout(true)).toEqual({ kind: "blocked_card", cardAttempts: 1 });
    await deviceIdentity.clear();
    expect(await wipePosForLogout(true)).toEqual({ kind: "not_device" });
  });
});
