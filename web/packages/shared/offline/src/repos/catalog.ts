/**
 * Catalog queries for POS-02/POS-11 (24 §5, §5.1; QT-NFR-01: barcode → line < 100 ms, all local).
 * Price rule (contracts/sync-pull.md, 16 §5): among entries with `valid_from <= now` prefer the device
 * branch, then the latest `valid_from`; the tenant-wide (null branch) price only when no branch price
 * exists. The caller copies the price into the receipt line ("frozen" — never re-priced later).
 * Prices are NUMERIC(18,4) decimal strings as delivered.
 */
import { deviceIdentity } from "../device-settings.ts";
import { memoryRows } from "../lib/memory-index.ts";
import { queryWords } from "../lib/search.ts";
import { now, posDb } from "../runtime.ts";
import type { BarcodeRow, CategoryRow, PriceRow, ProductRow, UnitRow } from "../types.ts";

export interface ProductView {
  product: ProductRow;
  /** Effective price for the branch, or null = unknown (marked goods cannot be sold offline, 16 §7). */
  price: string | null;
}

export interface BarcodeHit extends ProductView {
  barcode: BarcodeRow;
  /** Qty one scan adds (pack barcodes), decimal string "1.000". */
  unitsPerBarcode: string;
}

export function effectivePrice(
  entries: readonly PriceRow[],
  branchId: string | null,
  nowMs: number,
): string | null {
  let best: PriceRow | null = null;
  let bestRank = -1;
  for (const entry of entries) {
    const from = Date.parse(entry.valid_from);
    if (Number.isNaN(from) || from > nowMs) continue;
    const rank =
      entry.branch_id !== null && entry.branch_id === branchId ? 1 : entry.branch_id === null ? 0 : -1;
    if (rank < 0) continue;
    if (rank > bestRank || (rank === bestRank && best !== null && entry.valid_from > best.valid_from)) {
      best = entry;
      bestRank = rank;
    }
  }
  return best?.price ?? null;
}

async function branchOf(branchId?: string | null): Promise<string | null> {
  if (branchId !== undefined) return branchId;
  return (await deviceIdentity.get())?.branchId ?? null;
}

async function withPrices(products: ProductRow[], branchId: string | null): Promise<ProductView[]> {
  if (products.length === 0) return [];
  const prices = await posDb()
    .prices.where("product_id")
    .anyOf(products.map((p) => p.id))
    .toArray();
  const byProduct = new Map<string, PriceRow[]>();
  for (const price of prices) {
    const list = byProduct.get(price.product_id) ?? [];
    list.push(price);
    byProduct.set(price.product_id, list);
  }
  const nowMs = now();
  return products.map((product) => ({
    product,
    price: effectivePrice(byProduct.get(product.id) ?? [], branchId, nowMs),
  }));
}

const isActive = (p: ProductRow | undefined): p is ProductRow =>
  p !== undefined && (p.archived_at === null || p.archived_at === undefined);

const byName = (a: ProductRow, b: ProductRow) => a.name.localeCompare(b.name);

/** Active products sorted by name, from the in-tab memory copy (lib/memory-index.ts). */
function activeProducts(): Promise<ProductRow[]> {
  return memoryRows<ProductRow>("catalog", async (table) =>
    (await table.toArray()).filter(isActive).sort(byName),
  );
}

export const catalog = {
  /** Builds the in-tab search copy ahead of the first keystroke (POS page mount, after a pull). */
  async warmUp(): Promise<void> {
    await activeProducts();
  },

  /**
   * Word-prefix search over name / name_ru / code / MXIK (every query word must prefix-match a token),
   * plus exact barcode and code hits first. Empty query → the category (or everything) by name.
   * A non-empty query ignores `categoryId` (24 §5.1).
   */
  async search(
    query: string,
    opts: { categoryId?: string | null; branchId?: string | null; limit?: number } = {},
  ): Promise<ProductView[]> {
    const db = posDb();
    const limit = opts.limit ?? 50;
    const branchId = await branchOf(opts.branchId);
    const words = queryWords(query);

    if (words.length === 0) {
      const all = await activeProducts();
      const products = (opts.categoryId ? all.filter((p) => p.category_id === opts.categoryId) : all).slice(
        0,
        limit,
      );
      return withPrices(products, branchId);
    }

    const exact = new Map<string, ProductRow>();
    const raw = query.trim();
    const barcodeHits = await db.barcodes.where("barcode").equals(raw).toArray();
    for (const p of await db.catalog.bulkGet(barcodeHits.map((b) => b.product_id)))
      if (isActive(p)) exact.set(p.id, p);
    for (const p of await db.catalog.where("code").equals(raw).toArray()) if (isActive(p)) exact.set(p.id, p);

    const matches: ProductRow[] = [];
    for (const p of await activeProducts()) {
      if (exact.has(p.id)) continue;
      if (words.every((w) => p.tokens.some((t) => t.startsWith(w)))) matches.push(p);
      if (matches.length >= limit) break;
    }
    const products = [...exact.values(), ...matches].slice(0, limit);
    return withPrices(products, branchId);
  },

  /** Scanner path: exact barcode → product + price + pack size. */
  async byBarcode(code: string, branchId?: string | null): Promise<BarcodeHit | null> {
    const db = posDb();
    const barcode = await db.barcodes.where("barcode").equals(code).first();
    if (!barcode) return null;
    const product = await db.catalog.get(barcode.product_id);
    if (!isActive(product)) return null;
    const [view] = await withPrices([product], await branchOf(branchId));
    if (!view) return null;
    return { ...view, barcode, unitsPerBarcode: barcode.units_per_barcode };
  },

  /** Weight/price barcode item code (template `item_code_len`): weighed-prefix barcode or product code. */
  async byItemCode(itemCode: string, branchId?: string | null): Promise<ProductView | null> {
    const db = posDb();
    const barcode = await db.barcodes.where("barcode").equals(itemCode).first();
    const product = barcode
      ? await db.catalog.get(barcode.product_id)
      : await db.catalog.where("code").equals(itemCode).first();
    if (!isActive(product)) return null;
    const [view] = await withPrices([product], await branchOf(branchId));
    return view ?? null;
  },

  async get(productId: string, branchId?: string | null): Promise<ProductView | undefined> {
    const product = await posDb().catalog.get(productId);
    if (!isActive(product)) return undefined;
    const [view] = await withPrices([product], await branchOf(branchId));
    return view;
  },

  async barcodesOf(productId: string): Promise<BarcodeRow[]> {
    return posDb().barcodes.where("product_id").equals(productId).toArray();
  },

  /** Units (pull `catalog` entity unit) — `is_fractional` drives qty validation (18 §2.3). */
  units(): Promise<UnitRow[]> {
    return posDb().units.toArray();
  },

  unit(code: string): Promise<UnitRow | undefined> {
    return posDb().units.get(code);
  },

  /** Category tabs (24 §5.1): categories that have at least one sellable product, by sort_order/name. */
  async categories(): Promise<CategoryRow[]> {
    const db = posDb();
    const used = (await db.catalog.orderBy("category_id").uniqueKeys()).map(String);
    const rows = (await db.categories.bulkGet(used)).filter((c): c is CategoryRow => c !== undefined);
    return rows.sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.name.localeCompare(b.name));
  },
};

export const prices = {
  async current(productId: string, branchId?: string | null): Promise<string | null> {
    const entries = await posDb().prices.where("product_id").equals(productId).toArray();
    return effectivePrice(entries, await branchOf(branchId), now());
  },
};
