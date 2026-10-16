/**
 * @pages/reports — Hisobotlar, dashboard (M12). Package router (24 §1): route objects relative to
 * the back-office root `/app`, composed by apps/shell under the back-office layout.
 * BO-09 `/app/reports` is not built yet (shell shows "Tez orada").
 */
import type { RouteObject } from "react-router-dom";

import type { RouteHandle } from "@shared/models";

import { Dashboard } from "#/pages/dashboard/ui/page/Page.tsx";

export const routes: RouteObject[] = [
  {
    path: Dashboard.route,
    element: <Dashboard.Page />,
    handle: { titleKey: Dashboard.titleKey } satisfies RouteHandle,
  },
];
