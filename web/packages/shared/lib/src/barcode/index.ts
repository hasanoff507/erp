/**
 * GTIN / EAN check digits (EAN-8, UPC-A, EAN-13, GTIN-14) — catalog barcodes (US-M09, 19 barcodes).
 * Character-based digit handling; no Number()/parseInt (qaror #57).
 */

function digitsOnly(code: string): number[] | null {
  const out: number[] = [];
  for (const ch of code) {
    const d = "0123456789".indexOf(ch);
    if (d === -1) return null;
    out.push(d);
  }
  return out;
}

/** GS1 mod-10 check digit for the payload (all digits except the check digit). */
export function gtinCheckDigit(payload: string): string {
  const digits = digitsOnly(payload);
  if (!digits || digits.length === 0) throw new Error(`Invalid GTIN payload: ${payload}`);
  let sum = 0;
  // Weights 3,1,3,1… from the rightmost payload digit.
  for (let i = 0; i < digits.length; i += 1) {
    const d = digits[digits.length - 1 - i] ?? 0;
    sum += i % 2 === 0 ? d * 3 : d;
  }
  return String((10 - (sum % 10)) % 10);
}

/** EAN-13 check digit for the first 12 digits: `"478000012345"` → `"6"`. */
export function ean13CheckDigit(first12: string): string {
  if (first12.length !== 12) throw new Error("EAN-13 payload must have 12 digits");
  return gtinCheckDigit(first12);
}

/** True for a well-formed GTIN-8/12/13/14 with a correct check digit. */
export function isValidGtin(code: string): boolean {
  if (![8, 12, 13, 14].includes(code.length) || !digitsOnly(code)) return false;
  return gtinCheckDigit(code.slice(0, -1)) === code.slice(-1);
}

export function isValidEan13(code: string): boolean {
  return code.length === 13 && isValidGtin(code);
}
