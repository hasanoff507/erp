/**
 * @pages/debts — Qarz daftari (M08). Package router (24 §1): route objects relative to the back-office root
 * `/app`.
 *
 * - BO-06 `/app/debts` — qarzdorlar ro'yxati, eskirish, qarz daftari, bank to'lovi, boshlang'ich qarz,
 *   kechish / shubhali belgi (Egasi), ortiqcha to'lovlar; «Men qarzdorman» (`?direction=payable`).
 */
import type { RouteObject } from "react-router-dom";

import type { RouteHandle } from "@shared/models";

import { Debtors } from "#/pages/debtors/ui/page/Page.tsx";

export const routes: RouteObject[] = [
  {
    path: Debtors.route,
    element: <Debtors.Page />,
    handle: { titleKey: Debtors.titleKey } satisfies RouteHandle,
  },
];
