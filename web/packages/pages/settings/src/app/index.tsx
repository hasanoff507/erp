/**
 * @pages/settings — Do'kon, xodimlar/huquqlar, filiallar (M13, M14). Package router (24 §1): route
 * objects relative to the back-office root `/app`, composed by apps/shell under the back-office layout.
 * BO-11 /app/settings/users, BO-12 /app/settings/branches, BO-14 /app/settings/tenant (07).
 * BO-16 /app/approvals (tasdiqlash navbati, M13 approvals — 18 §9).
 * BO-20 /app/settings/telegram is not built yet (shell shows "Tez orada").
 */
import type { RouteObject } from "react-router-dom";

import type { RouteHandle } from "@shared/models";

import { Approvals } from "#/pages/approvals/ui/page/Page.tsx";
import { Branches } from "#/pages/branches/ui/page/Page.tsx";
import { Tenant } from "#/pages/tenant/ui/page/Page.tsx";
import { Users } from "#/pages/users/ui/page/Page.tsx";

export const routes: RouteObject[] = [Tenant, Users, Branches, Approvals].map((screen) => ({
  path: screen.route,
  element: <screen.Page />,
  handle: { titleKey: screen.titleKey } satisfies RouteHandle,
}));
