/**
 * @shared/models — 24-frontend-arxitekturasi.md §1/§3, 32 §9.
 * `generated/` comes from the FastAPI OpenAPI schema via orval (never hand-written DTOs).
 * Only cross-cutting DOMAIN types that the schema cannot express live next to it.
 */
export * from "./generated/index.ts";

export type { Money } from "@shared/lib/money";

/** 08 §11 / 06 §1.4 — interface languages; Uzbek (Latin) is the default. */
export type UiLanguage = "uz" | "ru";

/** `role_permissions.permission_code` (15 §2.1, 32 §2.5): `<module>.<action>`. */
export type PermissionCode = string;

/**
 * react-router `handle` contract shared by all @pages/* route objects: the shell topbar shows
 * `t(titleKey)` (screen name without ID — 06 §1.9).
 */
export interface RouteHandle {
  /** Fully qualified i18n key, e.g. "reports:dashboard.title". */
  titleKey?: string;
}
