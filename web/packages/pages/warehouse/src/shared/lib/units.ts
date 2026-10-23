import { i18next } from "@shared/i18n";

/** `platform.units.code` → label (`catalog:units.*`, shared with the product card); unknown → the code. */
export function unitLabel(code: string | null | undefined): string {
  if (!code) return "";
  const key = `catalog:units.${code}`;
  return i18next.exists(key) ? (i18next.t.bind(i18next) as (k: string) => string)(key) : code;
}
