import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { isOfflineError } from "../lib/errors.ts";
import { enqueueEvent } from "../outbox/enqueue.ts";
import { posDb } from "../runtime.ts";
import { CASHIER, DEVICE, SHIFT_ID, setupOffline, teardownOffline, type TestEnv } from "../testing/setup.ts";
import { $fiscalLadder, computeFiscalLadder, fiscalLadderLevel, refreshFiscalLadder } from "./ladder.ts";

const HOUR = 60 * 60 * 1000;
const REGISTER = DEVICE.cashRegisterId ?? "";
const fiscalSale = (n: number) =>
  enqueueEvent(
    "sale.created",
    { id: `s${n}`, shift_id: SHIFT_ID },
    { actorUserId: CASHIER, receiptSeq: { cashRegisterId: REGISTER, shiftId: SHIFT_ID } },
  );

let env: TestEnv;
beforeEach(async () => {
  env = await setupOffline();
});
afterEach(teardownOffline);

describe("fiscalLadderLevel (16 §6, qaror #43)", () => {
  it("maps elapsed hours to ok / warn24 / red40 / modal46 / blocked48", () => {
    const start = "2026-10-14T00:00:00.000Z";
    const at = (h: number) => Date.parse(start) + h * HOUR;
    expect(fiscalLadderLevel(null, at(100))).toBe("ok");
    expect(fiscalLadderLevel(start, at(23.99))).toBe("ok");
    expect(fiscalLadderLevel(start, at(24))).toBe("warn24");
    expect(fiscalLadderLevel(start, at(40))).toBe("red40");
    expect(fiscalLadderLevel(start, at(46))).toBe("modal46");
    expect(fiscalLadderLevel(start, at(47.99))).toBe("modal46");
    expect(fiscalLadderLevel(start, at(48))).toBe("blocked48");
  });
});

describe("$fiscalLadder and the local 48 h block", () => {
  it("50 h simulation: warns, blocks new fiscal documents at 48 h, keeps non-fiscal events and unblocks after the ack", async () => {
    const first = await fiscalSale(1);
    env.clock.advance(24 * HOUR);
    expect((await refreshFiscalLadder()).level).toBe("warn24");
    expect($fiscalLadder.getState().level).toBe("warn24");
    env.clock.advance(16 * HOUR);
    expect((await computeFiscalLadder()).level).toBe("red40");
    env.clock.advance(6 * HOUR);
    expect((await computeFiscalLadder()).level).toBe("modal46");
    await fiscalSale(2); // the modal does not stop the sale
    env.clock.advance(4 * HOUR); // 50 h
    const ladder = await computeFiscalLadder();
    expect(ladder.level).toBe("blocked48");
    expect(ladder.oldestUnackedAt).toBe(first.createdAt);

    await expect(fiscalSale(3)).rejects.toSatisfy((e) => isOfflineError(e, "FISCAL_OFFLINE_48H_BLOCKED"));
    // non-fiscal events and a debt-only sale (no receipt) still go to the outbox
    await enqueueEvent("cash_movement.created", { amount: "1000.00" }, { actorUserId: CASHIER });
    await enqueueEvent("sale.created", { id: "debt-only", receipt_seq: null }, { actorUserId: CASHIER });

    // OFD acks arrive for every receipt → unblocked
    await posDb()
      .outbox.toCollection()
      .modify((row) => {
        row.fiscal_unacked = 0;
        row.ofd_acked_at = new Date(env.clock.now).toISOString();
      });
    expect((await computeFiscalLadder()).level).toBe("ok");
    await expect(fiscalSale(4)).resolves.toMatchObject({ receiptSeq: 3 });
  });

  it("uses the server's last_unacked_receipt_at when it is older, and the trusted clock against clock rollback", async () => {
    await posDb().fiscal.put({
      id: REGISTER,
      fm_state: "ok",
      last_unacked_receipt_at: new Date(env.clock.now - 47 * HOUR).toISOString(),
    });
    expect((await computeFiscalLadder()).level).toBe("modal46");
    // the server told us it is 2 h later than the local clock: moving the clock back does not help
    await posDb().meta.put({ key: "clock.max_seen_time", value: env.clock.now + 2 * HOUR });
    env.clock.advance(-5 * HOUR);
    expect((await computeFiscalLadder()).level).toBe("blocked48");
  });
});
