import ruAuth from "./locales/ru/auth.json";
import ruCommon from "./locales/ru/common.json";
import ruPos from "./locales/ru/pos.json";
import ruReports from "./locales/ru/reports.json";
import uzAuth from "./locales/uz/auth.json";
import uzCommon from "./locales/uz/common.json";
import uzPos from "./locales/uz/pos.json";
import uzReports from "./locales/uz/reports.json";

/**
 * 08-dizayn-tizimi.md §11: one namespace per @pages/* package plus `common`; `uz.json`/`ru.json`
 * share the exact key structure (checked by resources.test.ts). `auth` = login (BO-01, shell).
 */
export const resources = {
  uz: { common: uzCommon, auth: uzAuth, reports: uzReports, pos: uzPos },
  ru: { common: ruCommon, auth: ruAuth, reports: ruReports, pos: ruPos },
} as const;

export const NAMESPACES = ["common", "auth", "reports", "pos"] as const;
export type Namespace = (typeof NAMESPACES)[number];
