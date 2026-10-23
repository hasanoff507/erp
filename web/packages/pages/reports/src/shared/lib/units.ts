import { i18next } from "@shared/i18n";
import { formatQty, type QtyUnitKind } from "@shared/lib/format";

/** Weight / volume / length units are shown with 3 decimals (08 §8); the rest as whole numbers. */
const FRACTIONAL_UNITS = new Set(["kg", "g", "l", "ml", "m"]);

export function qtyKind(unitCode: string | null | undefined, value: string): QtyUnitKind {
  if (unitCode && FRACTIONAL_UNITS.has(unitCode)) return "fractional";
  const dot = value.indexOf(".");
  const fraction = dot === -1 ? "" : value.slice(dot + 1);
  return [...fraction].every((ch) => ch === "0") ? "integer" : "fractional";
}

/** Translated unit label (`catalog:units.<code>`), the code itself when unknown. */
export function unitLabel(code: string | null | undefined): string {
  if (!code) return "";
  const key = `catalog:units.${code}`;
  return i18next.exists(key) ? (i18next.t.bind(i18next) as (k: string) => string)(key) : code;
}

/** `"12 dona"`, `"1,250 kg"`. */
export function formatUnitQty(value: string, unitCode: string | null | undefined): string {
  const label = unitLabel(unitCode);
  const qty = formatQty(value, qtyKind(unitCode, value));
  return label ? `${qty} ${label}` : qty;
}
