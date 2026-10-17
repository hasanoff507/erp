/**
 * @pages/reports — Hisobotlar, dashboard (M12). Package router (24 §1): route objects relative to
 * the back-office root `/app`, composed by apps/shell under the back-office layout.
 * BO-02 `/app/dashboard`; BO-09 `/app/reports` — hisobotlar markazi (Bosqich 3: «Kassa / smena tarixi»,
 * «QQS registri (qaytarishlar bilan)»; other reports «Tez orada»).
 */
import type { RouteObject } from "react-router-dom";

import type { RouteHandle } from "@shared/models";

import { Reports } from "#/pages/center/ui/page/Page.tsx";
import { Dashboard } from "#/pages/dashboard/ui/page/Page.tsx";

export const routes: RouteObject[] = [Dashboard, Reports].map((screen) => ({
  path: screen.route,
  element: <screen.Page />,
  handle: { titleKey: screen.titleKey } satisfies RouteHandle,
}));
