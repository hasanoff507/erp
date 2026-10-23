/**
 * Scan → product of the local catalog (24 §5.1, §6.3; offline-api.md §4, hw-api.md §5). Works offline:
 *  1. scale weight / amount label (`settings.weight_barcode_templates`) → PLU → product, qty from the label;
 *     a wrong check digit is rejected;
 *  2. ordinary barcode (pack barcodes add `units_per_barcode`);
 *  3. GS1 DataMatrix marking code → its GTIN barcode → product, one unit (the code itself is returned).
 * Anything else is `unknown` (07 POS-10 «Bu shtrix-kod tizimda yo'q»).
 */
import { parseWeightBarcode, weightLineQty, type WeightBarcodeTemplate } from "@shared/lib/scale";
import { catalog, settings, type BarcodeHit, type ProductView } from "@shared/offline";

import { gtinOfMarkingCode, isMarkingCode, normalizeScan } from "../lib/codes.ts";
import { qty3 } from "../lib/qty.ts";

export interface ScannedProduct {
  productId: string;
  name: string;
  nameRu: string | null;
  unitCode: string;
  isMarked: boolean;
  isWeighed: boolean;
  /** Quantity this scan stands for (1, pack size or label weight), 3 dp. */
  qty: string;
  /** Barcode as read (marking code: the DataMatrix string). */
  code: string;
  markingCode: string | null;
}

export type ScanResult =
  | { kind: "product"; item: ScannedProduct }
  | { kind: "unknown"; code: string }
  | { kind: "rejected"; code: string; reason: "check_digit" | "no_price" | "empty" };

export interface ScanDeps {
  templates(): Promise<readonly WeightBarcodeTemplate[] | null>;
  byBarcode(code: string): Promise<BarcodeHit | null>;
  byItemCode(code: string): Promise<ProductView | null>;
}

export const defaultScanDeps: ScanDeps = {
  templates: async () => (await settings.get()).weightBarcodeTemplates as WeightBarcodeTemplate[],
  byBarcode: (code) => catalog.byBarcode(code),
  byItemCode: (code) => catalog.byItemCode(code),
};

function toItem(view: ProductView, qty: string, code: string, markingCode: string | null): ScannedProduct {
  const p = view.product;
  return {
    productId: p.id,
    name: p.name,
    nameRu: p.name_ru ?? null,
    unitCode: p.unit_code,
    isMarked: p.is_marked === true,
    isWeighed: p.is_weighed === true,
    qty: qty3(qty) || "1.000",
    code,
    markingCode,
  };
}

export async function resolveScan(raw: string, deps: ScanDeps = defaultScanDeps): Promise<ScanResult> {
  const code = normalizeScan(raw);
  if (!code) return { kind: "rejected", code, reason: "empty" };

  if (isMarkingCode(code)) {
    const gtin = gtinOfMarkingCode(code);
    const hit = gtin ? await deps.byBarcode(gtin) : null;
    return hit ? { kind: "product", item: toItem(hit, "1", code, code) } : { kind: "unknown", code };
  }

  const weight = parseWeightBarcode(code, await deps.templates());
  if (weight.ok) {
    const view = await deps.byItemCode(weight.productCode);
    if (!view) return { kind: "unknown", code };
    if (weight.kind === "WEIGHT") return { kind: "product", item: toItem(view, weight.qty, code, null) };
    const qty = view.price ? weightLineQty(weight, view.price) : null;
    if (!qty) return { kind: "rejected", code, reason: "no_price" };
    return { kind: "product", item: toItem(view, qty, code, null) };
  }
  if (weight.reason === "check_digit") return { kind: "rejected", code, reason: "check_digit" };

  const hit = await deps.byBarcode(code);
  if (!hit) return { kind: "unknown", code };
  return { kind: "product", item: toItem(hit, hit.unitsPerBarcode || "1", code, null) };
}
