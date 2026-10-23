/**
 * Dexie databases — 16-offline-sync.md §1 (tables), §12 (two databases):
 * - `erp-pos`: everything tenant/user related (catalog, customers, permissions, outbox, card_attempts…);
 *   deleted on logout.
 * - `erp-device`: `device_settings` only (printer, catalog view, agent token, device identity, counter
 *   floors) — no personal/tenant business data, kept on logout, deleted on DEVICE_REVOKED.
 *
 * Schema versions are append-only: add `this.version(N + 1).stores({...})` (+ `.upgrade()`), never edit
 * an existing version.
 */
import Dexie, { type Table } from "dexie";

import type {
  BarcodeRow,
  CardAttempt,
  CardTerminalRow,
  CategoryRow,
  CustomerRow,
  FiscalReceiptRow,
  FiscalRegisterRow,
  LimitRow,
  LocalShift,
  MarkingCodeRow,
  MetaRow,
  OutboxRow,
  PinLockoutRow,
  PriceRow,
  ProductRow,
  SalesHistoryRow,
  SettingRow,
  StaffRow,
  StockRow,
  UnitRow,
} from "../types.ts";

export const POS_DB_VERSION = 2;
export const DEVICE_DB_VERSION = 2;

export class PosDb extends Dexie {
  meta!: Table<MetaRow, string>;
  outbox!: Table<OutboxRow, number>;
  catalog!: Table<ProductRow, string>;
  categories!: Table<CategoryRow, string>;
  units!: Table<UnitRow, string>;
  barcodes!: Table<BarcodeRow, string>;
  prices!: Table<PriceRow, string>;
  customers!: Table<CustomerRow, string>;
  stock!: Table<StockRow, string>;
  limits!: Table<LimitRow, string>;
  /** 16 §1 `permissions`: staff of this branch with roles, permissions and the local PIN verifier. */
  permissions!: Table<StaffRow, string>;
  marking_codes!: Table<MarkingCodeRow, string>;
  fiscal!: Table<FiscalRegisterRow, string>;
  fiscal_receipts!: Table<FiscalReceiptRow, string>;
  settings!: Table<SettingRow, string>;
  card_terminals!: Table<CardTerminalRow, string>;
  shift!: Table<LocalShift, string>;
  card_attempts!: Table<CardAttempt, string>;
  sales_history!: Table<SalesHistoryRow, string>;

  constructor(name: string) {
    super(name);
    this.version(1).stores({
      meta: "key",
      outbox: "seq, &client_event_id, status, [unsynced+seq], [fiscal_unacked+created_at], result_at",
      catalog: "id, category_id, *tokens, code",
      categories: "id",
      units: "code",
      barcodes: "id, barcode, product_id",
      prices: "id, product_id, [product_id+branch_key]",
      customers: "id, *tokens, phone",
      stock: "id, product_id",
      limits: "user_id",
      permissions: "user_id",
      marking_codes: "id, code, status",
      fiscal: "id",
      fiscal_receipts: "id, client_event_id",
      settings: "key",
      card_terminals: "id, cash_register_id",
      shift: "id, status",
      card_attempts: "attempt_id, card_terminal_id, status, client_event_id",
      sales_history: "id, created_at, client_event_id",
      pin_lockouts: "user_id",
    });
    // v2 (SEC-09): local PIN lockouts live in erp-device so a logout does not reset them
    this.version(2).stores({ pin_lockouts: null });
  }
}

export interface DeviceSettingRow {
  key: string;
  value: unknown;
}

export class DeviceDb extends Dexie {
  device_settings!: Table<DeviceSettingRow, string>;
  /** SEC-09: per (user, device) local PIN lockout — survives logout, wiped with the device on revoke. */
  pin_lockouts!: Table<PinLockoutRow, string>;

  constructor(name: string) {
    super(name);
    this.version(1).stores({ device_settings: "key" });
    this.version(2).stores({ pin_lockouts: "user_id" });
  }
}
