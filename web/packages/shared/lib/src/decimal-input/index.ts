/**
 * Decimal-string form inputs — MoneyInput / PriceInput / QtyInput (08 §7.2, §8; qaror #26, #57).
 *
 * Everything here is STRING manipulation only: the value never becomes a JS number, so there is no
 * rounding and no float error. The pipeline of an input is
 *   keystrokes → `sanitizeDecimalInput` (canonical partial "1234.5", "-", "12.") →
 *   `groupDecimalInput` (display "1 234,5") and `toDecimalString` (API value "1234.50").
 * User input accepts both `,` and `.` as the decimal separator and ignores spaces / NBSP grouping.
 */

const NBSP = " ";

export interface DecimalInputOptions {
  /** Maximum fraction digits the user may type (money 0 or 2, price 4, weight qty 3). */
  scale: number;
  /** Allow a leading minus sign (default false). */
  allowNegative?: boolean;
  /** Maximum integer digits (default 16 — NUMERIC(18,2)). */
  maxIntegerDigits?: number;
}

function isDigit(ch: string): boolean {
  return ch >= "0" && ch <= "9";
}

/**
 * Keeps only what a decimal can contain and returns the canonical partial value:
 * `"1 234,5"` → `"1234.5"`, `"007"` → `"7"`, `"12,"` → `"12."` (still typing), `"-"` → `"-"`.
 * With `scale: 0` the separator ends the number (pasted "1240000,50" → "1240000"); typed separators
 * are simply ignored.
 * Extra fraction digits beyond `scale` and integer digits beyond `maxIntegerDigits` are dropped.
 */
export function sanitizeDecimalInput(raw: string, options: DecimalInputOptions): string {
  const { scale, allowNegative = false, maxIntegerDigits = 16 } = options;
  let negative = false;
  let intPart = "";
  let fracPart = "";
  let seenSeparator = false;

  for (const ch of raw.trim()) {
    if (ch === "-" || ch === "−") {
      if (allowNegative && intPart === "" && !seenSeparator) negative = true;
      continue;
    }
    if (ch === "," || ch === ".") {
      // scale 0 (whole so'm): the separator ends the number — "1240000,5" stays 1 240 000.
      seenSeparator = true;
      continue;
    }
    if (!isDigit(ch)) continue;
    if (seenSeparator) {
      if (fracPart.length < scale) fracPart += ch;
    } else if (intPart.length < maxIntegerDigits) {
      intPart += ch;
    }
  }

  // Strip leading zeros ("007" → "7"); ",5" becomes "0.5" below.
  let firstNonZero = 0;
  while (firstNonZero < intPart.length - 1 && intPart.charAt(firstNonZero) === "0") firstNonZero += 1;
  intPart = intPart.slice(firstNonZero);

  const sign = negative ? "-" : "";
  const withFraction = seenSeparator && scale > 0;
  if (intPart === "" && !withFraction) return sign;
  return `${sign}${intPart || "0"}${withFraction ? `.${fracPart}` : ""}`;
}

/** Display form of a canonical value: `"1234567.5"` → `"1 234 567,5"` (NBSP groups, comma). */
export function groupDecimalInput(canonical: string): string {
  if (canonical === "" || canonical === "-") return canonical === "-" ? "−" : "";
  const negative = canonical.startsWith("-");
  const body = negative ? canonical.slice(1) : canonical;
  const dot = body.indexOf(".");
  const intPart = dot === -1 ? body : body.slice(0, dot);
  const fracPart = dot === -1 ? null : body.slice(dot + 1);
  let grouped = "";
  for (let i = 0; i < intPart.length; i += 1) {
    const fromEnd = intPart.length - i;
    grouped += intPart.charAt(i);
    if (fromEnd > 1 && (fromEnd - 1) % 3 === 0) grouped += NBSP;
  }
  return `${negative ? "−" : ""}${grouped}${fracPart === null ? "" : `,${fracPart}`}`;
}

/**
 * API value: canonical partial → decimal string with exactly `outputScale` fraction digits
 * (`"12000"`, 2 → `"12000.00"`; `"8333.3"`, 4 → `"8333.3000"`). Empty / lone minus → `""`.
 * Never rounds: the input already limits fraction digits to `scale ≤ outputScale`.
 */
export function toDecimalString(canonical: string, outputScale: number): string {
  if (canonical === "" || canonical === "-") return "";
  const negative = canonical.startsWith("-");
  const body = negative ? canonical.slice(1) : canonical;
  const dot = body.indexOf(".");
  const intPart = (dot === -1 ? body : body.slice(0, dot)) || "0";
  let fracPart = dot === -1 ? "" : body.slice(dot + 1);
  if (fracPart.length > outputScale) fracPart = fracPart.slice(0, outputScale);
  while (fracPart.length < outputScale) fracPart += "0";
  const isZero = [...intPart, ...fracPart].every((ch) => ch === "0");
  const sign = negative && !isZero ? "-" : "";
  return outputScale > 0 ? `${sign}${intPart}.${fracPart}` : `${sign}${intPart}`;
}

/**
 * Canonical partial for an incoming API value. Trailing fraction zeros beyond the field's `scale`
 * are dropped (`"12000.00"`, scale 0 → `"12000"`), digits within the scale are kept
 * (`"1.250"`, scale 3 → `"1.250"`). Returns `""` for an empty/invalid value.
 */
export function fromDecimalString(value: string | null | undefined, scale: number): string {
  if (value === null || value === undefined || value === "") return "";
  const negative = value.startsWith("-");
  const body = negative ? value.slice(1) : value;
  const dot = body.indexOf(".");
  const intPart = dot === -1 ? body : body.slice(0, dot);
  let fracPart = dot === -1 ? "" : body.slice(dot + 1);
  if (![...intPart, ...fracPart].every(isDigit) || intPart === "") return "";
  // Drop zeros the field cannot show (scale), but never drop a significant digit.
  while (fracPart.length > scale && fracPart.endsWith("0")) fracPart = fracPart.slice(0, -1);
  if (scale === 0 && fracPart === "") return `${negative ? "-" : ""}${intPart}`;
  return `${negative ? "-" : ""}${intPart}${fracPart ? `.${fracPart}` : ""}`;
}

/** Number of "significant" characters (digits, separator, minus) before `caret` in a display string. */
export function significantCharsBefore(display: string, caret: number): number {
  let count = 0;
  for (let i = 0; i < Math.min(caret, display.length); i += 1) {
    const ch = display.charAt(i);
    if (isDigit(ch) || ch === "," || ch === "." || ch === "-" || ch === "−") count += 1;
  }
  return count;
}

/** Caret position in `display` after `count` significant characters (inverse of the above). */
export function caretAfterSignificantChars(display: string, count: number): number {
  if (count <= 0) return 0;
  let seen = 0;
  for (let i = 0; i < display.length; i += 1) {
    const ch = display.charAt(i);
    if (isDigit(ch) || ch === "," || ch === "." || ch === "-" || ch === "−") {
      seen += 1;
      if (seen === count) return i + 1;
    }
  }
  return display.length;
}
