/**
 * Scale weight barcodes — 24 §6.3, 19 `/stock-settings` (`weight_barcode_templates[]`), US-M09-06,
 * QT-M01-22 / QT-M09-06. EAN-13 `PP CCCCC VVVVV K`: PP prefix (20–29), item (PLU) code, value
 * (grams or so'm), check digit. A wrong check digit rejects the code.
 * No Number()/parseInt (qaror #57): values stay decimal strings.
 */
import Decimal from "decimal.js";

import { isValidEan13 } from "#/barcode/index.ts";
import { toDecimal } from "#/money/index.ts";

export type WeightValueKind = "WEIGHT" | "AMOUNT";

/** One element of `settings.weight_barcode_templates` (19 /stock-settings). */
export interface WeightBarcodeTemplate {
  prefixes: readonly string[];
  item_code_len: number;
  value_len: number;
  value_kind: WeightValueKind;
  decimals: number;
  enabled?: boolean;
}

/** Standard templates: 22 — weight in grams, 21 — amount in so'm (19, 26 #31). */
export const DEFAULT_WEIGHT_BARCODE_TEMPLATES: readonly WeightBarcodeTemplate[] = Object.freeze([
  { prefixes: ["22"], item_code_len: 5, value_len: 5, value_kind: "WEIGHT", decimals: 3, enabled: true },
  { prefixes: ["21"], item_code_len: 5, value_len: 5, value_kind: "AMOUNT", decimals: 0, enabled: true },
]);

export type WeightBarcodeResult =
  | { ok: true; kind: "WEIGHT"; prefix: string; productCode: string; qty: string }
  | { ok: true; kind: "AMOUNT"; prefix: string; productCode: string; amount: string }
  | { ok: false; reason: "not_ean13" | "check_digit" | "no_template" };

const DIGITS = /^[0-9]{13}$/;

function validTemplate(t: WeightBarcodeTemplate): boolean {
  return (
    t.enabled !== false &&
    t.item_code_len >= 4 &&
    t.item_code_len <= 6 &&
    t.value_len >= 1 &&
    2 + t.item_code_len + t.value_len === 12 &&
    t.decimals >= 0 &&
    t.decimals <= 3 &&
    (t.value_kind === "WEIGHT" || t.value_kind === "AMOUNT")
  );
}

/**
 * Parses a scanned code against the tenant templates (`null`/empty → defaults).
 * `no_template` means "not a weight barcode" — the caller looks the code up as an ordinary barcode.
 */
export function parseWeightBarcode(
  code: string,
  templates: readonly WeightBarcodeTemplate[] | null | undefined,
): WeightBarcodeResult {
  const list = templates && templates.length ? templates : DEFAULT_WEIGHT_BARCODE_TEMPLATES;
  const trimmed = code.trim();
  if (!DIGITS.test(trimmed)) return { ok: false, reason: "not_ean13" };
  const prefix = trimmed.slice(0, 2);
  const template = list.find((t) => validTemplate(t) && t.prefixes.includes(prefix));
  if (!template) return { ok: false, reason: "no_template" };
  if (!isValidEan13(trimmed)) return { ok: false, reason: "check_digit" };
  const productCode = trimmed.slice(2, 2 + template.item_code_len);
  const raw = trimmed.slice(2 + template.item_code_len, 12);
  const value = toDecimal(raw).div(new Decimal(10).pow(template.decimals));
  if (template.value_kind === "WEIGHT") {
    return { ok: true, kind: "WEIGHT", prefix, productCode, qty: value.toFixed(3) };
  }
  return { ok: true, kind: "AMOUNT", prefix, productCode, amount: value.toFixed(2) };
}

/**
 * Line quantity for a parsed code: WEIGHT → qty as is; AMOUNT → amount ÷ current price, 3 places
 * ROUND_HALF_UP (US-M09-06 "miqdor = summa ÷ joriy narx"). Returns null for a zero/negative price.
 */
export function weightLineQty(
  parsed: { kind: "WEIGHT"; qty: string } | { kind: "AMOUNT"; amount: string },
  unitPrice: string,
): string | null {
  if (parsed.kind === "WEIGHT") return parsed.qty;
  const price = toDecimal(unitPrice);
  if (price.lte(0)) return null;
  return toDecimal(parsed.amount).div(price).toDecimalPlaces(3, Decimal.ROUND_HALF_UP).toFixed(3);
}

/**
 * Sum of two weight quantities of the same product (two labels → one receipt line, US-M09-06).
 */
export function addWeightQty(a: string, b: string): string {
  return toDecimal(a).plus(toDecimal(b)).toFixed(3);
}

/**
 * AMOUNT label vs current price: true when the label amount differs from `qty × price` rounded to
 * whole so'm — US-M09-06 warning "yorliqdagi summa joriy narxdan farqli".
 */
export function amountLabelMismatch(amount: string, qty: string, unitPrice: string): boolean {
  const expected = toDecimal(qty).times(toDecimal(unitPrice)).toDecimalPlaces(0, Decimal.ROUND_HALF_UP);
  return !expected.eq(toDecimal(amount).toDecimalPlaces(0, Decimal.ROUND_HALF_UP));
}
