import { validate as uuidValidate, version as uuidVersion, v7 as uuidv7 } from "uuid";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { deviceIdentity, deviceSettings, readCounterFloors } from "../device-settings.ts";
import { isOfflineError } from "../lib/errors.ts";
import { logout } from "../lifecycle/logout.ts";
import { cardAttempts } from "../repos/card-attempts.ts";
import { fiscal, markingCodes, salesHistory } from "../repos/reference.ts";
import { configureOffline, posDb } from "../runtime.ts";
import { CASHIER, DEVICE, SHIFT_ID, setupOffline, teardownOffline, type TestEnv } from "../testing/setup.ts";
import { enqueueEvent } from "./enqueue.ts";
import { outbox } from "./queries.ts";

const REGISTER = DEVICE.cashRegisterId ?? "";
const sale = (n: number) => ({
  id: `sale-${n}`,
  shift_id: SHIFT_ID,
  lines: [],
  payments: [],
  receipt_seq: null,
});

let env: TestEnv;
beforeEach(async () => {
  env = await setupOffline();
});
afterEach(teardownOffline);

describe("enqueueEvent (16 §2, §3.3, §11)", () => {
  it("writes a pending envelope with UUIDv7 id, monotonic seq and device receipt_seq in the payload root", async () => {
    const first = await enqueueEvent("sale.created", sale(1), {
      actorUserId: CASHIER,
      receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID },
    });
    const second = await enqueueEvent("sale.created", sale(2), {
      actorUserId: CASHIER,
      receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID },
    });
    expect(uuidValidate(first.clientEventId)).toBe(true);
    expect(uuidVersion(first.clientEventId)).toBe(7);
    expect([first.seq, second.seq]).toEqual([1, 2]);
    expect([first.receiptSeq, second.receiptSeq]).toEqual([1, 2]);

    const row = await outbox.get(second.clientEventId);
    expect(row).toMatchObject({
      status: "pending",
      device_id: DEVICE.deviceId,
      actor_user_id: CASHIER,
      type: "sale.created",
      seq: 2,
      receipt_seq: 2,
      fiscal: true,
      fiscal_unacked: 1,
      created_at: new Date(env.clock.now).toISOString(),
    });
    expect(row?.payload.receipt_seq).toBe(2);
  });

  it("keeps receipt_seq per (cash register, shift) and null for a debt-only sale", async () => {
    await enqueueEvent("sale.created", sale(1), {
      actorUserId: CASHIER,
      receiptSeq: { cashRegisterId: REGISTER, shiftId: "s-a" },
    });
    const other = await enqueueEvent("sale.created", sale(2), {
      actorUserId: CASHIER,
      receiptSeq: { cashRegisterId: REGISTER, shiftId: "s-b" },
    });
    const debtOnly = await enqueueEvent("sale.created", sale(3), { actorUserId: CASHIER });
    expect(other.receiptSeq).toBe(1);
    expect(debtOnly.receiptSeq).toBeNull();
    expect((await outbox.get(debtOnly.clientEventId))?.fiscal).toBe(false);
  });

  it("never hands out the same seq twice under concurrent writers (Web Lock)", async () => {
    const results = await Promise.all(
      Array.from({ length: 40 }, (_, i) =>
        enqueueEvent("sale.created", sale(i), {
          actorUserId: CASHIER,
          receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID },
        }),
      ),
    );
    const seqs = results.map((r) => r.seq).sort((a, b) => a - b);
    const receipts = results.map((r) => r.receiptSeq ?? 0).sort((a, b) => a - b);
    expect(seqs).toEqual(Array.from({ length: 40 }, (_, i) => i + 1));
    expect(receipts).toEqual(Array.from({ length: 40 }, (_, i) => i + 1));
  });

  it("refuses without a registered device and refuses unknown types", async () => {
    await deviceIdentity.clear();
    await expect(enqueueEvent("sale.created", sale(1), { actorUserId: CASHIER })).rejects.toSatisfy((e) =>
      isOfflineError(e, "DEVICE_NOT_REGISTERED"),
    );
    await deviceIdentity.set(DEVICE);
    await expect(
      enqueueEvent("sale.deleted" as "sale.created", sale(1), { actorUserId: CASHIER }),
    ).rejects.toSatisfy((e) => isOfflineError(e, "UNKNOWN_EVENT_TYPE"));
  });

  it("removes approved card attempts in the same transaction and refuses unresolved ones (16 §2.1)", async () => {
    await cardAttempts.put({
      attempt_id: "att-1",
      card_terminal_id: "term-1",
      kind: "purchase",
      amount: "10000.00",
      client_event_id: null,
      status: "approved",
      started_at: new Date(env.clock.now).toISOString(),
      result: { status: "approved", card_mask: "8600****1234", rrn: "123456789012" },
    });
    await cardAttempts.put({
      attempt_id: "att-2",
      card_terminal_id: "term-1",
      kind: "purchase",
      amount: "5000.00",
      client_event_id: null,
      status: "unknown",
      started_at: new Date(env.clock.now).toISOString(),
    });
    await expect(
      enqueueEvent("sale.created", sale(1), { actorUserId: CASHIER, removeCardAttemptIds: ["att-2"] }),
    ).rejects.toSatisfy((e) => isOfflineError(e, "CARD_OUTCOME_UNKNOWN"));
    expect(await posDb().outbox.count()).toBe(0); // the failed transaction wrote nothing
    expect((await posDb().meta.get("outbox.seq"))?.value).toBeUndefined();

    await enqueueEvent("sale.created", sale(2), { actorUserId: CASHIER, removeCardAttemptIds: ["att-1"] });
    expect(await cardAttempts.get("att-1")).toBeUndefined();
    expect(await cardAttempts.get("att-2")).toBeDefined();
  });

  it("stores offline-sold marking codes and a history row with the event (16 §7, §10)", async () => {
    const r = await enqueueEvent("sale.created", sale(1), {
      actorUserId: CASHIER,
      markingCodes: ["010478000012345621abc"],
      history: { id: "sale-1", kind: "sale", total: "12000.00" },
    });
    expect(await markingCodes.isUsed("010478000012345621abc")).toBe(true);
    expect(await markingCodes.isUsed("other")).toBe(false);
    const history = await salesHistory.get("sale-1");
    expect(history).toMatchObject({ client_event_id: r.clientEventId, total: "12000.00" });
  });

  it("keeps seq and receipt_seq monotonic across a logout wipe (floors in erp-device)", async () => {
    await enqueueEvent("sale.created", sale(1), {
      actorUserId: CASHIER,
      receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID },
    });
    await enqueueEvent("sale.created", sale(2), {
      actorUserId: CASHIER,
      receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID },
    });
    await deviceSettings.set("pos.catalog_view", "list");
    await logout({ confirmUnsynced: true });
    expect((await readCounterFloors()).seq).toBe(2);

    configureOffline({ dbNames: env.names });
    expect(await deviceIdentity.get()).toEqual(DEVICE); // erp-device kept
    expect(await deviceSettings.get("pos.catalog_view")).toBe("list");
    expect(await posDb().outbox.count()).toBe(0); // erp-pos deleted
    const next = await enqueueEvent("sale.created", sale(3), {
      actorUserId: CASHIER,
      receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID },
    });
    expect(next.seq).toBe(3);
    expect(next.receiptSeq).toBe(3);
  });
});

describe("outbox queries (POS-12)", () => {
  it("lists in seq order, summarises and retries a rejected event", async () => {
    const a = await enqueueEvent(
      "shift.opened",
      { shift_id: SHIFT_ID, shift_no: 1 },
      { actorUserId: CASHIER },
    );
    await enqueueEvent("sale.created", sale(1), { actorUserId: CASHIER });
    await posDb()
      .outbox.where("client_event_id")
      .equals(a.clientEventId)
      .modify({ status: "rejected", retryable: false });
    expect((await outbox.list()).map((r) => r.seq)).toEqual([1, 2]);
    expect(await outbox.summary()).toMatchObject({ pending: 1, rejected: 1, rejectedRetryable: 0 });
    expect((await outbox.list({ status: "rejected" })).map((r) => r.seq)).toEqual([1]);
    await outbox.retry(a.clientEventId);
    expect((await outbox.get(a.clientEventId))?.status).toBe("pending");
    const exported = await outbox.export();
    expect(exported.device_id).toBe(DEVICE.deviceId);
    expect(exported.events).toHaveLength(2);
  });
});

describe("enqueueEvent with a pre-allocated clientEventId (card flow, 16 §2.1)", () => {
  it("uses a given UUIDv7, refuses non-v7 ids and duplicates without writing anything", async () => {
    const id = uuidv7();
    const r = await enqueueEvent("sale.created", sale(1), { actorUserId: CASHIER, clientEventId: id });
    expect(r.clientEventId).toBe(id);
    expect((await outbox.get(id))?.seq).toBe(1);
    await expect(
      enqueueEvent("sale.created", sale(2), { actorUserId: CASHIER, clientEventId: id }),
    ).rejects.toSatisfy((e) => isOfflineError(e, "VALIDATION_ERROR"));
    await expect(
      enqueueEvent("sale.created", sale(3), {
        actorUserId: CASHIER,
        clientEventId: "6f1c2b0e-8f0a-4c2e-9d1a-2b3c4d5e6f70", // v4
      }),
    ).rejects.toSatisfy((e) => isOfflineError(e, "VALIDATION_ERROR"));
    expect(await posDb().outbox.count()).toBe(1);
    expect((await posDb().meta.get("outbox.seq"))?.value).toBe(1);
  });
});

describe("fiscal.receiptFor (POS-04)", () => {
  it("finds the pulled fiscal receipt by client_event_id", async () => {
    await posDb().fiscal_receipts.put({
      id: "fr1",
      client_event_id: "ev-1",
      status: "fiscalized",
      qr_url: "https://ofd/x",
    });
    expect((await fiscal.receiptFor("ev-1"))?.id).toBe("fr1");
    expect(await fiscal.receiptFor("ev-2")).toBeUndefined();
  });
});
