/** Barcode / MXIK client-side checks (19 §1). The server re-validates (BARCODE_DUPLICATE, MXIK_CODE_INVALID). */
import { isValidGtin } from "@shared/lib/barcode";

const DIGITS = /^[0-9]+$/;
/** Same character set as the backend (`product_barcodes.barcode`, import parser). */
const BARCODE_CHARS = /^[0-9A-Za-z\-.$/+%]{1,64}$/;
const GTIN_LENGTHS = new Set([8, 12, 13, 14]);

/** null when OK, otherwise a message key (`common` or `catalog:server`). */
export function barcodeIssue(code: string): string | null {
  const value = code.trim();
  if (value === "") return "validation.required";
  if (!BARCODE_CHARS.test(value)) return "validation.barcode_format";
  if (DIGITS.test(value) && GTIN_LENGTHS.has(value.length) && !isValidGtin(value)) {
    return "validation.barcode_check_digit";
  }
  return null;
}

/** MXIK (IKPU) — exactly 17 digits (19 §1, 21 §7). */
export function isMxikFormat(code: string): boolean {
  return code.length === 17 && DIGITS.test(code);
}
