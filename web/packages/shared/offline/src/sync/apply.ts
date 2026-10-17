/**
 * Applies one `/sync/pull` page to `erp-pos` in ONE Dexie transaction (contracts/sync-pull.md):
 * delta arrays are upserted by id (`deleted: true` removes); barcodes/prices rows carry the product's
 * full set (replace); snapshot objects (permissions, limits, shift, settings) replace the whole table,
 * `null` = unchanged. Fiscal receipt rows map OFD acks back onto local outbox events (16 §6 timer).
 */
import { META } from "../db/meta.ts";
import type { PosDb } from "../db/schema.ts";
import { searchTokens } from "../lib/search.ts";
import type {
  CustomerRow,
  FiscalReceiptRow,
  LimitRow,
  PriceRow,
  ProductRow,
  PullScope,
  StaffRow,
  SyncPullResponse,
} from "../types.ts";

type Row = Record<string, unknown>;

function rows(value: unknown): Row[] {
  return Array.isArray(value) ? value.filter((r): r is Row => typeof r === "object" && r !== null) : [];
}

function str(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function isDeleted(row: Row): boolean {
  return row.deleted === true;
}

export function toProductRow(row: Row): ProductRow {
  const name = str(row.name) ?? "";
  const nameRu = str(row.name_ru);
  const code = str(row.code);
  return {
    ...row,
    id: String(row.id),
    name,
    name_ru: nameRu,
    category_id: str(row.category_id),
    unit_code: str(row.unit_code) ?? "",
    tokens: searchTokens(name, nameRu, code, str(row.mxik_code)),
  };
}

export function toCustomerRow(row: Row): CustomerRow {
  const name = str(row.name) ?? "";
  const phone = str(row.phone);
  const digits = phone ? phone.replace(/\D+/g, "") : null;
  return {
    ...row,
    id: String(row.id),
    name,
    phone,
    tokens: searchTokens(name, digits, digits && digits.length > 9 ? digits.slice(-9) : null, str(row.stir)),
  };
}

function toStaffRow(row: Row): StaffRow {
  const permissions = rows(row.permissions).map((p) => ({
    code: String(p.code),
    limit_value: str(p.limit_value),
  }));
  return {
    ...row,
    user_id: String(row.user_id),
    full_name: str(row.full_name) ?? "",
    role_codes: Array.isArray(row.role_codes) ? row.role_codes.map(String) : [],
    branch_ids: Array.isArray(row.branch_ids) ? row.branch_ids.map(String) : [],
    active: row.active === true,
    must_change_pin: row.must_change_pin === true,
    // device-auth.md: inactive or no verifier → the device forgets that user's local verifier
    pin_local_hash: row.active === true ? str(row.pin_local_hash) : null,
    permissions,
  };
}

export const POS_TABLES_FOR_PULL = [
  "meta",
  "catalog",
  "categories",
  "units",
  "barcodes",
  "prices",
  "customers",
  "stock",
  "limits",
  "permissions",
  "marking_codes",
  "fiscal",
  "fiscal_receipts",
  "settings",
  "card_terminals",
  "outbox",
] as const;

/** Tables that receive delta rows (cleared before a from-scratch snapshot). */
export const DELTA_TABLES = [
  "catalog",
  "categories",
  "units",
  "barcodes",
  "prices",
  "customers",
  "stock",
  "marking_codes",
  "fiscal",
  "fiscal_receipts",
] as const;

/**
 * Applies `page` and stores `page.cursor`. Must run inside `db.transaction("rw", POS_TABLES_FOR_PULL)`.
 * Returns the scopes that carried data.
 */
export async function applyPullPage(db: PosDb, page: SyncPullResponse): Promise<PullScope[]> {
  const touched: PullScope[] = [];

  // catalog — product | category | unit
  const catalog = rows(page.catalog);
  if (catalog.length) touched.push("catalog");
  for (const row of catalog) {
    const entity = str(row.entity) ?? "product";
    const id = String(row.id);
    if (entity === "category") {
      if (isDeleted(row)) await db.categories.delete(id);
      else await db.categories.put({ ...row, id, name: str(row.name) ?? "" });
    } else if (entity === "unit") {
      const code = str(row.code) ?? id;
      if (isDeleted(row)) await db.units.delete(code);
      else await db.units.put({ ...row, code });
    } else if (isDeleted(row) || str(row.archived_at) !== null) {
      await db.catalog.delete(id);
    } else {
      await db.catalog.put(toProductRow(row));
    }
  }

  // barcodes — full set per product
  const barcodes = rows(page.barcodes);
  if (barcodes.length) touched.push("barcodes");
  for (const row of barcodes) {
    const productId = str(row.product_id) ?? String(row.id);
    await db.barcodes.where("product_id").equals(productId).delete();
    if (isDeleted(row)) continue;
    await db.barcodes.bulkPut(
      rows(row.barcodes).map((b) => ({
        ...b,
        id: `${productId}:${String(b.barcode)}`,
        product_id: productId,
        barcode: String(b.barcode),
        units_per_barcode: str(b.units_per_barcode) ?? "1.000",
      })),
    );
  }

  // prices — full relevant set per product
  const prices = rows(page.prices);
  if (prices.length) touched.push("prices");
  for (const row of prices) {
    const productId = str(row.product_id) ?? String(row.id);
    await db.prices.where("product_id").equals(productId).delete();
    if (isDeleted(row)) continue;
    await db.prices.bulkPut(
      rows(row.prices).map((p): PriceRow => ({
        ...p,
        id: str(p.price_id) ?? `${productId}:${str(p.branch_id) ?? "*"}:${str(p.valid_from) ?? ""}`,
        product_id: productId,
        branch_id: str(p.branch_id),
        branch_key: str(p.branch_id) ?? "*",
        price: str(p.price) ?? "0",
        valid_from: str(p.valid_from) ?? "1970-01-01T00:00:00Z",
      })),
    );
  }

  const customers = rows(page.customers);
  if (customers.length) touched.push("customers");
  for (const row of customers) {
    if (isDeleted(row)) await db.customers.delete(String(row.id));
    else await db.customers.put(toCustomerRow(row));
  }

  const stock = rows(page.stock);
  if (stock.length) touched.push("stock");
  for (const row of stock) {
    if (isDeleted(row)) await db.stock.delete(String(row.id));
    else await db.stock.put({ ...row, id: String(row.id), product_id: String(row.product_id) });
  }

  const marking = rows(page.marking_codes);
  if (marking.length) touched.push("marking_codes");
  for (const row of marking) {
    const code = String(row.code);
    // the server row supersedes the local "sold offline" marker of the same code
    await db.marking_codes.delete(`local:${code}`);
    if (isDeleted(row)) await db.marking_codes.delete(String(row.id));
    else
      await db.marking_codes.put({
        ...row,
        id: String(row.id),
        code,
        status: String(row.status),
      });
  }

  const fiscal = rows(page.fiscal);
  if (fiscal.length) touched.push("fiscal");
  for (const row of fiscal) {
    const id = String(row.id);
    if (str(row.entity) === "cash_register") {
      if (isDeleted(row)) await db.fiscal.delete(id);
      else await db.fiscal.put({ ...row, id });
      continue;
    }
    if (isDeleted(row)) {
      await db.fiscal_receipts.delete(id);
      continue;
    }
    const receipt = { ...row, id } as FiscalReceiptRow;
    await db.fiscal_receipts.put(receipt);
    const clientEventId = str(row.client_event_id);
    const acked = str(row.ofd_acked_at);
    if (clientEventId && acked) {
      await db.outbox
        .where("client_event_id")
        .equals(clientEventId)
        .modify((event) => {
          event.ofd_acked_at = acked;
          event.fiscal_unacked = 0;
        });
    }
  }

  // snapshot objects — replace the table; null/absent = unchanged
  const permissions = page.permissions as Row | null | undefined;
  if (permissions && typeof permissions === "object") {
    touched.push("permissions");
    await db.permissions.clear();
    await db.permissions.bulkPut(rows(permissions.staff).map(toStaffRow));
  }

  const limits = page.limits as Row | null | undefined;
  if (limits && typeof limits === "object") {
    touched.push("limits");
    await db.limits.clear();
    await db.limits.bulkPut(
      rows(limits.users).map((u): LimitRow => ({
        user_id: String(u.user_id),
        limits: (typeof u.limits === "object" && u.limits !== null ? u.limits : {}) as Record<
          string,
          string | null
        >,
      })),
    );
  }

  const shift = page.shift as Row | null | undefined;
  if (shift && typeof shift === "object") {
    touched.push("shift");
    await db.meta.put({ key: META.serverShift, value: shift });
  }

  const settings = page.settings as Row | null | undefined;
  if (settings && typeof settings === "object") {
    touched.push("settings");
    await db.settings.clear();
    await db.settings.bulkPut(
      Object.entries(settings)
        .filter(([key]) => key !== "card_terminals")
        .map(([key, value]) => ({ key, value })),
    );
    await db.card_terminals.clear();
    await db.card_terminals.bulkPut(rows(settings.card_terminals).map((t) => ({ ...t, id: String(t.id) })));
  }

  await db.meta.put({ key: META.pullCursor, value: page.cursor });
  return touched;
}
