import Dexie from "dexie";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { deviceIdentity, deviceSettings } from "../device-settings.ts";
import { quotaWarning } from "../events.ts";
import { isOfflineError } from "../lib/errors.ts";
import { enqueueEvent } from "../outbox/enqueue.ts";
import { outbox } from "../outbox/queries.ts";
import { cardAttempts } from "../repos/card-attempts.ts";
import { salesHistory } from "../repos/reference.ts";
import { configureOffline, posDb } from "../runtime.ts";
import { pushNow } from "../sync/push.ts";
import { CASHIER, DEVICE, SHIFT_ID, setupOffline, teardownOffline, type TestEnv } from "../testing/setup.ts";
import { logout, logoutCheck, wipeAfterRevoke } from "./logout.ts";
import { checkStorageQuota, quotaLevel, runRetention } from "./retention.ts";

const DAY = 24 * 60 * 60 * 1000;
const REGISTER = DEVICE.cashRegisterId ?? "";

let env: TestEnv;
beforeEach(async () => {
  env = await setupOffline();
});
afterEach(teardownOffline);

async function dbExists(name: string): Promise<boolean> {
  return (await Dexie.getDatabaseNames()).includes(name);
}

describe("logout (16 §12)", () => {
  it("is blocked while card_attempts is not empty", async () => {
    await cardAttempts.put({
      attempt_id: "a1",
      card_terminal_id: "t1",
      kind: "purchase",
      amount: "1000.00",
      client_event_id: null,
      status: "unknown",
      started_at: new Date(env.clock.now).toISOString(),
    });
    expect((await logoutCheck()).blocker).toBe("card_attempts");
    await expect(logout({ confirmUnsynced: true })).rejects.toSatisfy((e) =>
      isOfflineError(e, "CARD_OUTCOME_UNKNOWN"),
    );
    expect(await cardAttempts.count()).toBe(1);
  });

  it("asks for confirmation (export offered) while the outbox has unsynced events, then deletes only erp-pos", async () => {
    await enqueueEvent("sale.created", { id: "s1" }, { actorUserId: CASHIER });
    await deviceSettings.set("printer.transport", "agent");
    expect(await logoutCheck()).toMatchObject({ blocker: null, pending: 1 });
    await expect(logout({ confirmUnsynced: false })).rejects.toSatisfy((e) =>
      isOfflineError(e, "OUTBOX_NOT_EMPTY"),
    );
    expect((await outbox.export()).events).toHaveLength(1);

    await logout({ confirmUnsynced: true });
    expect(await dbExists(env.names.pos)).toBe(false);
    configureOffline({ dbNames: env.names });
    expect(await deviceSettings.get("printer.transport")).toBe("agent");
    expect(await deviceIdentity.get()).toEqual(DEVICE);
  });

  it("DEVICE_REVOKED wipe deletes both databases", async () => {
    await enqueueEvent("sale.created", { id: "s1" }, { actorUserId: CASHIER });
    await deviceSettings.set("pos.catalog_view", "grid");
    await wipeAfterRevoke();
    expect(await dbExists(env.names.pos)).toBe(false);
    expect(await dbExists(env.names.device)).toBe(false);
  });
});

describe("retention (16 §10)", () => {
  it("drops accepted events after 7 days but never pending, rejected or OFD-unacked fiscal events", async () => {
    const fiscal = await enqueueEvent(
      "sale.created",
      { id: "f", shift_id: SHIFT_ID },
      { actorUserId: CASHIER, receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID } },
    );
    const plain = await enqueueEvent("cash_movement.created", { id: "c" }, { actorUserId: CASHIER });
    const pending = await enqueueEvent("cash_movement.created", { id: "p" }, { actorUserId: CASHIER });
    await pushNow();
    await posDb()
      .outbox.where("client_event_id")
      .equals(pending.clientEventId)
      .modify({ status: "rejected", unsynced: 1 });
    env.clock.advance(8 * DAY);
    expect((await runRetention()).outboxDeleted).toBe(1);
    expect(await outbox.get(plain.clientEventId)).toBeUndefined();
    expect(await outbox.get(fiscal.clientEventId)).toBeDefined(); // no ofd_acked_at yet
    expect(await outbox.get(pending.clientEventId)).toBeDefined();

    await posDb()
      .outbox.where("client_event_id")
      .equals(fiscal.clientEventId)
      .modify({ ofd_acked_at: "x", fiscal_unacked: 0 });
    expect((await runRetention()).outboxDeleted).toBe(1);
  });

  it("keeps a 90-day receipt history window", async () => {
    await enqueueEvent(
      "sale.created",
      { id: "old" },
      { actorUserId: CASHIER, history: { id: "old", kind: "sale", total: "1.00" } },
    );
    env.clock.advance(91 * DAY);
    await enqueueEvent(
      "sale.created",
      { id: "new" },
      { actorUserId: CASHIER, history: { id: "new", kind: "sale", total: "2.00" } },
    );
    expect((await runRetention()).historyDeleted).toBe(1);
    expect((await salesHistory.list()).map((h) => h.id)).toEqual(["new"]);
  });

  it("quota: 80 % warns, 95 % trims the history cache, never the outbox", async () => {
    expect(quotaLevel(0.5)).toBe("ok");
    expect(quotaLevel(0.8)).toBe("warn80");
    expect(quotaLevel(0.96)).toBe("critical95");
    const seen = vi.fn();
    const unwatch = quotaWarning.watch(seen);
    await enqueueEvent(
      "sale.created",
      { id: "h" },
      { actorUserId: CASHIER, history: { id: "h", kind: "sale", total: "1.00" } },
    );
    env.clock.advance(20 * DAY);
    const state = await checkStorageQuota(() => Promise.resolve({ usage: 97, quota: 100 }));
    expect(state.level).toBe("critical95");
    expect(seen).toHaveBeenCalledWith(state);
    expect(await salesHistory.get("h")).toBeUndefined();
    expect(await posDb().outbox.count()).toBe(1);
    unwatch.unsubscribe();
  });
});
