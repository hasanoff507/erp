/**
 * @pages/billing — Tarif va to'lov, ro'yxatdan o'tish (M17). Package router (24 §1).
 *
 * - `routes`: back-office routes under `/app` (BO-19 /app/billing — not built yet, shell shows
 *   "Tez orada").
 * - `createPublicRoutes(slots)`: top-level routes outside the protected layouts —
 *   BO-21 `/onboarding` (①② public, ③–⑥ with the new session), UX-INSTALL `/install` (public),
 *   `/recover` and `/invite` (linked from the AS login page). Each page is a lazy chunk.
 *   `slots.productImport` is the catalog's import flow for ③a and `slots.openingStockImport` the same
 *   flow with `kind="opening_stock"` for ③b, injected by the shell because page packages never import
 *   each other (24 §1).
 * - UX-INSTALL helper for the shell: `startInstallPromptCapture` (call once at start). The iOS rule
 *   (`isIosNotInstalled`, `IOS_INSTALL_PATH`) lives in `@shared/lib/platform`; re-exported here for
 *   compatibility.
 */
import type { ComponentType, ReactNode } from "react";
import type { RouteObject } from "react-router-dom";

import type { RouteHandle } from "@shared/models";

import type { OnboardingPageProps } from "#/pages/onboarding/ui/page/Page.tsx";
import type {
  OpeningStockImportSlotProps,
  ProductImportSlotProps,
} from "#/pages/onboarding/model/types/index.ts";

export const routes: RouteObject[] = [];

export interface PublicRouteSlots {
  /** ③a Excel/CSV — the catalog import flow (embedded). */
  productImport?: ComponentType<ProductImportSlotProps>;
  /** ③a «Qo'lda» — catalog product form route. */
  manualProductHref?: string | null;
  /** ③b Excel/CSV — the catalog import flow with `kind="opening_stock"` (embedded). */
  openingStockImport?: ComponentType<OpeningStockImportSlotProps>;
  /** «Yakunlash» → BO-02 (default /app/dashboard). */
  dashboardPath?: string;
  /** Shown while a lazy page chunk loads. */
  fallback?: ReactNode;
}

export function createPublicRoutes(slots: PublicRouteSlots = {}): RouteObject[] {
  const onboardingProps: OnboardingPageProps = {
    productImport: slots.productImport,
    manualProductHref: slots.manualProductHref ?? null,
    openingStockImport: slots.openingStockImport,
    dashboardPath: slots.dashboardPath ?? "/app/dashboard",
  };
  const fallback = slots.fallback ?? null;
  return [
    {
      path: "/onboarding",
      handle: { titleKey: "onboarding:title" } satisfies RouteHandle,
      lazy: async () => {
        const { Onboarding } = await import("#/pages/onboarding/ui/page/Page.tsx");
        return { element: <Onboarding.Page {...onboardingProps} /> };
      },
      hydrateFallbackElement: fallback,
    },
    {
      path: "/install",
      handle: { titleKey: "onboarding:install.pageTitle" } satisfies RouteHandle,
      lazy: async () => {
        const { Install } = await import("#/pages/install/ui/Page.tsx");
        return { element: <Install.Page /> };
      },
      hydrateFallbackElement: fallback,
    },
    {
      path: "/recover",
      handle: { titleKey: "onboarding:recover.title" } satisfies RouteHandle,
      lazy: async () => {
        const { Recover } = await import("#/pages/credentials/ui/Pages.tsx");
        return { element: <Recover.Page /> };
      },
      hydrateFallbackElement: fallback,
    },
    {
      path: "/invite",
      handle: { titleKey: "onboarding:invite.title" } satisfies RouteHandle,
      lazy: async () => {
        const { Invite } = await import("#/pages/credentials/ui/Pages.tsx");
        return { element: <Invite.Page /> };
      },
      hydrateFallbackElement: fallback,
    },
  ];
}

export type {
  OpeningStockImportResult,
  OpeningStockImportSlotProps,
  ProductImportResult,
  ProductImportSlotProps,
} from "#/pages/onboarding/model/types/index.ts";
export { startInstallPromptCapture } from "#/features/install-guide/model/index.ts";
export {
  CLOUD_PRINT_ANCHOR,
  IOS_INSTALL_PATH,
  isIosNotInstalled,
} from "#/features/install-guide/lib/platform.ts";
export { setAnalyticsSink, type AnalyticsEvent, type AnalyticsSink } from "#/shared/lib/analytics.ts";
