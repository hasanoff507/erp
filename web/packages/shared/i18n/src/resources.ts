import ruAuth from "./locales/ru/auth.json";
import ruCatalog from "./locales/ru/catalog.json";
import ruCommon from "./locales/ru/common.json";
import ruOnboarding from "./locales/ru/onboarding.json";
import ruPos from "./locales/ru/pos.json";
import ruReports from "./locales/ru/reports.json";
import ruSettings from "./locales/ru/settings.json";
import uzAuth from "./locales/uz/auth.json";
import uzCatalog from "./locales/uz/catalog.json";
import uzCommon from "./locales/uz/common.json";
import uzOnboarding from "./locales/uz/onboarding.json";
import uzPos from "./locales/uz/pos.json";
import uzReports from "./locales/uz/reports.json";
import uzSettings from "./locales/uz/settings.json";

/**
 * 08-dizayn-tizimi.md §11: one namespace per @pages/* package plus `common`; `uz.json`/`ru.json`
 * share the exact key structure (checked by resources.test.ts). `auth` = login (BO-01, shell);
 * `onboarding` = signup wizard BO-21 and /install (UX-INSTALL).
 */
export const resources = {
  uz: {
    common: uzCommon,
    auth: uzAuth,
    reports: uzReports,
    pos: uzPos,
    settings: uzSettings,
    catalog: uzCatalog,
    onboarding: uzOnboarding,
  },
  ru: {
    common: ruCommon,
    auth: ruAuth,
    reports: ruReports,
    pos: ruPos,
    settings: ruSettings,
    catalog: ruCatalog,
    onboarding: ruOnboarding,
  },
} as const;

export const NAMESPACES = ["common", "auth", "reports", "pos", "settings", "catalog", "onboarding"] as const;
export type Namespace = (typeof NAMESPACES)[number];
