/**
 * Shell router (24 §1, 07 "Route"): `/login` (BO-01), back-office `/app/*`, web POS `/pos/*`.
 * Each @pages/* package contributes route objects; back-office routes not built yet fall through to
 * "Tez orada" (ComingSoonPage) so every sidebar link of 06 §1.9 resolves.
 *
 * Permissions (24 §2): the layouts require a session; every child route additionally requires the
 * permission of its sidebar item (RoutePermissionGuard, nav-items.ts). `/` and `/app` land on the
 * first screen the user may open. Every top-level area has an errorElement (RouteErrorPage).
 */
import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { routes as aiAssistantRoutes } from "@pages/ai-assistant";
import {
  routes as billingRoutes,
  createPublicRoutes,
  startInstallPromptCapture,
  type OpeningStockImportSlotProps,
} from "@pages/billing";
import { ImportProductsFlow, routes as catalogRoutes } from "@pages/catalog";
import { routes as debtsRoutes } from "@pages/debts";
import { routes as financeRoutes } from "@pages/finance";
import { routes as onecRoutes } from "@pages/onec";
import { routes as posRoutes } from "@pages/pos";
import { routes as reportsRoutes } from "@pages/reports";
import { routes as settingsRoutes } from "@pages/settings";
import { routes as warehouseRoutes } from "@pages/warehouse";

import { IosPosGate } from "#/features/ios-install-gate/index.ts";
import { ProtectedRoute } from "#/features/protected-route/index.ts";
import {
  ComingSoonPage,
  NoPermissionPage,
  NotFoundPage,
  RouteErrorPage,
  Splash,
} from "../ui/status/index.tsx";

import { DefaultRedirect, RootRedirect, RoutePermissionGuard } from "./guards.tsx";

/** BO-21 ③b Excel/CSV: the catalog import flow for `kind=opening_stock` (19 §6). */
function OpeningStockImport(props: OpeningStockImportSlotProps) {
  return <ImportProductsFlow {...props} kind="opening_stock" />;
}

/** After login without `next`: `/` → the first permitted screen (DefaultRedirect). */
export const DEFAULT_APP_PATH = "/";
export const LOGIN_SUBSCRIPTION_EXPIRED = "/login?reason=subscription_expired";

const backOfficeRoutes: RouteObject[] = [
  { index: true, element: <DefaultRedirect inline /> },
  ...reportsRoutes,
  ...catalogRoutes,
  ...warehouseRoutes,
  ...debtsRoutes,
  ...financeRoutes,
  ...settingsRoutes,
  ...billingRoutes,
  ...aiAssistantRoutes,
  ...onecRoutes,
  { path: "*", element: <ComingSoonPage /> },
];

export const appRoutes: RouteObject[] = [
  {
    errorElement: <RouteErrorPage />,
    children: [
      { path: "/", element: <RootRedirect /> },
      {
        path: "/login",
        // Route-level code splitting: the login page loads only on /login.
        lazy: async () => {
          const { LoginPage } = await import("#/pages/login/index.ts");
          return { element: <LoginPage defaultPath={DEFAULT_APP_PATH} /> };
        },
        hydrateFallbackElement: <Splash />,
      },
      // BO-21 /onboarding, UX-INSTALL /install, /recover, /invite (@pages/billing) — outside the
      // protected layouts; ③a/③b get the catalog import flow here (pages never import each other, 24 §1).
      ...createPublicRoutes({
        productImport: ImportProductsFlow,
        manualProductHref: "/app/catalog/products/new",
        openingStockImport: OpeningStockImport,
        dashboardPath: "/app/dashboard",
        fallback: <Splash />,
      }),
      {
        path: "/app",
        lazy: async () => {
          const { BackOfficeLayout } = await import("../ui/layout/back-office/BackOfficeLayout.tsx");
          return {
            element: (
              <ProtectedRoute pending={<Splash />} noPermission={<NoPermissionPage />}>
                <BackOfficeLayout />
              </ProtectedRoute>
            ),
          };
        },
        hydrateFallbackElement: <Splash />,
        errorElement: <RouteErrorPage />,
        children: [{ element: <RoutePermissionGuard inline />, children: backOfficeRoutes }],
      },
      {
        path: "/pos",
        lazy: async () => {
          const { PosLayout } = await import("../ui/layout/pos/PosLayout.tsx");
          return {
            element: (
              <IosPosGate>
                <ProtectedRoute pending={<Splash />} noPermission={<NoPermissionPage />}>
                  <PosLayout />
                </ProtectedRoute>
              </IosPosGate>
            ),
          };
        },
        hydrateFallbackElement: <Splash />,
        errorElement: <RouteErrorPage />,
        children: [{ element: <RoutePermissionGuard inline />, children: posRoutes }],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export function createAppRouter() {
  // UX-INSTALL: keep Chrome's one-shot install prompt for the «O'rnatish» button.
  startInstallPromptCapture();
  return createBrowserRouter(appRoutes);
}
