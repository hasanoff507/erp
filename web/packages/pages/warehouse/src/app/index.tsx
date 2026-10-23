/**
 * @pages/warehouse — Qoldiq, kirim, ko'chirish, inventarizatsiya (M04–M07).
 * Package router (24 §1): route objects relative to the back-office root `/app`.
 *
 * - BO-03 `/app/warehouse/stock` — qoldiq, ko'chirishlar, inventarizatsiyalar, hisobdan chiqarish.
 * - BO-04 `/app/purchases` — xaridnomalar, kirimlar, qaytarish, yetkazib beruvchilar.
 */
import type { RouteObject } from "react-router-dom";

import type { RouteHandle } from "@shared/models";

import { Purchases } from "#/pages/purchases/ui/page/Page.tsx";
import { Stock } from "#/pages/stock/ui/page/Page.tsx";

export const routes: RouteObject[] = [
  {
    path: Stock.route,
    element: <Stock.Page />,
    handle: { titleKey: Stock.titleKey } satisfies RouteHandle,
  },
  {
    path: Purchases.route,
    element: <Purchases.Page />,
    handle: { titleKey: Purchases.titleKey } satisfies RouteHandle,
  },
];
