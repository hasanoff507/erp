import ruAuth from "./locales/ru/auth.json";
import ruCatalog from "./locales/ru/catalog.json";
import ruCommon from "./locales/ru/common.json";
import ruFinance from "./locales/ru/finance.json";
import ruOnboarding from "./locales/ru/onboarding.json";
import ruPos from "./locales/ru/pos.json";
import ruReports from "./locales/ru/reports.json";
import ruSettings from "./locales/ru/settings.json";
import ruWarehouse from "./locales/ru/warehouse.json";
import uzAuth from "./locales/uz/auth.json";
import uzCatalog from "./locales/uz/catalog.json";
import uzCommon from "./locales/uz/common.json";
import uzFinance from "./locales/uz/finance.json";
import uzOnboarding from "./locales/uz/onboarding.json";
import uzPos from "./locales/uz/pos.json";
import uzReports from "./locales/uz/reports.json";
import uzSettings from "./locales/uz/settings.json";
import uzWarehouse from "./locales/uz/warehouse.json";

/**
 * 08-dizayn-tizimi.md §11: one namespace per @pages/* package plus `common`; `uz.json`/`ru.json`
 * share the exact key structure (checked by resources.test.ts). `auth` = login (BO-01, shell);
 * `onboarding` = signup wizard BO-21 and /install (UX-INSTALL); `warehouse` = @pages/warehouse
 * (BO-03, BO-04); `finance` = @pages/finance (BO-08 …).
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
    warehouse: uzWarehouse,
    finance: uzFinance,
  },
  ru: {
    common: ruCommon,
    auth: ruAuth,
    reports: ruReports,
    pos: ruPos,
    settings: ruSettings,
    catalog: ruCatalog,
    onboarding: ruOnboarding,
    warehouse: ruWarehouse,
    finance: ruFinance,
  },
} as const;

export const NAMESPACES = ["common", "auth", "reports", "pos", "settings", "catalog", "onboarding", "warehouse", "finance"] as const;
export type Namespace = (typeof NAMESPACES)[number];
