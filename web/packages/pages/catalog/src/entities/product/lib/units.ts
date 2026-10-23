/** `platform.units.code` → translated label (catalog:units.*); unknown codes show the code itself. */
import { i18next } from "@shared/i18n";

export function unitLabel(code: string): string {
  const key = `catalog:units.${code}`;
  return i18next.exists(key) ? (i18next.t.bind(i18next) as (k: string) => string)(key) : code;
}
