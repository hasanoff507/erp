/**
 * Read repositories over the pulled reference data (16 §1): customers, stock (display only), limits,
 * staff/permissions, settings + card terminals, server/local shift, fiscal register state, marking
 * codes (local duplicate check, 16 §7), receipt history (90 days, 16 §10).
 */
import Dexie from "dexie";

import { META } from "../db/meta.ts";
import { memoryRows } from "../lib/memory-index.ts";
import { queryWords } from "../lib/search.ts";
import { posDb } from "../runtime.ts";
import type {
  CardTerminalRow,
  CustomerRow,
  FiscalReceiptRow,
  FiscalRegisterRow,
  LimitRow,
  LocalShift,
  PosSettings,
  SalesHistoryRow,
  ServerShiftSnapshot,
  StaffRow,
  StockRow,
  WeightBarcodeTemplate,
} from "../types.ts";

export const customers = {
  async search(query: string, opts: { limit?: number } = {}): Promise<CustomerRow[]> {
    const limit = opts.limit ?? 30;
    const words = queryWords(query.replace(/^\+/, ""));
    const all = await memoryRows<CustomerRow>("customers", async (table) =>
      (await table.toArray()).sort((x, y) => x.name.localeCompare(y.name)),
    );
    if (words.length === 0) return all.slice(0, limit);
    const rows: CustomerRow[] = [];
    for (const c of all) {
      if (words.every((w) => c.tokens.some((t) => t.startsWith(w)))) rows.push(c);
      if (rows.length >= limit) break;
    }
    return rows;
  },
  get(id: string): Promise<CustomerRow | undefined> {
    return posDb().customers.get(id);
  },
};

export const stock = {
  forProduct(productId: string): Promise<StockRow[]> {
    return posDb().stock.where("product_id").equals(productId).toArray();
  },
};

export const limits = {
  async forUser(userId: string): Promise<Record<string, string | null>> {
    const row: LimitRow | undefined = await posDb().limits.get(userId);
    return row?.limits ?? {};
  },
  /** `undefined` = the user has no such permission limit row; `null` = unlimited. */
  async value(userId: string, code: string): Promise<string | null | undefined> {
    const all = await limits.forUser(userId);
    return code in all ? (all[code] ?? null) : undefined;
  },
};

export const staff = {
  list(): Promise<StaffRow[]> {
    return posDb().permissions.toArray();
  },
  get(userId: string): Promise<StaffRow | undefined> {
    return posDb().permissions.get(userId);
  },
  async hasPermission(userId: string, code: string): Promise<boolean> {
    const row = await posDb().permissions.get(userId);
    return row !== undefined && row.active && row.permissions.some((p) => p.code === code);
  },
};

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

export const settings = {
  async get(): Promise<PosSettings> {
    const db = posDb();
    const raw = Object.fromEntries((await db.settings.toArray()).map((r) => [r.key, r.value]));
    const fallback = raw.card_manual_fallback;
    const precheck = raw.marking_precheck;
    const subscription = raw.subscription as { status?: unknown } | null | undefined;
    return {
      weightBarcodeTemplates: asArray<WeightBarcodeTemplate>(raw.weight_barcode_templates),
      weightBarcodeVersion:
        typeof raw.weight_barcode_version === "string" ? raw.weight_barcode_version : null,
      cardManualFallback:
        fallback === "allow" || fallback === "manager_approval" || fallback === "forbid"
          ? fallback
          : "manager_approval",
      cardTerminals: await db.card_terminals.toArray(),
      discountRules: asArray<Record<string, unknown>>(raw.discount_rules),
      markingPrecheck: precheck === "off" || precheck === "block" ? precheck : "warn",
      subscriptionStatus: typeof subscription?.status === "string" ? subscription.status : null,
      raw,
    };
  },
};

export const cardTerminals = {
  forRegister(cashRegisterId: string): Promise<CardTerminalRow[]> {
    return posDb().card_terminals.where("cash_register_id").equals(cashRegisterId).toArray();
  },
  all(): Promise<CardTerminalRow[]> {
    return posDb().card_terminals.toArray();
  },
};

export const shift = {
  /** The local open shift of this device (16 §1 `shift`). */
  async current(): Promise<LocalShift | null> {
    return (await posDb().shift.where("status").equals("open").first()) ?? null;
  },
  async save(value: LocalShift): Promise<void> {
    await posDb().shift.put(value);
  },
  async clear(): Promise<void> {
    await posDb().shift.clear();
  },
  /**
   * SYNC-01: after a local close the pulled snapshot may still show the shift as open until the
   * `shift.closed` event is synced and pulled again — clear it so a login does not re-adopt it.
   * Without `shiftId` any open shift is cleared; with it, only that one.
   */
  async markServerClosed(shiftId?: string): Promise<void> {
    const db = posDb();
    await db.transaction("rw", db.meta, async () => {
      const row = await db.meta.get(META.serverShift);
      const snapshot = row?.value as ServerShiftSnapshot | undefined;
      if (!snapshot?.open_shift) return;
      if (shiftId !== undefined && snapshot.open_shift.id !== shiftId) return;
      await db.meta.put({ key: META.serverShift, value: { ...snapshot, open_shift: null } });
    });
  },
  /**
   * SYNC-01: ids of shifts this device has closed — local rows with status `closed` plus the shifts of
   * `shift.closed` outbox events not yet accepted. A server `open_shift` in this set is treated as absent.
   */
  async closedLocallyIds(): Promise<Set<string>> {
    const db = posDb();
    const ids = new Set<string>();
    for (const row of await db.shift.where("status").equals("closed").toArray()) ids.add(row.id);
    const unsynced = await db.outbox
      .where("[unsynced+seq]")
      .between([1, Dexie.minKey], [1, Dexie.maxKey])
      .toArray();
    for (const event of unsynced)
      if (event.type === "shift.closed" && event.shift_id) ids.add(event.shift_id);
    return ids;
  },
  /** Server view of this register (pull `shift` snapshot). */
  async server(): Promise<ServerShiftSnapshot | null> {
    const row = await posDb().meta.get(META.serverShift);
    return (row?.value as ServerShiftSnapshot | undefined) ?? null;
  },
};

export const fiscal = {
  /** The pulled fiscal receipt of a local event (POS-04: sign, QR, status, id for receipt.reprinted). */
  receiptFor(clientEventId: string): Promise<FiscalReceiptRow | undefined> {
    return posDb().fiscal_receipts.where("client_event_id").equals(clientEventId).first();
  },
  register(cashRegisterId: string): Promise<FiscalRegisterRow | undefined> {
    return posDb().fiscal.get(cashRegisterId);
  },
};

export const markingCodes = {
  /** True when the code is sold / pending verification (server cache or sold offline here). */
  async isUsed(code: string): Promise<boolean> {
    const rows = await posDb().marking_codes.where("code").equals(code).toArray();
    return rows.some((r) => r.status === "sold" || r.status === "pending_verification");
  },
};

export const salesHistory = {
  async list(opts: { limit?: number; before?: string } = {}): Promise<SalesHistoryRow[]> {
    const db = posDb();
    const collection = opts.before
      ? db.sales_history.where("created_at").below(opts.before)
      : db.sales_history.where("created_at").between(Dexie.minKey, Dexie.maxKey);
    return collection
      .reverse()
      .limit(opts.limit ?? 50)
      .toArray();
  },
  get(id: string): Promise<SalesHistoryRow | undefined> {
    return posDb().sales_history.get(id);
  },
};
