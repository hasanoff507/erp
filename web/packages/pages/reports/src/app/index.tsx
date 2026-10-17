/**
 * @pages/reports — Hisobotlar, dashboard (M12). Package router (24 §1): route objects relative to
 * the back-office root `/app`, composed by apps/shell under the back-office layout.
 * BO-02 `/app/dashboard`; BO-09 `/app/reports` — hisobotlar markazi.
 * Also exported for the shell topbar bell (06 §1.9 — the same `alerts[]` as BO-02 «Diqqat talab
 * qiladi»): the alert list and its helpers.
 */
import type { RouteObject } from "react-router-dom";

import type { RouteHandle } from "@shared/models";

import { Reports } from "#/pages/center/ui/page/Page.tsx";
import { Dashboard } from "#/pages/dashboard/ui/page/Page.tsx";

export { AlertList, sortAlerts, type Alert, type AlertListProps } from "#/entities/alert/index.ts";

export const routes: RouteObject[] = [Dashboard, Reports].map((screen) => ({
  path: screen.route,
  element: <screen.Page />,
  handle: { titleKey: screen.titleKey } satisfies RouteHandle,
}));
