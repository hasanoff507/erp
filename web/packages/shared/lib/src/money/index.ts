/**
 * Money — the only place where frontend money arithmetic is allowed.
 *
 * Rules: qaror #26, #57; 08-dizayn-tizimi.md §0 band 1; 32-kod-qoidalari.md §3.3.
 * - Money is ALWAYS a decimal string ("12000.00"), never a JS number.
 * - Arithmetic only in the two permitted cases (offline POS receipt totals, pre-submit form totals),
 *   string-in/string-out through decimal.js. Rounding identical to the backend (ROUND_HALF_UP):
 *     line_total = ROUND_HALF_UP(qty × unit_price − discount, 0)
 *     vat        = ROUND_HALF_UP(line_total × r / (100 + r), 2)
 * - `toTiyin` exists only for adapter boundaries (card terminal / fiscal, 24 §6.5).
 *
 * The `erp/no-money-arithmetic` lint rule rejects `+ - * /` on `Money` everywhere; this module does
 * not use those operators on Money either — it goes through Decimal.
 */
import Decimal from "decimal.js";

export type Money = string & { readonly __brand: "Money" };

/** Isolated Decimal constructor: 40 significant digits, ROUND_HALF_UP (= Python ROUND_HALF_UP). */
const D = Decimal.clone({ precision: 40, rounding: Decimal.ROUND_HALF_UP });

export class InvalidMoneyError extends Error {
  constructor(value: unknown) {
    super(`Invalid decimal string: ${String(value)}`);
    this.name = "InvalidMoneyError";
  }
}

/** Parses a decimal string strictly (no numbers, no exponent, no grouping). */
export function toDecimal(value: string): Decimal {
  if (typeof value !== "string" || value.trim() !== value || value === "") {
    throw new InvalidMoneyError(value);
  }
  let digits = 0;
  let dots = 0;
  for (let i = 0; i < value.length; i += 1) {
    const ch = value.charAt(i);
    if (ch === "-" && i === 0) continue;
    if (ch === ".") {
      dots += 1;
      continue;
    }
    if (ch < "0" || ch > "9") throw new InvalidMoneyError(value);
    digits += 1;
  }
  if (digits === 0 || dots > 1 || value.endsWith(".") || value.startsWith(".") || value.startsWith("-.")) {
    throw new InvalidMoneyError(value);
  }
  return new D(value);
}

/** Normalises a decimal string to a 2-place Money value (ROUND_HALF_UP to tiyin). */
export function money(value: string): Money {
  return toDecimal(value).toDecimalPlaces(2, D.ROUND_HALF_UP).toFixed(2) as Money;
}

export function isMoney(value: unknown): value is Money {
  if (typeof value !== "string") return false;
  try {
    toDecimal(value);
    return true;
  } catch {
    return false;
  }
}

export function addMoney(...values: Money[]): Money {
  return values.reduce((acc, v) => acc.plus(toDecimal(v)), new D(0)).toFixed(2) as Money;
}

export function subtractMoney(a: Money, b: Money): Money {
  return toDecimal(a).minus(toDecimal(b)).toFixed(2) as Money;
}

export function compareMoney(a: Money, b: Money): -1 | 0 | 1 {
  return toDecimal(a).comparedTo(toDecimal(b)) as -1 | 0 | 1;
}

/**
 * Receipt line total — whole so'm (qaror #26):
 * `ROUND_HALF_UP(qty × unit_price − discount, 0)`.
 * @param qty      quantity string, up to 3 decimals ("1.250")
 * @param unitPrice price string, up to 4 decimals ("8333.3333")
 * @param discount line discount (Money), default "0.00"
 */
export function lineTotal(qty: string, unitPrice: string, discount: Money = "0.00" as Money): Money {
  return toDecimal(qty)
    .times(toDecimal(unitPrice))
    .minus(toDecimal(discount))
    .toDecimalPlaces(0, D.ROUND_HALF_UP)
    .toFixed(2) as Money;
}

/**
 * VAT contained in a line total (tax-inclusive price), to the tiyin (qaror #26):
 * `ROUND_HALF_UP(line_total × r / (100 + r), 2)`.
 * @param ratePct VAT rate in percent as a decimal string ("12.00")
 */
export function vatIncluded(total: Money, ratePct: string): Money {
  const r = toDecimal(ratePct);
  return toDecimal(total).times(r).div(r.plus(100)).toDecimalPlaces(2, D.ROUND_HALF_UP).toFixed(2) as Money;
}

/**
 * Money → integer tiyin. ONLY at adapter boundaries (card terminal, fiscal partner — 24 §6.5).
 * Throws if the value has sub-tiyin precision or is outside the safe-integer range.
 */
export function toTiyin(value: string): number {
  const tiyin = toDecimal(value).times(100);
  if (!tiyin.isInteger()) throw new InvalidMoneyError(value);
  const n = tiyin.toNumber();
  if (!Number.isSafeInteger(n)) throw new InvalidMoneyError(value);
  return n;
}

/** Integer tiyin → Money string (adapter responses). */
export function fromTiyin(tiyin: number): Money {
  if (!Number.isSafeInteger(tiyin)) throw new InvalidMoneyError(tiyin);
  return new D(tiyin).div(100).toFixed(2) as Money;
}
