/**
 * BO-11 permission catalog labels in the UI language (WEB-06): `settings:permissions.<code>` and
 * `settings:modules.<Mxx>`. A code this bundle does not know yet falls back to the server's (Uzbek)
 * description / the raw module code — never an i18n key.
 */
import { i18next } from "@shared/i18n";

type Translate = (key: string) => string;

function label(key: string, fallback: string): string {
  const full = `settings:${key}`;
  return i18next.exists(full) ? (i18next.t.bind(i18next) as unknown as Translate)(full) : fallback;
}

export function permissionLabel(item: { code: string; description: string }): string {
  return label(`permissions.${item.code}`, item.description);
}

/** `"M01"` → "Kassa (POS)"; several modules (`"M07, M10"`) are joined with " · ". */
export function moduleLabel(module: string): string {
  return module
    .split(/[,/]/)
    .map((code) => code.trim())
    .filter(Boolean)
    .map((code) => label(`modules.${code}`, code))
    .join(" · ");
}

/** `"M07, M10"` → `"M07"`: a permission is listed once, under its primary module (15 §2.1). */
export function primaryModule(module: string): string {
  return module.split(/[,/]/)[0]?.trim() || module;
}
