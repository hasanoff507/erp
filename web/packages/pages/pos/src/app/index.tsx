/**
 * @pages/pos — veb-kassa (POS-01…16). Package router (24 §1): route objects relative to `/pos`,
 * rendered inside the shell's POS layout (full screen, data-theme="light", data-density="touch").
 * Bosqich 0: POS-01 and POS-02 placeholders only.
 */
import { Navigate, type RouteObject } from "react-router-dom";

import type { RouteHandle } from "@shared/models";

import { PosLogin } from "#/pages/login/ui/page/Page.tsx";
import { Sale } from "#/pages/sale/ui/page/Page.tsx";

export const routes: RouteObject[] = [
  { index: true, element: <Navigate to={Sale.route} replace /> },
  {
    path: PosLogin.route,
    element: <PosLogin.Page />,
    handle: { titleKey: PosLogin.titleKey } satisfies RouteHandle,
  },
  { path: Sale.route, element: <Sale.Page />, handle: { titleKey: Sale.titleKey } satisfies RouteHandle },
];
