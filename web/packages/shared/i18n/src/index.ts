/**
 * @shared/i18n — i18next: Uzbek (Latin) is the default and fallback, Russian is second
 * (06 §1.4, 08 §0 band 3, §11). A missing Russian string falls back to Uzbek — a key name is never shown.
 */
import i18next, { type i18n as I18n } from "i18next";
import { initReactI18next } from "react-i18next";

import { setDateLocale } from "@shared/lib/date";

import { NAMESPACES, resources } from "./resources.ts";

export { NAMESPACES, resources, type Namespace } from "./resources.ts";
export { Trans, useTranslation } from "react-i18next";
export {
  hasServerMessage,
  serverErrorText,
  translateServerMessage,
  type ServerErrorLike,
  type ServerMessageOptions,
} from "./server-messages.ts";

export const SUPPORTED_LANGUAGES = ["uz", "ru"] as const;
export type UiLanguage = (typeof SUPPORTED_LANGUAGES)[number];
export const DEFAULT_LANGUAGE: UiLanguage = "uz";

const STORAGE_KEY = "erp.lang";

declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: "common";
    resources: (typeof resources)["uz"];
    returnNull: false;
  }
}

export function isUiLanguage(value: unknown): value is UiLanguage {
  return value === "uz" || value === "ru";
}

/** The user's last explicit choice (per device); otherwise Uzbek — never the browser locale. */
export function readStoredLanguage(): UiLanguage {
  try {
    const stored = globalThis.localStorage?.getItem(STORAGE_KEY);
    return isUiLanguage(stored) ? stored : DEFAULT_LANGUAGE;
  } catch {
    return DEFAULT_LANGUAGE;
  }
}

function applyLanguageSideEffects(lang: UiLanguage): void {
  setDateLocale(lang);
  if (typeof document !== "undefined") document.documentElement.lang = lang;
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, lang);
  } catch {
    // storage unavailable (private mode) — language still switches for this session
  }
}

export function initI18n(lang: UiLanguage = readStoredLanguage()): I18n {
  if (!i18next.isInitialized) {
    void i18next.use(initReactI18next).init({
      resources,
      lng: lang,
      fallbackLng: DEFAULT_LANGUAGE,
      supportedLngs: [...SUPPORTED_LANGUAGES],
      ns: [...NAMESPACES],
      defaultNS: "common",
      interpolation: { escapeValue: false },
      returnNull: false,
      initAsync: false,
    });
    i18next.on("languageChanged", (lng) => {
      if (isUiLanguage(lng)) applyLanguageSideEffects(lng);
    });
  }
  applyLanguageSideEffects(lang);
  return i18next;
}

export function changeLanguage(lang: UiLanguage): Promise<unknown> {
  return i18next.changeLanguage(lang);
}

export function currentLanguage(): UiLanguage {
  return isUiLanguage(i18next.resolvedLanguage) ? i18next.resolvedLanguage : DEFAULT_LANGUAGE;
}

/**
 * Server `message_key` → text (08 §11): `t("common:" + message_key)`, falling back to
 * `common:errors.internal_error` when the key is unknown. Raw codes/JSON are never displayed.
 */
export function translateMessageKey(messageKey: string, params?: Record<string, unknown>): string {
  const key = `common:${messageKey}`;
  const t = i18next.t.bind(i18next) as (k: string, o?: Record<string, unknown>) => string;
  return i18next.exists(key) ? t(key, params) : t("common:errors.internal_error");
}

export { i18next };
