/**
 * What a scanned string is (24 §5.1, 06 §1.6): a GS1 DataMatrix marking code (Asl belgisi, 21 §5), an
 * EAN-13 / EAN-8 / other GTIN barcode, or something else. Pure — used by POS-08 (marking codes), POS-16
 * (scanner test) and the product resolver.
 */
import { isValidEan13, isValidGtin } from "@shared/lib/barcode";

export type CodeKind = "datamatrix" | "ean13" | "ean8" | "gtin" | "other";

const GS = "\u001d";

/** GS1 DataMatrix marking code: `01` + GTIN-14 + `21` serial (+ GS-separated crypto tail). */
export function isMarkingCode(code: string): boolean {
  return /^01[0-9]{14}21/.test(code) && (code.includes(GS) || code.length >= 25);
}

/** The product barcode (EAN-13 when the GTIN-14 starts with 0) of a marking code, else null. */
export function gtinOfMarkingCode(code: string): string | null {
  if (!isMarkingCode(code)) return null;
  const gtin14 = code.slice(2, 16);
  return gtin14.startsWith("0") ? gtin14.slice(1) : gtin14;
}

export function classifyCode(raw: string): CodeKind {
  const code = raw.trim();
  if (isMarkingCode(code)) return "datamatrix";
  if (!/^[0-9]+$/.test(code)) return "other";
  if (code.length === 13 && isValidEan13(code)) return "ean13";
  if (code.length === 8 && isValidGtin(code)) return "ean8";
  if ((code.length === 12 || code.length === 14) && isValidGtin(code)) return "gtin";
  return "other";
}

/** Marking codes are stored exactly as read (GS separators kept, 19 §8); whitespace around is dropped. */
export function normalizeScan(raw: string): string {
  return raw.replace(/^[\s]+|[\r\n]+$/g, "").trim();
}
